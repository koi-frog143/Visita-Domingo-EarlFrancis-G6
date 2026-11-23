import io
import tempfile
from datetime import timedelta

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, ResidentProfile, VisitorProfile
from .models import AuditLog, IDDocument, VisitRequest
from .services import decide_visit, review_document


def sample_id(name="sample.png"):
    data = io.BytesIO()
    Image.new("RGB", (100, 60), color="green").save(data, format="PNG")
    return SimpleUploadedFile(name, data.getvalue(), content_type="image/png")


class VisitWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visitor = CustomUser.objects.create_user(email="slice.visitor@example.com", full_name="Slice Visitor", role="VISITOR")
        cls.profile = VisitorProfile.objects.create(user=cls.visitor)
        cls.other = CustomUser.objects.create_user(email="slice.other@example.com", full_name="Other Visitor", role="VISITOR")
        cls.other_profile = VisitorProfile.objects.create(user=cls.other)
        cls.resident = CustomUser.objects.create_user(email="slice.resident@example.com", full_name="Slice Resident", role="RESIDENT")
        cls.host = ResidentProfile.objects.create(user=cls.resident, unit_number="101")
        cls.other_resident = CustomUser.objects.create_user(email="slice.host2@example.com", full_name="Other Resident", role="RESIDENT")
        ResidentProfile.objects.create(user=cls.other_resident, unit_number="102")
        cls.admin = CustomUser.objects.create_user(email="slice.admin@example.com", full_name="Slice Admin", role="ADMIN")
        cls.guard = CustomUser.objects.create_user(email="slice.guard@example.com", full_name="Slice Guard", role="GUARD")

    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.storage.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.client.force_login(self.visitor)

    def data(self, **overrides):
        start = timezone.localtime(timezone.now() + timedelta(days=2))
        data = {"resident": str(self.host.pk), "purpose": "Family visit", "expected_start_at": start.strftime("%Y-%m-%dT%H:%M"), "expected_end_at": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")}
        data.update(overrides)
        return data

    def visit(self):
        return VisitRequest.objects.create(visitor=self.profile, created_by=self.visitor, resident=self.host, purpose="Family visit", expected_start_at=timezone.now()+timedelta(days=2), expected_end_at=timezone.now()+timedelta(days=2, hours=2))

    def verified(self):
        return IDDocument.objects.create(visitor=self.profile, document_type="School ID", file=sample_id(), review_status="VERIFIED", reviewed_by=self.admin, reviewed_at=timezone.now())

    def test_create_read_edit_delete_from_ui(self):
        response = self.client.post(reverse("visit_create"), self.data())
        visit = VisitRequest.objects.get()
        self.assertRedirects(response, reverse("visit_detail", args=[visit.pk]))
        self.assertContains(self.client.get(reverse("visit_list")), "Slice Visitor")
        self.client.post(reverse("visit_edit", args=[visit.pk]), self.data(purpose="Updated purpose"))
        visit.refresh_from_db()
        self.assertEqual(visit.purpose, "Updated purpose")
        self.assertContains(self.client.get(reverse("visit_delete", args=[visit.pk])), "Delete this request?")
        self.assertTrue(VisitRequest.objects.filter(pk=visit.pk).exists())
        self.assertRedirects(self.client.post(reverse("visit_delete", args=[visit.pk])), reverse("visit_list"))
        self.assertFalse(VisitRequest.objects.exists())
        self.assertEqual(AuditLog.objects.count(), 3)

    def test_required_and_blank_purpose_are_rejected(self):
        for purpose in ["", "   "]:
            response = self.client.post(reverse("visit_create"), self.data(purpose=purpose))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(VisitRequest.objects.exists())

    def test_empty_post_shows_required_field_errors(self):
        for route in ["visit_create", "id_upload"]:
            self.assertContains(self.client.post(reverse(route), {}), "This field is required")

    def test_departure_before_or_equal_arrival_is_rejected(self):
        data = self.data()
        for end in [data["expected_start_at"], "2020-01-01T12:00"]:
            response = self.client.post(reverse("visit_create"), {**data, "expected_end_at": end})
            self.assertContains(response, "Departure must be later than arrival")
        self.assertFalse(VisitRequest.objects.exists())

    def test_past_arrival_and_malformed_dates_are_rejected(self):
        for value in ["2020-01-01T12:00", "invalid"]:
            response = self.client.post(reverse("visit_create"), self.data(expected_start_at=value))
            self.assertEqual(response.status_code, 200)
        self.assertFalse(VisitRequest.objects.exists())

    def test_inactive_or_wrong_role_host_is_rejected(self):
        self.resident.is_active = False
        self.resident.save()
        self.assertEqual(self.client.post(reverse("visit_create"), self.data()).status_code, 200)
        self.assertEqual(self.client.post(reverse("visit_create"), self.data(resident=str(self.profile.pk))).status_code, 200)
        self.assertFalse(VisitRequest.objects.exists())

    def test_forged_owner_status_and_decision_time_are_ignored(self):
        self.client.post(reverse("visit_create"), self.data(visitor=str(self.other_profile.pk), created_by=str(self.other.pk), status="APPROVED", decided_at="2027-01-01T12:00"))
        visit = VisitRequest.objects.get()
        self.assertEqual(visit.visitor_id, self.profile.pk)
        self.assertEqual(visit.created_by_id, self.visitor.pk)
        self.assertEqual(visit.status, "PENDING")
        self.assertIsNone(visit.decided_at)

    def test_other_visitors_cannot_read_edit_cancel_or_delete(self):
        visit = self.visit()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("visit_list")), "Family visit")
        for route in ["visit_detail", "visit_edit", "visit_cancel", "visit_delete"]:
            self.assertEqual(self.client.get(reverse(route, args=[visit.pk])).status_code, 404)
            self.assertEqual(self.client.post(reverse(route, args=[visit.pk]), self.data()).status_code, 404)
        self.assertTrue(VisitRequest.objects.filter(pk=visit.pk).exists())

    def test_other_resident_cannot_read_or_decide(self):
        visit = self.visit()
        self.client.force_login(self.other_resident)
        self.assertEqual(self.client.get(reverse("visit_detail", args=[visit.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "REJECTED"}).status_code, 404)

    def test_anonymous_redirect_and_role_restrictions(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("visit_list")).status_code, 302)
        for user in [self.resident, self.admin, self.guard]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("visit_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("visit_list")).status_code, 403)

    def test_approval_requires_verified_id(self):
        visit = self.visit()
        self.client.force_login(self.resident)
        response = self.client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "APPROVED"}, follow=True)
        self.assertContains(response, "Approval requires an administrator-verified ID")
        visit.refresh_from_db()
        self.assertEqual(visit.status, "PENDING")
        self.assertFalse(AuditLog.objects.exists())

    def test_approval_persists_timestamp_and_audit(self):
        self.verified()
        visit = self.visit()
        self.client.force_login(self.resident)
        self.client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "APPROVED"})
        visit.refresh_from_db()
        self.assertEqual(visit.status, "APPROVED")
        self.assertIsNotNone(visit.decided_at)
        self.assertTrue(AuditLog.objects.filter(actor=self.resident, entity_id=visit.pk, action="VISIT_APPROVED").exists())

    def test_rejection_does_not_require_verified_id(self):
        visit = self.visit()
        decide_visit(actor=self.resident, visit_id=visit.pk, decision="REJECTED")
        visit.refresh_from_db()
        self.assertEqual(visit.status, "REJECTED")

    def test_duplicate_or_conflicting_decision_cannot_overwrite(self):
        self.verified()
        visit = self.visit()
        decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")
        for decision in ["APPROVED", "REJECTED"]:
            with self.assertRaises(ValidationError):
                decide_visit(actor=self.resident, visit_id=visit.pk, decision=decision)
        self.assertEqual(AuditLog.objects.filter(entity_id=visit.pk).count(), 1)

    def test_cancelled_request_cannot_be_approved(self):
        visit = self.visit()
        self.client.post(reverse("visit_cancel", args=[visit.pk]))
        with self.assertRaises(ValidationError):
            decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")

    def test_expired_request_cannot_be_approved(self):
        visit = self.visit()
        VisitRequest.objects.filter(pk=visit.pk).update(expected_start_at=timezone.now()-timedelta(hours=1))
        with self.assertRaises(ValidationError):
            decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")

    def test_approved_request_cannot_be_edited_or_deleted(self):
        self.verified()
        visit = self.visit()
        decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")
        self.client.post(reverse("visit_edit", args=[visit.pk]), self.data(purpose="Forged change"))
        self.client.post(reverse("visit_delete", args=[visit.pk]))
        visit.refresh_from_db()
        self.assertEqual(visit.purpose, "Family visit")
        self.assertEqual(visit.status, "APPROVED")

    def test_approved_request_cancels_and_retains_history(self):
        self.verified()
        visit = self.visit()
        decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")
        self.client.get(reverse("visit_cancel", args=[visit.pk]))
        visit.refresh_from_db()
        self.assertEqual(visit.status, "APPROVED")
        self.client.post(reverse("visit_cancel", args=[visit.pk]))
        visit.refresh_from_db()
        self.assertEqual(visit.status, "CANCELLED")
        self.assertIsNotNone(visit.decided_at)

    def test_decision_is_post_only_and_csrf_protected(self):
        visit = self.visit()
        self.client.force_login(self.resident)
        self.assertEqual(self.client.get(reverse("visit_decide", args=[visit.pk])).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.visitor)
        for route in ["visit_delete", "visit_cancel", "visit_edit"]:
            self.assertEqual(csrf_client.post(reverse(route, args=[visit.pk]), self.data()).status_code, 403)
        self.assertEqual(csrf_client.post(reverse("visit_create"), self.data()).status_code, 403)
        csrf_client.force_login(self.resident)
        self.assertEqual(csrf_client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "REJECTED"}).status_code, 403)

    def test_invalid_decision_is_rejected(self):
        visit = self.visit()
        self.client.force_login(self.resident)
        self.client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "ADMIN"})
        visit.refresh_from_db()
        self.assertEqual(visit.status, "PENDING")

    def test_filter_and_admin_read_access(self):
        visit = self.visit()
        self.assertNotContains(self.client.get(reverse("visit_list")+"?status=REJECTED"), "View request →")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("visit_list")), str(visit.pk))
        self.assertEqual(self.client.post(reverse("visit_decide", args=[visit.pk]), {"decision": "APPROVED"}).status_code, 403)

    def test_database_constraints_reject_invalid_dates_status_and_decision(self):
        visit = self.visit()
        for values in [{"expected_end_at": visit.expected_start_at}, {"status": "INVALID"}, {"status": "APPROVED"}]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                VisitRequest.objects.filter(pk=visit.pk).update(**values)

    def test_upload_verify_and_approve_end_to_end(self):
        self.client.post(reverse("id_upload"), {"document_type": "School ID", "file": sample_id()})
        document = IDDocument.objects.get()
        self.assertEqual(document.visitor_id, self.profile.pk)
        self.assertEqual(document.review_status, "PENDING")
        self.assertNotIn("sample", document.file.name)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("id_review", args=[document.pk])), "Slice Visitor")
        response = self.client.get(reverse("id_file", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        # Consume through Django's client wrapper so request cleanup preserves
        # the TestCase transaction before the next request.
        self.assertGreater(len(b"".join(response.streaming_content)), 0)
        self.client.post(reverse("id_review", args=[document.pk]), {"decision": "VERIFIED", "review_note": "Sample reviewed"})
        document.refresh_from_db()
        self.assertEqual(document.reviewed_by, self.admin)
        visit = self.visit()
        decide_visit(actor=self.resident, visit_id=visit.pk, decision="APPROVED")
        self.assertEqual(VisitRequest.objects.get(pk=visit.pk).status, "APPROVED")

    def test_fake_image_wrong_extension_and_oversized_uploads_rejected(self):
        uploads = [SimpleUploadedFile("fake.png", b"not an image", content_type="image/png"), sample_id("wrong.jpg")]
        data = sample_id().read() + b"0" * (5 * 1024 * 1024)
        uploads.append(SimpleUploadedFile("big.png", data, content_type="image/png"))
        for upload in uploads:
            response = self.client.post(reverse("id_upload"), {"document_type": "School ID", "file": upload})
            self.assertEqual(response.status_code, 200)
        self.assertFalse(IDDocument.objects.exists())

    def test_id_owner_and_review_result_cannot_be_forged(self):
        self.client.post(reverse("id_upload"), {"document_type": "School ID", "file": sample_id(), "visitor": str(self.other_profile.pk), "review_status": "VERIFIED"})
        document = IDDocument.objects.get()
        self.assertEqual(document.visitor, self.profile)
        self.assertEqual(document.review_status, "PENDING")

    def test_only_administrator_can_download_or_review_ids(self):
        document = self.verified()
        for user in [self.visitor, self.other, self.resident, self.guard]:
            self.client.force_login(user)
            for route in ["id_file", "id_review"]:
                self.assertEqual(self.client.get(reverse(route, args=[document.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse(route, args=[document.pk]), {"decision": "VERIFIED"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("id_list")).status_code, 403)

    def test_other_visitors_cannot_see_id_metadata(self):
        self.verified()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("id_list")), "School ID")

    def test_rejected_id_needs_reason_and_cannot_be_reviewed_twice(self):
        document = IDDocument.objects.create(visitor=self.profile, document_type="School ID", file=sample_id())
        self.client.force_login(self.admin)
        response = self.client.post(reverse("id_review", args=[document.pk]), {"decision": "REJECTED", "review_note": ""})
        self.assertContains(response, "Give the visitor a reason")
        review_document(actor=self.admin, document_id=document.pk, decision="REJECTED", note="Image unreadable")
        with self.assertRaises(ValidationError):
            review_document(actor=self.admin, document_id=document.pk, decision="VERIFIED", note="")
        self.client.force_login(self.visitor)
        self.assertContains(self.client.get(reverse("id_list")), "Image unreadable")

    def test_no_public_media_route(self):
        document = self.verified()
        self.client.logout()
        self.assertEqual(self.client.get("/media/"+document.file.name).status_code, 404)
        self.assertEqual(self.client.get(reverse("id_file", args=[document.pk])).status_code, 302)

    def test_new_tables_are_not_accessible_to_supabase_api_roles(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            for (role,) in cursor.fetchall():
                for model in [VisitRequest, IDDocument, AuditLog]:
                    for privilege in ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"]:
                        cursor.execute("SELECT has_table_privilege(%s, %s, %s)", [role, model._meta.db_table, privilege])
                        self.assertFalse(cursor.fetchone()[0])

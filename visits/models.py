import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def private_id_path(instance, filename):
    # Never retain a visitor-supplied name or expose a public media URL.
    suffix = filename.rsplit(".", 1)[-1].lower()
    return f"ids/{instance.visitor_id}/{uuid.uuid4().hex}.{suffix}"


class IDDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey("accounts.VisitorProfile", on_delete=models.PROTECT, related_name="id_documents")
    document_type = models.CharField(max_length=40)
    file = models.FileField(upload_to=private_id_path, max_length=255)
    review_status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(review_status__in=["PENDING", "VERIFIED", "REJECTED"]), name="valid_id_review_status"),
            models.CheckConstraint(
                condition=(models.Q(review_status="PENDING", reviewed_at__isnull=True, reviewed_by__isnull=True)
                           | models.Q(review_status__in=["VERIFIED", "REJECTED"], reviewed_at__isnull=False, reviewed_by__isnull=False)),
                name="consistent_id_review",
            ),
        ]


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey("accounts.VisitorProfile", on_delete=models.PROTECT, related_name="visits")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_visits", editable=False)
    resident = models.ForeignKey("accounts.ResidentProfile", on_delete=models.PROTECT, related_name="visit_requests")
    purpose = models.CharField(max_length=255)
    expected_start_at = models.DateTimeField()
    expected_end_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["status", "expected_start_at"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(expected_end_at__gt=models.F("expected_start_at")), name="visit_end_after_start"),
            models.CheckConstraint(condition=models.Q(status__in=["PENDING", "APPROVED", "REJECTED", "CANCELLED"]), name="valid_visit_status"),
            models.CheckConstraint(
                condition=(models.Q(status="PENDING", decided_at__isnull=True)
                           | models.Q(status__in=["APPROVED", "REJECTED"], decided_at__isnull=False)
                           | models.Q(status="CANCELLED")),
                name="consistent_visit_decision",
            ),
        ]

    def clean(self):
        super().clean()
        if self.created_by_id and self.visitor_id and self.created_by_id != self.visitor.user_id:
            raise ValidationError("The creator must be the visitor account linked to this request.")
        if self.expected_start_at and self.expected_end_at and self.expected_end_at <= self.expected_start_at:
            raise ValidationError({"expected_end_at": "Departure must be later than arrival."})
        if not self.purpose.strip():
            raise ValidationError({"purpose": "Tell your host the purpose of your visit."})

    @property
    def can_edit(self):
        return self.status == self.Status.PENDING and self.expected_start_at > timezone.now()

    @property
    def can_cancel(self):
        return self.status in [self.Status.PENDING, self.Status.APPROVED]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    entity_type = models.CharField(max_length=40)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=40)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

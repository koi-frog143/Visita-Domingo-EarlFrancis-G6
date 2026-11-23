"""Atomic state transitions. Views never trust posted owner or status fields."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, VisitorProfile
from .models import AuditLog, IDDocument, VisitRequest


def record_action(actor, entity, action):
    AuditLog.objects.create(actor=actor, entity_type=type(entity).__name__, entity_id=entity.pk, action=action)


@transaction.atomic
def decide_visit(*, actor, visit_id, decision):
    if actor.role != CustomUser.Role.RESIDENT or not actor.is_active:
        raise PermissionDenied
    visit = VisitRequest.objects.select_for_update().get(pk=visit_id)
    if visit.resident.user_id != actor.pk:
        raise PermissionDenied
    if decision not in [VisitRequest.Status.APPROVED, VisitRequest.Status.REJECTED]:
        raise ValidationError("Choose approve or reject.")
    if visit.status != VisitRequest.Status.PENDING:
        raise ValidationError("This request has already been decided or cancelled. Refresh to see its current status.")
    if visit.expected_start_at <= timezone.now():
        raise ValidationError("This request's arrival time has passed. Ask the visitor to submit a new request.")
    # ID review uses the same visitor lock, serializing verification with approval.
    VisitorProfile.objects.select_for_update().get(pk=visit.visitor_id)
    if not visit.visitor.user.is_active:
        raise ValidationError("The visitor account is inactive.")
    if decision == VisitRequest.Status.APPROVED and not IDDocument.objects.filter(
        visitor=visit.visitor, review_status=IDDocument.Status.VERIFIED,
    ).exists():
        raise ValidationError("Approval requires an administrator-verified ID. The visitor can upload an ID from their dashboard.")
    visit.status = decision
    visit.decided_at = timezone.now()
    visit.save(update_fields=["status", "decided_at"])
    record_action(actor, visit, f"VISIT_{decision}")
    return visit


@transaction.atomic
def review_document(*, actor, document_id, decision, note):
    if actor.role != CustomUser.Role.ADMIN or not actor.is_active:
        raise PermissionDenied
    document = IDDocument.objects.select_for_update().get(pk=document_id)
    VisitorProfile.objects.select_for_update().get(pk=document.visitor_id)
    if document.review_status != IDDocument.Status.PENDING:
        raise ValidationError("This ID has already been reviewed.")
    if decision not in [IDDocument.Status.VERIFIED, IDDocument.Status.REJECTED]:
        raise ValidationError("Choose verify or reject.")
    if decision == IDDocument.Status.REJECTED and not note.strip():
        raise ValidationError("Give the visitor a reason for rejection.")
    document.review_status = decision
    document.review_note = note.strip()
    document.reviewed_by = actor
    document.reviewed_at = timezone.now()
    document.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at"])
    record_action(actor, document, f"ID_{decision}")
    return document

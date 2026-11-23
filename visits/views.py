from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import CustomUser, VisitorProfile
from .forms import DecisionForm, IDUploadForm, ReviewForm, VisitRequestForm
from .models import IDDocument, VisitRequest
from .services import decide_visit, record_action, review_document


def visible_visits(user):
    visits = VisitRequest.objects.select_related("visitor__user", "resident__user")
    if user.role == CustomUser.Role.VISITOR:
        return visits.filter(visitor__user=user)
    if user.role == CustomUser.Role.RESIDENT:
        return visits.filter(resident__user=user)
    if user.role == CustomUser.Role.ADMIN:
        return visits
    # The guard's QR workflow is outside PD2; do not disclose pending visits.
    raise PermissionDenied


@login_required
def visit_list(request):
    visits = visible_visits(request.user)
    status = request.GET.get("status", "")
    if status in VisitRequest.Status.values:
        visits = visits.filter(status=status)
    from django.core.paginator import Paginator
    page = Paginator(visits, 15).get_page(request.GET.get("page"))
    return render(request, "visits/list.html", {"page_obj": page, "statuses": VisitRequest.Status.choices, "selected_status": status})


@role_required(CustomUser.Role.VISITOR)
def visit_create(request):
    form = VisitRequestForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            profile, _ = VisitorProfile.objects.get_or_create(user=request.user)
            visit = form.save(commit=False)
            visit.visitor = profile
            visit.created_by = request.user
            visit.save()
            record_action(request.user, visit, "VISIT_CREATED")
        messages.success(request, "Visit request sent. Your resident can now review it.")
        return redirect("visit_detail", pk=visit.pk)
    return render(request, "visits/form.html", {"form": form, "editing": False})


@login_required
def visit_detail(request, pk):
    visit = get_object_or_404(visible_visits(request.user), pk=pk)
    return render(request, "visits/detail.html", {
        "visit": visit, "decision_form": DecisionForm(),
        "verified_id": IDDocument.objects.filter(visitor=visit.visitor, review_status="VERIFIED").exists(),
    })


@role_required(CustomUser.Role.VISITOR)
def visit_edit(request, pk):
    with transaction.atomic():
        visit = get_object_or_404(VisitRequest.objects.select_for_update(), pk=pk, visitor__user=request.user)
        if not visit.can_edit:
            messages.error(request, "Only pending requests with a future arrival time can be edited.")
            return redirect("visit_detail", pk=pk)
        form = VisitRequestForm(request.POST if request.method == "POST" else None, instance=visit)
        if request.method == "POST" and form.is_valid():
            form.save()
            record_action(request.user, visit, "VISIT_UPDATED")
            messages.success(request, "Visit request updated.")
            return redirect("visit_detail", pk=pk)
    return render(request, "visits/form.html", {"form": form, "editing": True, "visit": visit})


@role_required(CustomUser.Role.VISITOR)
def visit_cancel(request, pk):
    with transaction.atomic():
        visit = get_object_or_404(VisitRequest.objects.select_for_update(), pk=pk, visitor__user=request.user)
        if request.method == "POST":
            if visit.can_cancel:
                visit.status = VisitRequest.Status.CANCELLED
                visit.save(update_fields=["status"])
                record_action(request.user, visit, "VISIT_CANCELLED")
                messages.success(request, "Visit cancelled. The request remains in your history.")
            else:
                messages.error(request, "This request cannot be cancelled in its current state.")
            return redirect("visit_detail", pk=pk)
    return render(request, "visits/confirm.html", {"visit": visit, "action": "Cancel", "deleting": False})


@role_required(CustomUser.Role.VISITOR)
def visit_delete(request, pk):
    with transaction.atomic():
        visit = get_object_or_404(VisitRequest.objects.select_for_update(), pk=pk, visitor__user=request.user)
        if request.method == "POST":
            if visit.status == VisitRequest.Status.PENDING:
                record_action(request.user, visit, "VISIT_DELETED")
                visit.delete()
                messages.success(request, "Pending visit request deleted.")
                return redirect("visit_list")
            messages.error(request, "Only pending requests can be deleted. Decided requests are retained as history.")
            return redirect("visit_detail", pk=pk)
    return render(request, "visits/confirm.html", {"visit": visit, "action": "Delete", "deleting": True})


@role_required(CustomUser.Role.RESIDENT)
@require_POST
def visit_decide(request, pk):
    # Scope before entering the service so foreign IDs receive a uniform 404.
    get_object_or_404(VisitRequest, pk=pk, resident__user=request.user)
    form = DecisionForm(request.POST)
    if form.is_valid():
        try:
            visit = decide_visit(actor=request.user, visit_id=pk, decision=form.cleaned_data["decision"])
            messages.success(request, f"Visit {visit.get_status_display().lower()}.")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
    else:
        messages.error(request, "Choose approve or reject.")
    return redirect("visit_detail", pk=pk)


@login_required
def id_list(request):
    documents = IDDocument.objects.select_related("visitor__user", "reviewed_by")
    if request.user.role == CustomUser.Role.VISITOR:
        documents = documents.filter(visitor__user=request.user)
    elif request.user.role != CustomUser.Role.ADMIN:
        raise PermissionDenied
    return render(request, "visits/ids.html", {"documents": documents[:100]})


@role_required(CustomUser.Role.VISITOR)
def id_upload(request):
    form = IDUploadForm(request.POST if request.method == "POST" else None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            profile, _ = VisitorProfile.objects.get_or_create(user=request.user)
            document = form.save(commit=False)
            document.visitor = profile
            document.save()
            record_action(request.user, document, "ID_SUBMITTED")
        messages.success(request, "ID submitted for administrator review.")
        return redirect("id_list")
    return render(request, "visits/upload.html", {"form": form})


@role_required(CustomUser.Role.ADMIN)
def id_review(request, pk):
    document = get_object_or_404(IDDocument.objects.select_related("visitor__user"), pk=pk)
    form = ReviewForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            review_document(actor=request.user, document_id=pk, decision=form.cleaned_data["decision"], note=form.cleaned_data["review_note"])
            messages.success(request, "ID review saved. The visitor can see the result.")
            return redirect("id_list")
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "visits/review.html", {"form": form, "document": document})


@role_required(CustomUser.Role.ADMIN)
def id_file(request, pk):
    document = get_object_or_404(IDDocument, pk=pk)
    try:
        response = FileResponse(document.file.open("rb"), as_attachment=True, filename=f"id-{document.pk}{'.png' if document.file.name.endswith('.png') else '.jpg'}")
    except FileNotFoundError:
        raise Http404("This ID file is unavailable. Ask the visitor to upload a new copy.")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response

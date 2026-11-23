from pathlib import Path

from django import forms
from django.utils import timezone

from accounts.models import ResidentProfile
from .models import IDDocument, VisitRequest


class ResidentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.user.full_name} — Unit {obj.unit_number}"


class VisitRequestForm(forms.ModelForm):
    resident = ResidentChoiceField(queryset=ResidentProfile.objects.none(), label="Resident / host", empty_label="Choose your host")

    class Meta:
        model = VisitRequest
        fields = ["resident", "purpose", "expected_start_at", "expected_end_at"]
        labels = {"expected_start_at": "Expected arrival", "expected_end_at": "Expected departure"}
        widgets = {
            "purpose": forms.Textarea(attrs={"rows": 3, "placeholder": "What brings you here?"}),
            "expected_start_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "expected_end_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resident"].queryset = ResidentProfile.objects.filter(
            user__is_active=True, user__role="RESIDENT",
        ).exclude(unit_number="").select_related("user").order_by("unit_number", "user__full_name")

    def clean_expected_start_at(self):
        value = self.cleaned_data["expected_start_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Choose an arrival time in the future.")
        return value


class IDUploadForm(forms.ModelForm):
    # ImageField verifies actual image content with Pillow, not just the extension.
    file = forms.ImageField(label="ID image", help_text="JPG or PNG, up to 5 MB. Use a sample ID for the lab.")

    class Meta:
        model = IDDocument
        fields = ["document_type", "file"]
        widgets = {"document_type": forms.TextInput(attrs={"placeholder": "School ID or government ID"})}

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Choose an image no larger than 5 MB.")
        expected_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(Path(upload.name).suffix.lower())
        if not expected_format or upload.image.format != expected_format:
            raise forms.ValidationError("Upload a JPG or PNG image with a matching file extension.")
        return upload


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[("VERIFIED", "Verify ID"), ("REJECTED", "Reject ID")])
    review_note = forms.CharField(label="Review note", max_length=255, required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        data = super().clean()
        if data.get("decision") == "REJECTED" and not data.get("review_note"):
            self.add_error("review_note", "Give the visitor a reason for rejection.")
        return data


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("APPROVED", "Approve visit"), ("REJECTED", "Reject visit")])

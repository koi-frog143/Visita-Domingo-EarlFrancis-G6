import uuid
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, router, transaction
from django.db.models.functions import Lower


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).strip().lower()
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # Django's built-in salted password hashing.
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "ADMIN")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_superuser=True.")
        if extra_fields.get("role") != "ADMIN":
            raise ValueError("Superusers must have the ADMIN role.")
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        GUARD = "GUARD", "Security Guard"
        RESIDENT = "RESIDENT", "Resident"
        VISITOR = "VISITOR", "Visitor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Use unique email instead of a separate username.
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(
        max_length=30, blank=True,
        validators=[RegexValidator(
            r"^\+?(?=[0-9() .-]*[0-9])[0-9() .-]{7,30}$",
            "Enter a valid contact number using 7–30 digits, spaces, parentheses, dots or hyphens.",
        )],
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VISITOR)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]
    objects = CustomUserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="unique_visita_email_ci"),
            models.CheckConstraint(
                condition=models.Q(role__in=["ADMIN", "GUARD", "RESIDENT", "VISITOR"]),
                name="valid_visita_user_role",
            ),
        ]

    def clean(self):
        super().clean()
        self.validate_role_profiles(self._state.db or router.db_for_write(type(self), instance=self))

    def validate_role_profiles(self, using):
        if self.role not in self.Role.values:
            raise ValidationError({"role": "Choose a valid Visita role."})
        if self.is_superuser and (self.role != self.Role.ADMIN or not self.is_staff):
            raise ValidationError({"role": "Superusers must remain staff Administrators."})
        if ResidentProfile.objects.using(using).filter(user_id=self.pk).exists() and self.role != self.Role.RESIDENT:
            raise ValidationError({"role": "This account has a Resident profile. Its role cannot be changed while that profile exists."})
        if VisitorProfile.objects.using(using).filter(user_id=self.pk).exists() and self.role != self.Role.VISITOR:
            raise ValidationError({"role": "This account has a Visitor profile. Its role cannot be changed while that profile exists."})

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        # All role/profile writes serialize on the same account row.
        with transaction.atomic(using=using):
            type(self).objects.using(using).select_for_update().filter(pk=self.pk).first()
            self.validate_role_profiles(using)
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class ResidentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="resident_profile")
    unit_number = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        validate_profile(self, CustomUser.Role.RESIDENT, VisitorProfile)

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            CustomUser.objects.using(using).select_for_update().get(pk=self.user_id)
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.full_name} - Unit {self.unit_number}"


class VisitorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="visitor_profile")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        validate_profile(self, CustomUser.Role.VISITOR, ResidentProfile)

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            CustomUser.objects.using(using).select_for_update().get(pk=self.user_id)
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return self.user.full_name


def validate_profile(profile, expected_role, other_model):
    if not profile.user_id:
        return  # The required FK is reported by full_clean / ModelForm.
    using = profile._state.db or router.db_for_write(type(profile), instance=profile)
    user = CustomUser.objects.using(using).filter(pk=profile.user_id).first()
    if user is None:
        return  # Let foreign-key validation report a missing account.
    if user.role != expected_role:
        raise ValidationError({"user": f"This profile requires a {expected_role} account."})
    if other_model.objects.using(using).filter(user_id=profile.user_id).exists():
        raise ValidationError({"user": "An account cannot have both Resident and Visitor profiles."})
    if not profile._state.adding:
        original = type(profile).objects.using(using).filter(pk=profile.pk).values_list("user_id", flat=True).first()
        if original is not None and original != profile.user_id:
            raise ValidationError({"user": "An existing profile cannot be reassigned to another account."})

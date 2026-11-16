from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .forms import EmailAuthenticationForm, ProfileUpdateForm, RegistrationForm
from .models import VisitorProfile


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            VisitorProfile.objects.create(user=user)
        messages.success(request, "Account created! You can now log in.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})


class VisitaLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def form_invalid(self, form):
        messages.error(self.request, "Invalid email or password. Please try again.")
        return super().form_invalid(form)


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("profile")
    return render(request, "accounts/edit_profile.html", {"form": form})

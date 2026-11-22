from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from apps.accounts.models import Role

from .models import CitizenProfile

User = get_user_model()


class CitizenLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True})
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role != Role.CITIZEN:
            raise forms.ValidationError(
                "This sign-in is for citizens. Dispatchers and administrators use the operations dashboard.",
                code="not_citizen",
            )


class RegisterForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=32, help_text="Responders may call this number.")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return data

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(
            email=d["email"],
            password=d["password1"],
            first_name=d["first_name"],
            last_name=d["last_name"],
            phone=d["phone"],
            role=Role.CITIZEN,
        )
        CitizenProfile.objects.create(user=user)
        return user


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=32)
    address = forms.CharField(max_length=255, required=False, label="Home address")
    emergency_contact_name = forms.CharField(max_length=120, required=False)
    emergency_contact_phone = forms.CharField(max_length=32, required=False)

    @transaction.atomic
    def save(self, user):
        d = self.cleaned_data
        user.first_name, user.last_name, user.phone = d["first_name"], d["last_name"], d["phone"]
        user.save(update_fields=["first_name", "last_name", "phone"])
        profile, _ = CitizenProfile.objects.get_or_create(user=user)
        profile.address = d["address"]
        profile.emergency_contact_name = d["emergency_contact_name"]
        profile.emergency_contact_phone = d["emergency_contact_phone"]
        profile.save()

from django import forms
from django.contrib.auth.forms import AuthenticationForm


class OpsAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "autocomplete": "email",
                "placeholder": "Enter email",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "Enter password",
                "autocomplete": "current-password",
            }
        )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_ops:
            raise forms.ValidationError(
                "This sign-in is for dispatchers and administrators only.",
                code="not_ops",
            )
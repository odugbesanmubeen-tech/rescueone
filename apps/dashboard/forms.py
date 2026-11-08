from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from apps.accounts.models import Role
from apps.dispatch.models import DispatcherProfile
from apps.incidents.models import Category
from apps.responders.models import ResponderProfile, ResponderType
from apps.stations.models import Station
from apps.vehicles.models import Vehicle

User = get_user_model()


class LatLngMixin:
    """Optional latitude/longitude pair; both or neither."""

    def clean_latlng(self):
        lat = self.cleaned_data.get("latitude")
        lng = self.cleaned_data.get("longitude")
        if (lat is None) != (lng is None):
            raise forms.ValidationError("Enter both latitude and longitude, or leave both empty.")
        return lat, lng


def latitude_field():
    return forms.FloatField(required=False, min_value=-90, max_value=90, widget=forms.NumberInput(attrs={"step": "any"}))


def longitude_field():
    return forms.FloatField(required=False, min_value=-180, max_value=180, widget=forms.NumberInput(attrs={"step": "any"}))


class IncidentLogForm(LatLngMixin, forms.Form):
    category = forms.ChoiceField(choices=Category.choices)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=False)
    reporter_name = forms.CharField(max_length=120, required=False, label="Caller name")
    reporter_phone = forms.CharField(max_length=32, required=False, label="Caller phone")
    address_text = forms.CharField(max_length=255, required=False, label="Address / landmark")
    latitude = latitude_field()
    longitude = longitude_field()

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        lat, lng = self.clean_latlng()
        if lat is None and not data.get("address_text", "").strip():
            raise forms.ValidationError("Provide an address, or latitude and longitude.")
        return data


class StatusUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=[])
    note = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, allowed=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [(s.value, s.label) for s in allowed]


class StationForm(forms.ModelForm):
    class Meta:
        model = Station
        fields = ["name", "address", "phone", "latitude", "longitude", "is_active"]
        widgets = {
            "latitude": forms.NumberInput(attrs={"step": "any"}),
            "longitude": forms.NumberInput(attrs={"step": "any"}),
        }

    def clean(self):
        data = super().clean()
        if (data.get("latitude") is None) != (data.get("longitude") is None):
            raise forms.ValidationError("Enter both latitude and longitude, or leave both empty.")
        return data


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["number", "vehicle_type", "station", "is_available"]


class StaffUserForm(forms.Form):
    """Admin-created accounts for responders and dispatchers."""

    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=32, required=False)
    password = forms.CharField(widget=forms.PasswordInput, help_text="The user can sign in with this password.")
    station = forms.ModelChoiceField(queryset=Station.objects.filter(is_active=True), required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        pw = self.cleaned_data["password"]
        validate_password(pw)
        return pw

    def _make_user(self, role):
        d = self.cleaned_data
        return User.objects.create_user(
            email=d["email"],
            password=d["password"],
            first_name=d["first_name"],
            last_name=d["last_name"],
            phone=d.get("phone", ""),
            role=role,
        )


class ResponderCreateForm(StaffUserForm):
    responder_type = forms.ChoiceField(choices=ResponderType.choices)
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.all(), required=False)

    @transaction.atomic
    def save(self):
        user = self._make_user(Role.RESPONDER)
        return ResponderProfile.objects.create(
            user=user,
            responder_type=self.cleaned_data["responder_type"],
            station=self.cleaned_data.get("station"),
            vehicle=self.cleaned_data.get("vehicle"),
        )


class DispatcherCreateForm(StaffUserForm):
    employee_id = forms.CharField(max_length=32, required=False)

    @transaction.atomic
    def save(self):
        user = self._make_user(Role.DISPATCHER)
        return DispatcherProfile.objects.create(
            user=user,
            employee_id=self.cleaned_data.get("employee_id", ""),
            station=self.cleaned_data.get("station"),
        )

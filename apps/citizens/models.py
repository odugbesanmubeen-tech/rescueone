from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


class CitizenProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="citizen_profile")
    address = models.CharField(max_length=255, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"Citizen: {self.user}"


@receiver(post_save, sender=User)
def create_or_update_citizen_profile(sender, instance, created, **kwargs):
    """
    Automatically creates a CitizenProfile whenever a new User is created.
    """
    if created:
        CitizenProfile.objects.create(user=instance)
    else:
        # Safeguard to ensure a profile exists if the user is updated later
        if hasattr(instance, 'citizen_profile'):
            instance.citizen_profile.save()
        else:
            CitizenProfile.objects.create(user=instance)

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    CITIZEN = "CITIZEN", "Citizen"
    RESPONDER = "RESPONDER", "Responder"
    DISPATCHER = "DISPATCHER", "Dispatcher"
    ADMIN = "ADMIN", "Administrator"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CITIZEN, db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    @property
    def is_ops(self):
        return self.role in (Role.DISPATCHER, Role.ADMIN)

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN

    @property
    def display_name(self):
        return self.get_full_name() or self.email

    def __str__(self):
        return self.display_name

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from utils.base_model import BaseAbstractModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseAbstractModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # SPEC-009 RN-8: se enciende cuando la contraseña la eligió el servidor y la
    # vio el administrador —al crear un colaborador y al regenerársela— y se apaga
    # cuando la persona pone la suya. Vive en `User` y no en el perfil porque la
    # contraseña es del usuario: así también sirve si alguna vez se le entrega una
    # temporal a un administrador.
    must_change_password = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Admin(BaseAbstractModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="admin_profile"
    )
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="admins",
    )

    def __str__(self):
        return f"Admin: {self.user.email}"


class Collaborator(BaseAbstractModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="collaborator_profile"
    )
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="collaborators",
    )

    def __str__(self):
        return f"Collaborator: {self.user.email}"

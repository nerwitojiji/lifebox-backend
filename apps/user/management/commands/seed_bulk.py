"""
Seed masivo de colaboradores para pruebas de escala.

Ejemplo:
  python manage.py seed_bulk --users 50
"""

from __future__ import annotations

import re
from typing import Iterable

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.organization.models import Organization
from apps.user.models import Collaborator, User
from utils.model_factories import create_organization

DEFAULT_PASSWORD = "password123"
USER_EMAIL_RE = re.compile(r"^bulk(\d+)@lifebox\.test$")
BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Crea colaboradores en bulk. "
        f"Password de los usuarios nuevos: {DEFAULT_PASSWORD}"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            required=True,
            metavar="N",
            help="Cantidad de colaboradores nuevos a crear (bulk)",
        )

    def handle(self, *args, **options):
        n_users = options["users"]
        if n_users <= 0:
            raise CommandError("--users debe ser un entero positivo")

        org = create_organization(name="Lifebox Demo")
        self.stdout.write(f"Organización: {org.name} (id={org.id})")

        with transaction.atomic():
            created = self._bulk_create_users(org, n_users)

        self.stdout.write(
            self.style.SUCCESS(
                f"Usuarios/colaboradores creados: {created} "
                f"(password {DEFAULT_PASSWORD})"
            )
        )

    def _next_index(self, values: Iterable[str], pattern: re.Pattern[str]) -> int:
        max_n = 0
        for value in values:
            match = pattern.match(value)
            if match:
                max_n = max(max_n, int(match.group(1)))
        return max_n + 1

    def _bulk_create_users(self, org: Organization, count: int) -> int:
        existing_emails = User.objects.filter(
            email__startswith="bulk",
            email__endswith="@lifebox.test",
        ).values_list("email", flat=True)
        start = self._next_index(existing_emails, USER_EMAIL_RE)
        end = start + count
        now = timezone.now()
        password_hash = make_password(DEFAULT_PASSWORD)

        users = [
            User(
                email=f"bulk{i}@lifebox.test",
                first_name="Bulk",
                last_name=f"User{i}",
                password=password_hash,
                is_active=True,
                is_staff=False,
                is_superuser=False,
                created_at=now,
                updated_at=now,
                show=True,
            )
            for i in range(start, end)
        ]
        created_users = User.objects.bulk_create(users, batch_size=BATCH_SIZE)

        # SQLite/Django 4.2+ asigna PKs en bulk_create; si no, re-fetch por email.
        if created_users and created_users[0].pk is None:
            emails = [u.email for u in users]
            created_users = list(
                User.objects.filter(email__in=emails).only("id", "email")
            )

        collaborators = [
            Collaborator(
                user=user,
                organization=org,
                created_at=now,
                updated_at=now,
                show=True,
            )
            for user in created_users
        ]
        Collaborator.objects.bulk_create(collaborators, batch_size=BATCH_SIZE)

        self.stdout.write(
            f"Rango: bulk{start}@lifebox.test … bulk{end - 1}@lifebox.test"
        )
        return count

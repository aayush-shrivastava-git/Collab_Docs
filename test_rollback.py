
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
from collaboration.models import (
    User,
    Workspace,
    Document,
    DocumentVersion,
    AuditLog,
)

# Use an existing user and workspace.
user = User.objects.first()
workspace = Workspace.objects.first()

if not user or not workspace:
    raise RuntimeError(
        "Create a user and workspace in Postman first."
    )

document_id = None

try:
    with transaction.atomic():
        document = Document.objects.create(
            workspace=workspace,
            title="Rollback Demonstration",
            content="This document must not persist.",
            status=Document.Status.DRAFT,
            created_by=user,
            updated_by=user,
        )

        document_id = document.id

        # The post_save signal should create an audit entry.
        # Create a version in the same transaction as well.
        DocumentVersion.objects.create(
            document=document,
            version_number=document.versions.count() + 1,
            content=document.content,
            saved_by=user,
        )

        # Deliberately fail to trigger a rollback.
        raise RuntimeError("Intentional rollback demonstration")

except RuntimeError as exc:
    print(f"Expected failure: {exc}")

print("Document exists:",
      Document.objects.filter(id=document_id).exists())

print("Versions remaining:",
      DocumentVersion.objects.filter(
          document_id=document_id
      ).count())

print("Audit logs remaining:",
      AuditLog.objects.filter(
          model_name="Document",
          object_id=str(document_id),
      ).count())

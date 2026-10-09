
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AuditLog, Document


@receiver(post_save, sender=Document)
def document_audit_log(sender, instance, created, **kwargs):
    AuditLog.objects.create(
        actor=instance.created_by,
        action=(
            AuditLog.Action.CREATED
            if created
            else AuditLog.Action.UPDATED
        ),
        model_name="Document",
        object_id=str(instance.id),
        details={"title": instance.title},
    )

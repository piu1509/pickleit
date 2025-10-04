
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from django.core import management
from .models import LogEntry
from .middleware import get_current_user

def is_migration_command():
    """Check if the current management command is a migration command."""
    return any(
        command in management.get_commands()
        for command in ['migrate', 'makemigrations', 'sqlmigrate']
    )

@receiver(post_save)
def log_model_changes(sender, instance, created, **kwargs):
    if sender == LogEntry or is_migration_command():
        # Prevent logging the log entries themselves or during migrations
        return

    # Check if the instance has an id attribute
    if not hasattr(instance, 'id'):
        return

    action = 'create' if created else 'update'
    LogEntry.objects.create(
        user=getattr(get_current_user(), 'username', 'Anonymous'),  # Log the username
        action=action,
        model_name=sender.__name__,
        instance_id=instance.id
    )

@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    if sender == LogEntry or is_migration_command():
        # Prevent logging the log entries themselves or during migrations
        return

    # Check if the instance has an id attribute
    if not hasattr(instance, 'id'):
        return

    LogEntry.objects.create(
        user=getattr(get_current_user(), 'username', 'Anonymous'),  # Log the username
        action='delete',
        model_name=sender.__name__,
        instance_id=instance.id
    )


import logging

logger = logging.getLogger('apps.user')

def log_model_save(sender, instance, created, **kwargs):
    if created:
        logger.info(f'Created instance of {sender.__name__} with ID {instance.id}')
    else:
        logger.info(f'Updated instance of {sender.__name__} with ID {instance.id}')

def log_model_delete(sender, instance, **kwargs):
    logger.info(f'Deleted instance of {sender.__name__} with ID {instance.id}')

# # Register signals for all models in the app
def register_signals_for_app(app_name):
    app_models = apps.get_app_config(app_name).get_models()
    for model in app_models:
        if not any([h.__class__ == log_model_save for h in model._meta.signals['post_save'].handlers]):
            post_save.connect(log_model_save, sender=model)
        if not any([h.__class__ == log_model_delete for h in model._meta.signals['post_delete'].handlers]):
            post_delete.connect(log_model_delete, sender=model)


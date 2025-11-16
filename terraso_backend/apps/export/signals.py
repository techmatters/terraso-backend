# Copyright © 2021-2025 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.project_management.models import Project, Site

from .models import ExportToken

User = get_user_model()


@receiver(post_save, sender=User)
def delete_user_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when user is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.
    """
    if instance.deleted_at is not None:
        # User was soft-deleted, delete their export tokens
        ExportToken.objects.filter(
            resource_type="USER", resource_id=str(instance.id)
        ).delete()

        # Also clear the export_token field from the user
        if instance.export_token:
            instance.export_token = None
            # Use update to avoid triggering the signal again
            User.objects.filter(pk=instance.pk).update(export_token=None)


@receiver(post_save, sender=Project)
def delete_project_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when project is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.
    """
    if instance.deleted_at is not None:
        # Project was soft-deleted, delete its export tokens
        ExportToken.objects.filter(
            resource_type="PROJECT", resource_id=str(instance.id)
        ).delete()

        # Also clear the export_token field from the project
        if instance.export_token:
            instance.export_token = None
            # Use update to avoid triggering the signal again
            Project.objects.filter(pk=instance.pk).update(export_token=None)


@receiver(post_save, sender=Site)
def delete_site_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when site is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.
    """
    if instance.deleted_at is not None:
        # Site was soft-deleted, delete its export tokens
        ExportToken.objects.filter(
            resource_type="SITE", resource_id=str(instance.id)
        ).delete()

        # Also clear the export_token field from the site
        if instance.export_token:
            instance.export_token = None
            # Use update to avoid triggering the signal again
            Site.objects.filter(pk=instance.pk).update(export_token=None)

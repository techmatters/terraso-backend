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

from apps.collaboration.models import Membership
from apps.project_management.models import Project, Site

from .models import ExportToken

User = get_user_model()


@receiver(post_save, sender=User)
def delete_user_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when user is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.

    This deletes:
    - All tokens created BY this user (user_id matches)
    - All tokens FOR this user as a resource (resource_type=USER)
    """
    if instance.deleted_at is not None:
        # Delete all tokens created by this user
        ExportToken.objects.filter(user_id=str(instance.id)).delete()

        # Also delete tokens for this user as a resource
        ExportToken.objects.filter(resource_type="USER", resource_id=str(instance.id)).delete()


@receiver(post_save, sender=Project)
def delete_project_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when project is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.

    This deletes all tokens for this project (from any user).
    """
    if instance.deleted_at is not None:
        # Delete all tokens for this project (any user)
        ExportToken.objects.filter(resource_type="PROJECT", resource_id=str(instance.id)).delete()


@receiver(post_save, sender=Site)
def delete_site_export_tokens_on_soft_delete(sender, instance, **kwargs):
    """
    Delete export tokens when site is soft-deleted.
    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.

    This deletes all tokens for this site (from any user).
    """
    if instance.deleted_at is not None:
        # Delete all tokens for this site (any user)
        ExportToken.objects.filter(resource_type="SITE", resource_id=str(instance.id)).delete()


@receiver(post_save, sender=Membership)
def delete_export_tokens_on_membership_removal(sender, instance, **kwargs):
    """
    Delete export tokens when user is removed from a project.
    This includes tokens for the project itself and all sites in the project.

    SafeDeleteModel doesn't trigger post_delete, so we use post_save
    and check if deleted_at is set.

    Note: MembershipList can be associated with projects, groups, landscapes,
    or story maps. We only care about project memberships for export tokens.
    """
    if instance.deleted_at is None:
        return

    # Safely get project - membership_list may be for groups, landscapes, etc.
    project = getattr(instance.membership_list, "project", None)
    if project is None:
        return

    user_id = str(instance.user.id)

    # Delete user's token for this project
    ExportToken.objects.filter(
        user_id=user_id,
        resource_type="PROJECT",
        resource_id=str(project.id),
    ).delete()

    # Delete user's tokens for all sites in this project
    site_ids = project.sites.values_list("id", flat=True)
    ExportToken.objects.filter(
        user_id=user_id,
        resource_type="SITE",
        resource_id__in=[str(sid) for sid in site_ids],
    ).delete()

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, Group, User
from apps.shared_data import permission_rules as perm_rules
from apps.shared_data.services import DataEntryFileStorage


class DataEntry(BaseModel):
    """
    Data Entry stores information about resources (usually files) that contain
    different kind of data used by Landscape managers. Common resource types are
    csv, xls and JSON files.

    A Data Entry can point to internal or external resources. An internal
    resource is stored on Terraso's infrastructure and an external resource is
    stored out of the Terraso's infrastructure. In both cases, the Data Entry
    only has the URL for that resource as a link to it.

    Attributes
    ----------
    name: str
        any user given name for that resource
    description: str
        a longer description explaining the resource
    resource_type: str
        the 'technical' type of the resource, usually the mime type
    url: str
        the URL where the resource can be accessed

    groups: ManyToManyField(Group)
        Groups where the resource is linked to (shared)
    created_by: User
        User who created the resource
    """

    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")

    ENTRY_TYPE_FILE = "file"
    ENTRY_TYPE_LINK = "link"
    MEMBERSHIP_TYPES = (
        (ENTRY_TYPE_FILE, _("File")),
        (ENTRY_TYPE_LINK, _("Link")),
    )
    entry_type = models.CharField(
        max_length=32,
        choices=MEMBERSHIP_TYPES,
    )

    resource_type = models.CharField(max_length=255)
    url = models.URLField()
    size = models.PositiveBigIntegerField(null=True)

    groups = models.ManyToManyField(Group, related_name="data_entries")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    file_removed_at = models.DateTimeField(blank=True, null=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = "Data Entries"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_data_entry,
            "delete": perm_rules.allowed_to_delete_data_entry,
            "view": perm_rules.allowed_to_view_data_entry,
        }

    @property
    def s3_object_name(self):
        object_name = "/".join(self.url.split("/")[-2:]) if self.url else ""

        # We want to put back the space character so the sign url works properly
        object_name = object_name.replace("%20", " ")
        return object_name

    @property
    def signed_url(self):
        storage = DataEntryFileStorage(custom_domain=None)
        return storage.url(self.s3_object_name)

    def delete_file_on_storage(self):
        if not self.deleted_at:
            raise RuntimeError(
                f"Storage object cannot be deleted if its DataEntry ({self.id}) is not deleted."
            )

        if self.file_removed_at:
            return

        storage = DataEntryFileStorage(custom_domain=None)
        storage.delete(self.s3_object_name)
        self.file_removed_at = timezone.now()
        self.save(keep_deleted=True)

    def to_dict(self):
        return dict(
            id=str(self.id),
            name=self.name,
            description=self.description,
            url=self.signed_url,
            resource_type=self.resource_type,
            size=self.size,
            created_by=str(self.created_by.id),
            groups=[str(group.id) for group in self.groups.all()],
        )

    def __str__(self):
        return self.name

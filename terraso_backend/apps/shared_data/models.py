from django.db import models

from apps.core.models import Group, SlugModel, User
from apps.shared_data import permission_rules as perm_rules
from apps.shared_data.services import DataEntryFileStorage


class DataEntry(SlugModel):
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

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True, default="")
    resource_type = models.CharField(max_length=255)
    url = models.URLField()
    size = models.PositiveBigIntegerField(null=True)

    groups = models.ManyToManyField(Group, related_name="data_entries")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        verbose_name_plural = "Data Entries"
        rules_permissions = {
            "change": perm_rules.allowed_to_change_data_entry,
            "delete": perm_rules.allowed_to_delete_data_entry,
            "view": perm_rules.allowed_to_view_data_entry,
        }

    @property
    def s3_object_name(self):
        return "/".join(self.url.split("/")[-2:]) if self.url else ""

    @property
    def signed_url(self):
        storage = DataEntryFileStorage(custom_domain=None)
        return storage.url(self.s3_object_name)

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

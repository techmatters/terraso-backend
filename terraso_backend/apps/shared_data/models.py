from django.db import models

from apps.core.models import Group, SlugModel, User
from apps.shared_data import permission_rules as perm_rules


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

    groups = models.ManyToManyField(Group)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    field_to_slug = "name"

    class Meta(SlugModel.Meta):
        rules_permissions = {
            "change": perm_rules.allowed_to_change_data_entry,
            "delete": perm_rules.allowed_to_delete_data_entry,
        }

    def __str__(self):
        return self.name

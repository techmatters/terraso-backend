from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.
CREATE = 1
READ = 2
CHANGE = 3
DELETE = 4

EVENT_CHOICES = (
    (CREATE, _("CREATE")),
    (READ, _("READ")),
    (CHANGE, _("CHANGE")),
    (DELETE, _("DELETE")),
)


class Log(models.Model):
    """
    Log model for audits logs
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    client_timestamp = models.DateTimeField()
    # TODO - Discuss: if we should delete on cascade or not
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='user'
    )
    resource_id = models.TextField()
    event = models.PositiveSmallIntegerField(_('event'), choices=EVENT_CHOICES)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        verbose_name='content type',
        blank=True,
        null=True
    )
    resource_json_repr = models.JSONField()

    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return str(self.client_timestamp) + " - " + str(self.metadata)

    def get_string(self, template: str = None) -> str:
        if template is None:
            return str(self)
        return template.format(**self.metadata)

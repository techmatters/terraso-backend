from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.
CREATE = 1
READ = 2
CHANGE = 3
DELETION = 4

EVENT_CHOICES = (
    (CREATE, _("Addition")),
    (READ, _("Read")),
    (CHANGE, _("Change")),
    (DELETION, _("Deletion")),
)


class Log(models.Model):
    """
    Log model for audits logs
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    keyValueCache = models.JSONField()
    client_timestamp = models.DateTimeField()
    # TODO - Discuss: if we should delete on cascade or not
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name='user')
    resource_id = models.TextField(blank=True, null=True)
    event = models.PositiveSmallIntegerField(_('event'), choices=EVENT_CHOICES)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        verbose_name='content type',
        blank=True,
        null=True
    )
    resource_repr = models.CharField(max_length=250)

    metadataCache = models.JSONField(blank=True, null=True)

    def __str__(self):
        return str(self.client_timestamp) + " - " + self.keyValueCache

    def get_string(self, template: str = None) -> str:
        if template is None:
            return str(self)
        return template.format(**self.keyValueCache)


# TODO - Discuss: if we should just store string for the the log resource or
# foreing keys if we store foreing key they will have to be generic keys
class KeyValue(models.Model):
    """
    Key Value model for audits logs
    """
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)
    log = models.ForeignKey(Log, on_delete=models.CASCADE)

    def __str__(self):
        return self.key + ' - ' + self.value


class AuditLog(models.Model):
    """
    Audit Log model for audits
    Note: This model is not used in the current implementation but is the alternative
    to the KeyValue model and has the same asumption as the KeyValue model that stores
    the references as strings and not as foreing keys
    """
    user = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    resource = models.CharField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user + ' - ' + self.action + ' - ' + self.description

from django.db import models


# Create your models here.
class Log(models.Model):
    """
    Log model for audits logs
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    keyValueCache = models.JSONField()
    client_timestamp = models.DateTimeField()

    def __str__(self):
        return self.user + ' - ' + self.action + ' - ' + self.description


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

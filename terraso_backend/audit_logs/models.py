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


class KeyValue(models.Model):
    """
    Key Value model for audits logs
    """
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)
    value_type = models.CharField(max_length=100)
    value_ref = models.CharField(max_length=100)
    value_ref_type = models.CharField(max_length=100)
    log = models.ForeignKey(Log, on_delete=models.CASCADE)

    def __str__(self):
        return self.key + ' - ' + self.value


class AuditLog(models.Model):
    """
    Audit Log model for audits
    """
    user = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user + ' - ' + self.action + ' - ' + self.description

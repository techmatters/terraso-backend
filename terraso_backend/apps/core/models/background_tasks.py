from django.db import models

from .users import User


class BackgroundTask(models.Model):
    StatusType = models.TextChoices("StatusType", "finished failed running")
    status = models.CharField(max_length=10, choices=StatusType.choices)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

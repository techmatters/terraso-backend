from django.conf import settings


def backup_allowed(request):
    return {"allow_restore": settings.ALLOW_RESTORE_FROM_BACKUP}

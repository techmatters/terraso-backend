from django.conf import settings


def restore_allowed(request):
    return {"allow_restore": settings.ALLOW_RESTORE_FROM_BACKUP}

from django.db import DatabaseError
from django.http import HttpResponse
from django.views import View

from apps.core.models import Group, Landscape, User


class HealthView(View):
    def get(self, request, *args, **kwargs):
        try:
            check_db_access()
        except DatabaseError:
            return HttpResponse("Database error fetching DB resources", status=400)
        except Exception:
            return HttpResponse("Unexpected error fetching DB resources", status=400)

        return HttpResponse("OK", status=200)


def check_db_access():
    # During the health check we try to do a minor DB access to make sure
    # main tables can be reached
    Landscape.objects.count()
    Group.objects.count()
    User.objects.count()

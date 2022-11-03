import json
import random

from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseNotAllowed
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


@staff_member_required
def create_restore_job(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    return HttpResponse(json.dumps({"taskId": 1}), "application/json")


@staff_member_required
def check_restore_job_status(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    status = "running" if random.random() > 0.4 else "done"
    return HttpResponse(json.dumps({"status": status}), "application/json")

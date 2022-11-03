import json
import threading
import time

import structlog
from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError, transaction
from django.db.transaction import get_connection
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound
from django.views import View

from apps.core.models import BackgroundTask, Group, Landscape, User

logger = structlog.get_logger(__name__)


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
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    with transaction.atomic():
        cursor = get_connection().cursor()
        cursor.execute(f"LOCK TABLE {BackgroundTask._meta.db_table}")
        task = BackgroundTask(created_by=request.user, status="running")
        try:
            active_tasks = BackgroundTask.objects.filter(status="running").count()
            if active_tasks:
                return HttpResponse(
                    json.dumps({"message": "Already a restore task running"}),
                    "application/json",
                    400,
                )
            task.save()
        except Exception:
            task.delete()
        finally:
            cursor.close()
        thread = threading.Thread(target=restore, args=[task], daemon=True)
        thread.start()

    return HttpResponse(json.dumps({"taskId": task.id}), "application/json")


@staff_member_required
def check_restore_job_status(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(permitted_methods=["GET"])
    try:
        task = BackgroundTask.objects.get(id=task_id)
    except BackgroundTask.DoesNotExist:
        return HttpResponseNotFound(
            json.dumps({"message": f"No task with id {task_id}"}), "application/json"
        )
    return HttpResponse(json.dumps({"status": task.status}), "application/json")


def restore(task):
    try:
        time.sleep(15)
    except Exception:
        logger.exception("Job failed!")
        print("FAILURE")
        task.status = "failed"
    else:
        task.status = "finished"
    finally:
        task.save()

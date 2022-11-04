import configparser
import json
import subprocess
import threading
import time
from pathlib import Path

import httpx
import structlog
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core import management
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


def _sync_s3_buckets(
    source_buckets: list[str], dest_buckets: list[str], aws_credentials: tuple[str, str, str]
):
    """Sync contents of source_buckets to dest_buckets."""
    env = {
        key: value
        for key, value in zip(
            ["AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"], aws_credentials
        )
    }
    for source, dest in zip(source_buckets, dest_buckets):
        subprocess.run(["aws", "s3", source, dest], env=env)


JOB_WAIT_TIME_SEC = 5


def _backup_service(service_name: str, render_token: str, start_command: str):
    """Send request to source service to trigger backup and wait for completion."""
    jobs_resource = "{settings.RENDER_API_URL}/services/{service_name}/jobs"
    headers = {"authorization": "Bearer {render_token}"}
    resp = httpx.post(jobs_resource, headers=headers, json={"startCommand": start_command})
    resp.raise_for_status()
    resp_json = resp.json()
    job_id = resp_json["id"]
    status = None
    while not status:
        time.sleep(JOB_WAIT_TIME_SEC)
        status_resp = httpx.get(f"{jobs_resource}/{job_id}", headers)
        status_resp.raise_for_status()
        status_resp_json = status_resp.json()
        status = status_resp_json["status"]
        if status == "failed":
            raise RuntimeError(f"Render job failed: {status['message']}")


def _restore_from_backup():
    management.command("loadbackup", "--s3")


def _load_config_file(path: Path) -> tuple[list[str], list[str], str]:
    config = configparser.ConfigParser()
    config.read(path)
    source_buckets = []
    dest_buckets = []
    for key in config.sections():
        block = config[key]
        source_buckets.append(block["source_bucket"])
        dest_buckets.append(block["dest_bucket"])
    return source_buckets, dest_buckets, config["service_name"]


def restore(task):
    """Restore current instance from source instance."""
    try:
        source_buckets, dest_buckets, service_name = _load_config_file(
            Path(settings.DB_RESTORE_CONFIG_FILE)
        )
        aws_credentials = (
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_S3_REGION_NAME,
        )
        _sync_s3_buckets(source_buckets, dest_buckets, aws_credentials)
        _backup_service(
            service_name, settings.RENDER_API_URL, "python3 terraso_backend/manage.py backup --s3"
        )
        _restore_from_backup()
    except Exception:
        logger.exception("Job failed!")
        task.status = "failed"
    else:
        task.status = "finished"
    finally:
        task.save()

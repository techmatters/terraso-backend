# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import json
import os
import subprocess
import threading
import time

import httpx
import structlog
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sessions.models import Session
from django.core import management
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.transaction import get_connection
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    JsonResponse,
)
from django.views import View
from django.views.generic.edit import FormView

from apps.auth.mixins import AuthenticationRequiredMixin
from apps.core.gis.parsers import parse_file_to_geojson
from apps.core.models import BackgroundTask, Group, Landscape, User

logger = structlog.get_logger(__name__)

RENDER_STATUS_JOB_CHECK_DELAY_SEC = 5


class ParseGeoFileView(AuthenticationRequiredMixin, FormView):
    def post(self, request, **kwargs):
        file = request.FILES.get("file")

        try:
            geojson = parse_file_to_geojson(file)
        except ValidationError as error:
            return JsonResponse(
                {"errors": [{"message": json.dumps([{"code": error.message}])}]}, status=400
            )

        return JsonResponse({"geojson": geojson})


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
        thread = threading.Thread(
            target=restore, args=[task, request.user.id, request.session.session_key], daemon=True
        )
        thread.start()

    return HttpResponse(json.dumps({"taskId": task.id}), "application/json")


def check_restore_job_status(request, task_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(permitted_methods=["GET"])
    try:
        task = BackgroundTask.objects.get(id=task_id)
        session = Session.objects.get(session_key=request.session.session_key)
        session_user_id = session.get_decoded().get("_auth_user_id")
        if session_user_id != str(task.created_by_id):
            return HttpResponseNotFound(json.dumps({"message": "Restricted"}), "application/json")
    except BackgroundTask.DoesNotExist | Session.DoesNotExist:
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
    env.update(os.environ)
    for source, dest in zip(source_buckets, dest_buckets):
        subprocess.run(["aws", "s3", "sync", "s3://" + source, "s3://" + dest], env=env)


def _backup_service(service_name: str, render_token: str, start_command: str):
    """Send request to source service to trigger backup and wait for completion."""
    jobs_resource = f"{settings.RENDER_API_URL}services/{service_name}/jobs"
    headers = {"authorization": f"Bearer {render_token}"}
    resp = httpx.post(jobs_resource, headers=headers, json={"startCommand": start_command})
    resp.raise_for_status()
    resp_json = resp.json()
    job_id = resp_json["id"]
    status = None
    while not status:
        time.sleep(RENDER_STATUS_JOB_CHECK_DELAY_SEC)
        status_resp = httpx.get(f"{jobs_resource}/{job_id}", headers=headers)
        status_resp.raise_for_status()
        status_resp_json = status_resp.json()
        status = status_resp_json["status"]
        if status == "failed":
            raise RuntimeError(f"Render job failed: {status['message']}")


def _restore_from_backup(user_id, session_id):
    management.call_command("loadbackup", s3=True, save_user=user_id, save_session=session_id)


def _load_config() -> tuple[list[str], list[str], str]:
    service = settings.DB_RESTORE_SOURCE_ID
    source_buckets = []
    dest_buckets = []
    for bucket in ("files", "images"):
        source_bucket = bucket + "." + settings.DB_RESTORE_SOURCE_HOST
        dest_bucket = bucket + "." + settings.DB_RESTORE_DEST_HOST
        source_buckets.append(source_bucket)
        dest_buckets.append(dest_bucket)
    return source_buckets, dest_buckets, service


def restore(task, user_id, session_id):
    """Restore current instance from source instance."""
    try:
        source_buckets, dest_buckets, service_name = _load_config()
        aws_credentials = (
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_S3_REGION_NAME,
        )
        _sync_s3_buckets(source_buckets, dest_buckets, aws_credentials)
        _backup_service(
            service_name, settings.RENDER_API_TOKEN, "python3 terraso_backend/manage.py backup --s3"
        )
        _restore_from_backup(user_id, session_id)
    except Exception:
        logger.exception(f"Background task {task.id} for {user_id} failed! Logging exception trace")
        task.status = "failed"
    else:
        task.status = "finished"
    finally:
        task.save()

# from apps.graphql.schema.schema.schema import schema
from apps.graphql.schema.schema import schema
from django.contrib.auth import get_user_model

def simple_report(request):
    """Generate a simple report of the number of users, landscapes, groups, and data entries."""

    # logger.info("request is for simple report", request)
    format = request.GET.get("format", "json")

    # if request.method != "GET":
    #    return HttpResponseNotAllowed(permitted_methods=["GET"])

    # User = get_user_model()
    # service_user = User.objects.get(email="johannes@schmidtparty.com")
    # request.user = service_user



    gql = """
    query FindUser($emailPart: String!) {
        users(email_Icontains: $emailPart, first: 100, email: null) {
            edges {
                node {
                    id
                    email
                }
            }
            totalCount
        }
        # projects {
        #     edges {
        #         node {
        #             id
        #             name
        #         }
        #     }
        #     totalCount
        # }
        project(id: "90f32c23-3dfb-4c31-80c3-27dca6ef1cc3") {
            name
            description
            updatedAt
            siteSet {
                totalCount
                edges {
                    cursor
                    node {
                        name
                        latitude
                        longitude
                        elevation
                        updatedAt
                        privacy
                        archived
                        id
                        seen
                        notes {
                            totalCount
                            edges {
                                node {
                                    deletedAt
                                    deletedByCascade
                                    id
                                    content
                                    createdAt
                                    updatedAt
                                }
                            }
                        }
                        soilData {
                            downSlope
                            crossSlope
                            bedrock
                            slopeLandscapePosition
                            slopeAspect
                            slopeSteepnessSelect
                            slopeSteepnessPercent
                            slopeSteepnessDegree
                            surfaceCracksSelect
                            surfaceSaltSelect
                            floodingSelect
                            limeRequirementsSelect
                            surfaceStoninessSelect
                            waterTableDepthSelect
                            soilDepthSelect
                            landCoverSelect
                            grazingSelect
                            depthIntervalPreset
                            depthIntervals {
                                label
                                soilTextureEnabled
                                soilColorEnabled
                                soilStructureEnabled
                                carbonatesEnabled
                                phEnabled
                                soilOrganicCarbonMatterEnabled
                                electricalConductivityEnabled
                                sodiumAdsorptionRatioEnabled
                                depthInterval {
                                    start
                                    end
                                }
                            }
                            depthDependentData {
                                texture
                                clayPercent
                                rockFragmentVolume
                                colorHue
                                colorValue
                                colorChroma
                                colorPhotoUsed
                                colorPhotoSoilCondition
                                colorPhotoLightingCondition
                                conductivity
                                conductivityTest
                                conductivityUnit
                                structure
                                ph
                                phTestingSolution
                                phTestingMethod
                                soilOrganicCarbon
                                soilOrganicMatter
                                soilOrganicCarbonTesting
                                soilOrganicMatterTesting
                                sodiumAbsorptionRatio
                                carbonates
                            }
                        }
                    }
                }
            }
        }
    }
    """

    result = schema.execute(
        gql,
        variable_values={"emailPart": "johannes"},
        context_value=request,   # lets resolvers see request if they need it
    )

    if result.errors:
        # Keep it simple for now; you can improve error formatting later.
        return JsonResponse(
            {"ok": False, "errors": [str(e) for e in result.errors]},
            status=400,
        )

    # result.data is already plain Python dicts/lists/scalars
    return JsonResponse({"ok": True, "data": result.data})

    # report = { "test": "johannes", "num_users": 42, "num_landscapes": 7, "num_groups": 3, "num_data_entries": 128, "format": format }
    # response = JsonResponse(report)
    # response["Content-Disposition"] = 'attachment; filename="simple_report.json"'
    # return response
    # return HttpResponse("<h1>this is a test</h1")

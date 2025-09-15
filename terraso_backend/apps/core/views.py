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
# from django.contrib.auth import get_user_model

def fetch_all_notes_for_site(site_id, request, page_size=200):
    after = None
    notes = []
    gql = """
    query SiteNotes($id: ID!, $first: Int!, $after: String) {
      site(id: $id) {
        notes(first: $first, after: $after) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id
              content
              createdAt
              updatedAt
              deletedAt
              deletedByCascade
              author {
                id
                email
                firstName
                lastName
                profileImage
              }
            }
          }
        }
      }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"id": site_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors: raise RuntimeError(res.errors)
        conn = res.data["site"]["notes"]
        notes.extend(e["node"] for e in conn["edges"])
        if not conn["pageInfo"]["hasNextPage"]:
            return notes
        after = conn["pageInfo"]["endCursor"]

# todo: is this data available somewhere else?
depth_intervals_nrcs_gsp = [
    { "label": "0-5 cm", "depthInterval": { "start": 0, "end": 5 },  "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "5-15 cm", "depthInterval": { "start": 5, "end": 15 }, "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "15-30 cm", "depthInterval": { "start": 15, "end": 30 }, "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "30-60 cm", "depthInterval": { "start": 30, "end": 60 }, "soilTextureEnabled": False, "soilColorEnabled": False, "soilStructureEnabled": False, "carbonatesEnabled": False, "phEnabled": False, "soilOrganicCarbonMatterEnabled": False, "electricalConductivityEnabled": False, "sodiumAdsorptionRatioEnabled": False },
    { "label": "60-100 cm",   "depthInterval": { "start": 60, "end": 100 },"soilTextureEnabled": False, "soilColorEnabled": False, "soilStructureEnabled": False, "carbonatesEnabled": False, "phEnabled": False, "soilOrganicCarbonMatterEnabled": False,  "electricalConductivityEnabled": False,"sodiumAdsorptionRatioEnabled": False },
    { "label": "100-200 cm",   "depthInterval": { "start": 100, "end": 200 },"soilTextureEnabled": False, "soilColorEnabled": False, "soilStructureEnabled": False, "carbonatesEnabled": False, "phEnabled": False, "soilOrganicCarbonMatterEnabled": False,  "electricalConductivityEnabled": False,"sodiumAdsorptionRatioEnabled": False }
]

depth_intervals_blm = [
    { "label": "0-1 cm", "depthInterval": { "start": 0, "end": 1 },  "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "1-10 cm", "depthInterval": { "start": 1, "end": 10 }, "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "10-20 cm", "depthInterval": { "start": 10, "end": 20 }, "soilTextureEnabled": True, "soilColorEnabled": True, "soilStructureEnabled": True, "carbonatesEnabled": True, "phEnabled": True, "soilOrganicCarbonMatterEnabled": True, "electricalConductivityEnabled": True, "sodiumAdsorptionRatioEnabled": True },
    { "label": "20-50 cm", "depthInterval": { "start": 20, "end":50 }, "soilTextureEnabled": False, "soilColorEnabled": False, "soilStructureEnabled": False, "carbonatesEnabled": False, "phEnabled": False, "soilOrganicCarbonMatterEnabled": False, "electricalConductivityEnabled": False, "sodiumAdsorptionRatioEnabled": False },
    { "label": "50-70 cm",   "depthInterval": { "start": 50, "end": 70 },"soilTextureEnabled": False, "soilColorEnabled": False, "soilStructureEnabled": False, "carbonatesEnabled": False, "phEnabled": False, "soilOrganicCarbonMatterEnabled": False,  "electricalConductivityEnabled": False,"sodiumAdsorptionRatioEnabled": False },
]

def add_default_depth_intervals(soil_data):
    match soil_data["depthIntervalPreset"]:
        case "NRCS":
            soil_data["depthIntervals"] = depth_intervals_nrcs_gsp

        case "BLM":
            soil_data["depthIntervals"] = depth_intervals_blm


def add_munsell_color_strings(depth_dependent_data):
    for d in depth_dependent_data:
        d["colorMunsell"] = munsell_to_string(d)


def hide_site_id(site):
    site["id"] = "hide id?"

# from terraso-mobile-client, en.json
rock_fragment_volume = {
    "VOLUME_0_1": "0–1%",
    "VOLUME_1_15": "1–15%",
    "VOLUME_15_35": "15–35%",
    "VOLUME_35_60": "35–60%",
    "VOLUME_60": ">60%"
}

def replace_rock_fragment_volume_strings(depth_dependent_data):
    for d in depth_dependent_data:
        if d.get("rockFragmentVolume"):
            d["rockFragmentVolume"] = rock_fragment_volume.get(d.get("rockFragmentVolume"), d.get("rockFragmentVolume"))


# from terraso-mobile-client, en.json
soil_texture = {
    "CLAY": "Clay",
    "CLAY_LOAM": "Clay Loam",
    "LOAM": "Loam",
    "LOAMY_SAND": "Loamy Sand",
    "SAND": "Sand",
    "SANDY_CLAY": "Sandy Clay",
    "SANDY_CLAY_LOAM": "Sandy Clay Loam",
    "SANDY_LOAM": "Sandy Loam",
    "SILT": "Silt",
    "SILTY_CLAY": "Silty Clay",
    "SILTY_CLAY_LOAM": "Silty Clay Loam",
    "SILT_LOAM": "Silt Loam"
}

def replace_soil_texture_strings(depth_dependent_data):
    for d in depth_dependent_data:
        if d.get("texture"):
            d["texture"] = soil_texture.get(d.get("texture"), d.get("texture"))

# from terraso-mobile-client, en.json
vertical_cracking = {
    "NO_CRACKING": "No cracks",
    "SURFACE_CRACKING_ONLY": "Surface cracks only",
    "DEEP_VERTICAL_CRACKS": "Deep vertical cracks"
}

def replace_surface_cracking_strings(soil_data):
    if soil_data.get("surfaceCracksSelect"):
        soil_data["surfaceCracksSelect"] = vertical_cracking.get(soil_data.get("surfaceCracksSelect"), soil_data.get("surfaceCracksSelect"))


# alternative implementation using the enum from models
# from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
# def replace_rock_fragment_volume_strings(depth_dependent_data):
#     for d in depth_dependent_data:
#         if d.get("rockFragmentVolume"):
#             try:
#                 d["rockFragmentVolume"] = DepthDependentSoilData.RockFragmentVolume(d.get("rockFragmentVolume")).label
#             except ValueError:
#                 pass

# page_size is for notes pagination
def fetch_site_data(site_id, request, page_size=50):
    gql = """
    query SiteWithNotes($id: ID!) {
        site(id: $id) {
            id
            name
            latitude
            longitude
            elevation
            updatedAt
            privacy
            archived
            seen
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
            soilMetadata {
               selectedSoilId
            }
            project {
                id
                name
                description
            }
        }
    }
    """



    res = schema.execute(
        gql,
        variable_values={"id": site_id},
        context_value=request,
    )
    if res.errors:
        raise RuntimeError(res.errors)
    
    # reshape the data a bit
    add_default_depth_intervals(res.data["site"]["soilData"])
    add_munsell_color_strings(res.data["site"]["soilData"].get("depthDependentData", []))
    hide_site_id(res.data["site"])
    replace_rock_fragment_volume_strings(res.data["site"]["soilData"].get("depthDependentData", []))
    replace_soil_texture_strings(res.data["site"]["soilData"].get("depthDependentData", []))
    replace_surface_cracking_strings(res.data["site"]["soilData"])

    n = fetch_all_notes_for_site(site_id, request, 1)
    res.data["site"]["notes"] = n

    return res.data["site"] 


def fetch_project_list(user_id, request, page_size=50):
    all_projects = []
    after = None
    gql = """
    query Projects($member: ID!, $first: Int!, $after: String) {
      projects(member: $member, first: $first, after: $after) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"member": user_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["projects"]
        batch = [e["node"] for e in conn["edges"]]
        all_projects.extend(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return all_projects

def fetch_all_sites(project_id, request, page_size=50):
    all_sites = []
    after = None
    gql = """
    query ProjectWithSites($id: ID!, $first: Int!, $after: String) {
        sites(project: $id, first: $first, after: $after) {
            pageInfo { hasNextPage endCursor }
            edges { 
                cursor
                node {
                    id
                    name
                }
            }
        }
    }
    """
    while True:
        res = schema.execute(
            gql,
            variable_values={"id": project_id, "first": page_size, "after": after},
            context_value=request,
        )
        if res.errors:
            raise RuntimeError(res.errors)
        conn = res.data["sites"]
        batch = [e["node"] for e in conn["edges"]]
        all_sites.extend(batch)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return all_sites

def flatten_note(note):
    return ",".join([ note["content"], note["author"]["email"], note["createdAt"] ])
    # return ",".join([ "abc", "def", "ghi" ])
    # return ",".join(note["content"], note["createdAt"], note["author"]["email"] if note.get("author") else None    )

# returns n rows of flattened data, one per depth interval
def flatten_site(site: dict) -> dict:
    soilData = site.get("soilData", {})
    notes = site.get("notes")
    rows = [];

    flattened_notes = [flatten_note(note) for note in notes] if notes else []

    for depth_interval, depth_dependent_data in zip(soilData.get("depthIntervals", []), soilData.get("depthDependentData", [])):

        flat = {
            "id": site["id"],
            "name": site["name"],
            "projectName": site["project"]["name"],
            "latitude": site["latitude"],
            "longitude": site["longitude"],
            "elevation": site["elevation"],
            "updatedAt": site["updatedAt"],
            # "privacy": site["privacy"],
            # "archived": site["archived"],
            # "seen": site["seen"],
            "slopeSteepnessDegree": soilData.get("slopeSteepnessDegree"),
            "downSlope": soilData.get("downSlope"),
            "surfaceCracksSelect": soilData.get("surfaceCracksSelect"),
            "notes": ";".join(flattened_notes),
            "user-selected-soil": site.get("soilMetadata", {}).get("selectedSoilId"),

            # depth interval specific data
            "depth-label": depth_interval.get("label"),
            "depth-start": depth_interval.get("depthInterval").get("start"),
            "depth-end": depth_interval.get("depthInterval").get("end"),
            "depth-rockFragmentVolume": depth_dependent_data.get("rockFragmentVolume"),
            "depth-texture": depth_dependent_data.get("texture"),
            "depth-color": depth_dependent_data.get("colorMunsell"), # added earlier
        }
        rows.append(flat)
        
    return rows


def download_convert_to_csv(sites):
    from io import StringIO
    import csv

    flattened_sites = []
    for site in sites:
        flattened_sites.extend(flatten_site(site))

    fieldnames = list(flattened_sites[0].keys()) if flattened_sites else []
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flattened_sites)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()

from django.contrib.auth import get_user_model

def simple_report(request):

    format = request.GET.get("format", "csv")
    # project_id = request.GET.get("project_id", "90f32c23-3dfb-4c31-80c3-27dca6ef1cc3") # johannes local
    project_id = request.GET.get("project_id", "860ec581-3bdb-4846-a149-222d7991e866") # derek server
    # user_id = request.GET.get("user_id", "4f2301b4-208f-45f9-98e1-7bac2610c231") # johannes local
    user_id = request.GET.get("user_id", "f8953ff0-6398-49b0-a246-92568fc7d804") # derek server

    
    # getting list of projects for a user requires authentication

    User = get_user_model()
    service_user = User.objects.get(email="derek@techmatters.org")
    request.user = service_user

    # projects = fetch_project_list(user_id, request, 50) # local johannes
    # return JsonResponse({"projects": projects})

    s = fetch_all_sites(project_id, request, 1)
    # return JsonResponse({'allsites': s})

    bogale = [
         { "id": "bc549dd6-d5f5-47a2-bdf9-3d6914fc053d" }, # Bogale 1
         { "id": "b1f66a85-1824-48d9-a97f-ecee323f9588" }, # Bogale 2
         { "id": "7bd4220a-37ca-47d7-ae3b-f81f46637739" }, # Bogale 3
         { "id": "4c8ee3e8-2bca-412b-8384-568c0d0f9f53" }, # Bogale 4
     ]

    # test = [site["id"] for site in s]
    # return JsonResponse({'test': test})
    all_sites = [fetch_site_data(site["id"], request, 1) for site in s]
    # all_sites = [fetch_site_data("a72dad3b-36aa-4250-b08c-b203f1930836", request, 50)]

    if format == "json":
        return JsonResponse({ "sites": all_sites })
    return HttpResponse(download_convert_to_csv(all_sites), content_type='text/csv')

    # report = { "test": "johannes", "num_users": 42, "num_landscapes": 7, "num_groups": 3, "num_data_entries": 128, "format": format }
    # response = JsonResponse(report)
    # response["Content-Disposition"] = 'attachment; filename="simple_report.json"'
    # return response
    # return HttpResponse("<h1>this is a test</h1")


### Munsell Stuff; initially AI generated using ccolorConversions.ts; numerous edits
# algorithm: terraso-mobile-client/dev-client/src/model/color/colorConversions.ts
# color_values: terraso-mobile-client/dev-client/node_modules/terraso-client-shared/src/soilId/soilIdTypes.ts

from typing import Optional, Tuple

# Equivalent of nonNeutralColorHues and colorValues
non_neutral_color_hues = [
    "R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"
]
color_values = [2, 2.5, 3, 4, 5, 6, 7, 8, 8.5, 9, 9.5] # from soilIdTypes.ts

def render_munsell_hue(color_hue: Optional[float], color_chroma: Optional[float]) -> Tuple[Optional[int], Optional[str]]:
    if color_hue is None:
        return None, None

    if isinstance(color_chroma, (int, float)) and round(color_chroma) == 0:
        return None, "N"

    if color_hue == 100:
        color_hue = 0

    hue_index = int(color_hue // 10)
    substep = round((color_hue % 10) / 2.5)

    if substep == 0:
        hue_index = (hue_index + 9) % 10
        substep = 4

    substep = (substep * 5) / 2

    return substep, non_neutral_color_hues[hue_index]


def munsell_to_string(color: dict) -> str:
    """
    color = {"colorHue": float, "colorValue": float, "colorChroma": float}
    """
    hue_substep, hue = render_munsell_hue(color.get("colorHue"), color.get("colorChroma"))
    v = color.get("colorValue")
    c = color.get("colorChroma")

    if c is None:
        return "N"

    
    if v is None:
        v = 0

    # snap value to closest allowed value
    value = min(color_values, key=lambda v_allowed: abs(v_allowed - v))
    chroma = round(c)
    if chroma == 0:
        return f"N {value}/"

    return f"{hue_substep}{hue} {value}/{chroma}"


# Example usage:
# example = {"colorHue": 25, "colorValue": 5.2, "colorChroma": 6.7}
# print(munsell_to_string(example))  # -> "5Y 5/7"




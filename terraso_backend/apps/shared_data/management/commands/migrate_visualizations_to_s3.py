# Copyright © 2026 Technology Matters
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

import structlog
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.shared_data.geojson_upload import get_geojson_from_data_entry
from apps.shared_data.models.visualization_config import VisualizationConfig
from apps.shared_data.services import geojson_upload_service
from apps.story_map.models.story_maps import StoryMap

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Migrates existing visualization configs from Mapbox tilesets/inline GeoJSON to S3 GeoJSON"
    )

    def handle(self, *args, **options):
        # Migrate VisualizationConfigs that have DataEntry but no S3 key
        vcs = VisualizationConfig.objects.filter(
            geojson_s3_key__isnull=True,
            data_entry__isnull=False,
        )

        migrated_vc_count = 0
        for vc in vcs:
            try:
                geojson = get_geojson_from_data_entry(vc.data_entry, vc)
                if geojson is None:
                    self.stdout.write(f"SKIP VC {vc.id} ({vc.title}): no GeoJSON generated")
                    continue

                file_content = json.dumps(geojson).encode("utf-8")
                file = ContentFile(file_content)
                file_name = f"{vc.id}.geojson"
                path = geojson_upload_service.upload_file_get_path(
                    str(vc.id), file, file_name=file_name
                )
                vc.geojson_s3_key = path
                vc.save()
                migrated_vc_count += 1
                self.stdout.write(f"MIGRATED VC {vc.id} ({vc.title}): key={path}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"ERROR VC {vc.id} ({vc.title}): {e}"))
                logger.exception("Migration error", extra={"vc_id": vc.id})

        self.stdout.write(
            self.style.SUCCESS(f"\nMigrated {migrated_vc_count} VisualizationConfigs")
        )

        # Step 2: Update StoryMap configs — replace inline geojson with S3 URL reference
        vcs_with_keys = {
            str(vc.id): vc
            for vc in VisualizationConfig.objects.filter(geojson_s3_key__isnull=False).only(
                "id", "geojson_s3_key"
            )
        }

        updated_sm_count = 0
        for sm in StoryMap.objects.all():
            changed = False
            for field_name in ("configuration", "published_configuration"):
                config = getattr(sm, field_name, None)
                if not config:
                    continue
                data_layers = config.get("dataLayers", {})
                if not data_layers:
                    continue
                for layer in data_layers.values():
                    if not isinstance(layer, dict):
                        continue
                    vc_id = layer.get("id")
                    if not vc_id:
                        continue
                    vc = vcs_with_keys.get(str(vc_id))
                    if not vc:
                        continue
                    # Remove inline geojson and embed the signed URL
                    if "geojson" in layer:
                        del layer["geojson"]
                    layer["geojsonSignedUrl"] = geojson_upload_service.get_signed_url(
                        vc.geojson_s3_key
                    )
                    changed = True
            if changed:
                sm.save(update_fields=["configuration", "published_configuration"])
                updated_sm_count += 1
                self.stdout.write(f"UPDATED SM {sm.id} ({sm.title})")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nUpdated {updated_sm_count} StoryMaps with geojsonSignedUrl references"
            )
        )
        self.stdout.write(self.style.SUCCESS("Migration complete"))

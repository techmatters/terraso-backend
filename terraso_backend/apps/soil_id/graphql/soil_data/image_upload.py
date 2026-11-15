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

import graphene
from django.conf import settings

from apps.graphql.schema.commons import BaseAuthenticatedMutation
from apps.graphql.schema.constants import MutationTypes
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.types import DepthIntervalInput
from apps.storage.services import soil_image_upload_service


class SoilImageUploadUrlRequest(BaseAuthenticatedMutation):
    """Mint a short-lived presigned S3 PUT URL for a soil image.

    Phase 1 of the site+depth image feature: the client requests a URL here
    (authorized against the site), then PUTs the image bytes directly to S3 —
    they never transit the backend. The returned ``object_key`` encodes site +
    depth, so uploaded images are findable by S3 prefix without any database
    record. Recording the key in the database (to list images later) is a
    tentative follow-up and is intentionally not done here yet.
    """

    # Only used to name the model in not-allowed errors; this mutation does not
    # write a model of its own.
    model_class = Site

    # Nullable: on the error path the base mutation returns only `errors`, so
    # these stay null. Marking them required would make GraphQL null the whole
    # payload on error and surface a top-level non-null violation instead.
    upload_url = graphene.String()
    object_key = graphene.String()

    class Input:
        site_id = graphene.ID(required=True)
        depth_interval = graphene.Field(DepthIntervalInput, required=True)
        content_type = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, site_id, depth_interval, content_type):
        site = cls.get_or_throw(Site, "id", site_id)

        user = info.context.user
        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            raise cls.not_allowed(MutationTypes.CREATE)

        extension = settings.SOIL_IMAGE_ACCEPTED_CONTENT_TYPES.get(content_type)
        if extension is None:
            accepted = ", ".join(sorted(settings.SOIL_IMAGE_ACCEPTED_CONTENT_TYPES))
            raise ValueError(f"Unsupported content type '{content_type}'. Accepted: {accepted}")

        object_key = soil_image_upload_service.build_object_key(
            site_id=site.id,
            depth_start=depth_interval["start"],
            depth_end=depth_interval["end"],
            extension=extension,
        )
        upload_url = soil_image_upload_service.create_presigned_put_url(object_key, content_type)

        return cls(upload_url=upload_url, object_key=object_key)

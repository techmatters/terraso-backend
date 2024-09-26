import enum
import traceback

import graphene
import structlog
from django.db import transaction

from apps.graphql.schema.commons import BaseWriteMutation
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_data import (
    SoilDataDepthDependentInputs,
    SoilDataInputs,
    SoilDataNode,
)
from apps.soil_id.models.soil_data import SoilData

logger = structlog.get_logger(__name__)


class SoilDataBulkUpdateSuccess(graphene.ObjectType):
    soil_data = graphene.Field(SoilDataNode, required=True)


# TODO: just a generic "can't access" result?
class SoilDataBulkUpdateFailureReason(graphene.Enum):
    DOES_NOT_EXIST = "DOES_NOT_EXIST"
    NOT_ALLOWED = "NOT_ALLOWED"


class SoilDataBulkUpdateFailure(graphene.ObjectType):
    reason = graphene.Field(SoilDataBulkUpdateFailureReason, required=True)


class SoilDataBulkUpdateResult(graphene.Union):
    class Meta:
        types = (SoilDataBulkUpdateSuccess, SoilDataBulkUpdateFailure)


class SoilDataBulkUpdateResultEntry(graphene.ObjectType):
    site_id = graphene.ID(required=True)
    result = graphene.Field(SoilDataBulkUpdateResult, required=True)


class SoilDataBulkUpdateDepthDependentEntry(SoilDataDepthDependentInputs, graphene.InputObjectType):
    pass


class SoilDataBulkUpdateEntry(SoilDataInputs, graphene.InputObjectType):
    site_id = graphene.ID(required=True)
    depth_intervals = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataBulkUpdateDepthDependentEntry)), required=True
    )


class SoilDataBulkUpdate(BaseWriteMutation):
    results = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataBulkUpdateResultEntry)), required=True
    )

    class Input:
        soil_data = graphene.Field(
            graphene.List(graphene.NonNull(SoilDataBulkUpdateEntry)), required=True
        )

    @classmethod
    def mutate_and_get_payload(cls, root, info, soil_data):
        try:
            results = []

            with transaction.atomic():
                for entry in soil_data:
                    site_id = entry.pop("site_id")
                    depth_intervals = entry.pop("depth_intervals")

                    site = Site.objects.filter(id=site_id).first()

                    if site is None:
                        results.append(
                            SoilDataBulkUpdateResultEntry(
                                site_id=site_id,
                                result=SoilDataBulkUpdateFailure(
                                    reason=SoilDataBulkUpdateFailureReason.DOES_NOT_EXIST
                                ),
                            )
                        )
                        continue

                    user = info.context.user
                    if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
                        results.append(
                            SoilDataBulkUpdateResultEntry(
                                site_id=entry["site_id"],
                                result=SoilDataBulkUpdateFailure(
                                    reason=SoilDataBulkUpdateFailureReason.NOT_ALLOWED
                                ),
                            )
                        )
                        continue

                    if not hasattr(site, "soil_data"):
                        site.soil_data = SoilData()

                    for attr, value in entry.items():
                        if isinstance(value, enum.Enum):
                            value = value.value
                        setattr(site.soil_data, attr, value)

                    site.soil_data.save()

                    for depth_interval_input in depth_intervals:
                        interval = depth_interval_input.pop("depth_interval")
                        depth_interval, _ = site.soil_data.depth_dependent_data.get_or_create(
                            depth_interval_start=interval["start"],
                            depth_interval_end=interval["end"],
                        )

                        for attr, value in depth_interval_input.items():
                            if isinstance(value, enum.Enum):
                                value = value.value
                            setattr(depth_interval, attr, value)

                        depth_interval.save()

                    results.append(
                        SoilDataBulkUpdateResultEntry(
                            site_id=site_id,
                            result=SoilDataBulkUpdateSuccess(soil_data=site.soil_data),
                        )
                    )

            logger.info(results)

            return cls(results=results)
        except Exception as exc:
            logger.info(traceback.format_exc(exc))

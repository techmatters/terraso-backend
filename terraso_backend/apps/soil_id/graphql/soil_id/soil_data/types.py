import enum

import graphene
import structlog
from django.db import transaction

from apps.graphql.schema.commons import BaseWriteMutation
from apps.graphql.schema.sites import SiteNode
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_data import (
    DepthIntervalInput,
    SoilDataDepthDependentInputs,
    SoilDataDepthIntervalFields,
    SoilDataInputs,
)
from apps.soil_id.models.soil_data import SoilData
from apps.soil_id.models.soil_data_history import SoilDataHistory

logger = structlog.get_logger(__name__)


class SoilDataBulkUpdateSuccess(graphene.ObjectType):
    site = graphene.Field(SiteNode, required=True)


# TODO: just a generic "can't access" result?
class SoilDataBulkUpdateFailureReason(graphene.Enum):
    DOES_NOT_EXIST = "DOES_NOT_EXIST"
    NOT_ALLOWED = "NOT_ALLOWED"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"


class SoilDataBulkUpdateFailure(graphene.ObjectType):
    site = graphene.Field(SiteNode, required=False)
    reason = graphene.Field(SoilDataBulkUpdateFailureReason, required=True)


class SoilDataBulkUpdateResult(graphene.Union):
    class Meta:
        types = (SoilDataBulkUpdateSuccess, SoilDataBulkUpdateFailure)


class SoilDataBulkUpdateResultEntry(graphene.ObjectType):
    site_id = graphene.ID(required=True)
    result = graphene.Field(SoilDataBulkUpdateResult, required=True)


class SoilDataBulkUpdateDepthDependentEntry(SoilDataDepthDependentInputs, graphene.InputObjectType):
    pass


class SoilDataBulkUpdateSoilData(SoilDataInputs, graphene.InputObjectType):
    pass


class SoilDataBulkUpdateDepthIntervalEntry(SoilDataDepthIntervalFields, graphene.InputObjectType):
    deleted = graphene.Boolean(required=True)
    pass


class SoilDataBulkUpdateEntry(SoilDataInputs, graphene.InputObjectType):
    site_id = graphene.ID(required=True)
    soil_data = graphene.Field(graphene.NonNull(SoilDataBulkUpdateSoilData))
    depth_dependent_data = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataBulkUpdateDepthDependentEntry)), required=True
    )
    depth_intervals = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataBulkUpdateDepthIntervalEntry)), required=True
    )
    deleted_depth_intervals = graphene.Field(
        graphene.List(graphene.NonNull(DepthIntervalInput)), required=True
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
        # TODO: refactor spaghetti mutation logic re: history, split into smaller functions
        results = []

        with transaction.atomic():
            for entry in soil_data:
                site_id = entry.pop("site_id")
                depth_intervals = entry["depth_dependent_data"]

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
                            site_id=site_id,
                            result=SoilDataBulkUpdateFailure(
                                site=site, reason=SoilDataBulkUpdateFailureReason.NOT_ALLOWED
                            ),
                        )
                    )
                    continue

                if not hasattr(site, "soil_data"):
                    site.soil_data = SoilData()

                for attr, value in entry["soil_data"].items():
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

                    depth_interval_input["depth_interval"] = interval

                    depth_interval.save()

                results.append(
                    SoilDataBulkUpdateResultEntry(
                        site_id=site_id,
                        result=SoilDataBulkUpdateSuccess(site=site),
                    )
                )

                history_entry = SoilDataHistory(site=site, changed_by=user, soil_data_changes=entry)
                history_entry.save()

        return cls(results=results)

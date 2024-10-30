import copy

import graphene
import structlog
from django.db import IntegrityError, transaction
from django.forms import ValidationError

from apps.core.models.users import User
from apps.graphql.schema.commons import BaseWriteMutation
from apps.graphql.schema.sites import SiteNode
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission
from apps.soil_id.graphql.soil_data.types import (
    SoilDataDepthDependentInputs,
    SoilDataDepthIntervalInputs,
    SoilDataInputs,
)
from apps.soil_id.graphql.types import DepthIntervalInput
from apps.soil_id.models.soil_data import SoilData
from apps.soil_id.models.soil_data_history import SoilDataHistory

logger = structlog.get_logger(__name__)


class SoilDataPushEntrySuccess(graphene.ObjectType):
    site = graphene.Field(SiteNode, required=True)


# TODO: just a generic "can't access" result?
class SoilDataPushFailureReason(graphene.Enum):
    DOES_NOT_EXIST = "DOES_NOT_EXIST"
    NOT_ALLOWED = "NOT_ALLOWED"
    INVALID_DATA = "INVALID_DATA"


class SoilDataPushEntryFailure(graphene.ObjectType):
    reason = graphene.Field(SoilDataPushFailureReason, required=True)


class SoilDataPushEntryResult(graphene.Union):
    class Meta:
        types = (SoilDataPushEntrySuccess, SoilDataPushEntryFailure)


class SoilDataPushEntry(graphene.ObjectType):
    site_id = graphene.ID(required=True)
    result = graphene.Field(SoilDataPushEntryResult, required=True)


class SoilDataPushInputDepthDependentData(SoilDataDepthDependentInputs, graphene.InputObjectType):
    pass


class SoilDataPushInputDepthInterval(SoilDataDepthIntervalInputs, graphene.InputObjectType):
    pass


class SoilDataPushInputSoilData(SoilDataInputs, graphene.InputObjectType):
    depth_dependent_data = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataPushInputDepthDependentData)), required=True
    )
    depth_intervals = graphene.Field(
        graphene.List(graphene.NonNull(SoilDataPushInputDepthInterval)), required=True
    )
    deleted_depth_intervals = graphene.Field(
        graphene.List(graphene.NonNull(DepthIntervalInput)), required=True
    )


class SoilDataPushInputEntry(graphene.InputObjectType):
    site_id = graphene.ID(required=True)
    soil_data = graphene.Field(graphene.NonNull(SoilDataPushInputSoilData))


class SoilDataPush(BaseWriteMutation):
    results = graphene.Field(graphene.List(graphene.NonNull(SoilDataPushEntry)), required=True)

    class Input:
        soil_data_entries = graphene.Field(
            graphene.List(graphene.NonNull(SoilDataPushInputEntry)), required=True
        )

    @staticmethod
    def record_soil_data_push(user: User, soil_data_entries: list[dict]) -> list[SoilDataHistory]:
        history_entries = []

        for entry in soil_data_entries:
            changes = copy.deepcopy(entry["soil_data"])
            site = Site.objects.filter(id=entry["site_id"]).first()

            history_entry = SoilDataHistory(site=site, changed_by=user, soil_data_changes=changes)
            history_entry.save()
            history_entries.append(history_entry)

        return history_entries

    @staticmethod
    def record_entry_failure(
        history_entry: SoilDataHistory, reason: SoilDataPushFailureReason, site_id: str
    ):
        history_entry.update_failure_reason = reason.value
        history_entry.save()
        return SoilDataPushEntry(site_id=site_id, result=SoilDataPushEntryFailure(reason=reason))

    @staticmethod
    def get_valid_site_for_soil_update(user: User, site_id: str):
        site = Site.objects.filter(id=site_id).first()

        if site is None:
            return None, SoilDataPushFailureReason.DOES_NOT_EXIST

        if not check_site_permission(user, SiteAction.ENTER_DATA, Context(site=site)):
            return None, SoilDataPushFailureReason.NOT_ALLOWED

        if not check_site_permission(user, SiteAction.UPDATE_DEPTH_INTERVAL, Context(site=site)):
            return None, SoilDataPushFailureReason.NOT_ALLOWED

        if not hasattr(site, "soil_data"):
            site.soil_data = SoilData()

        return site, None

    @staticmethod
    def save_soil_data(site: Site, soil_data: dict):
        if (
            "depth_interval_preset" in soil_data
            and soil_data["depth_interval_preset"] != site.soil_data.depth_interval_preset
        ):
            site.soil_data.depth_intervals.all().delete()

        BaseWriteMutation.assign_graphql_fields_to_model_instance(
            model_instance=site.soil_data, fields=soil_data
        )

    @staticmethod
    def save_depth_dependent_data(site: Site, depth_dependent_data: list[dict]):
        for depth_dependent_entry in depth_dependent_data:
            interval = depth_dependent_entry.pop("depth_interval")
            depth_interval, _ = site.soil_data.depth_dependent_data.get_or_create(
                depth_interval_start=interval["start"],
                depth_interval_end=interval["end"],
            )

            BaseWriteMutation.assign_graphql_fields_to_model_instance(
                model_instance=depth_interval, fields=depth_dependent_entry
            )

    @staticmethod
    def update_depth_intervals(site: Site, depth_intervals: list[dict]):
        for depth_interval_input in depth_intervals:
            interval_input = depth_interval_input.pop("depth_interval")
            depth_interval, _ = site.soil_data.depth_intervals.get_or_create(
                depth_interval_start=interval_input["start"],
                depth_interval_end=interval_input["end"],
            )

            BaseWriteMutation.assign_graphql_fields_to_model_instance(
                model_instance=depth_interval, fields=depth_interval_input
            )

    @staticmethod
    def delete_depth_intervals(site: Site, deleted_depth_intervals: list[dict]):
        for interval in deleted_depth_intervals:
            site.soil_data.depth_intervals.filter(
                depth_interval_start=interval["start"], depth_interval_end=interval["end"]
            ).delete()

    @staticmethod
    def get_entry_result(user: User, soil_data_entry: dict, history_entry: SoilDataHistory):
        site_id = soil_data_entry["site_id"]
        soil_data = soil_data_entry["soil_data"]

        depth_dependent_data = soil_data.pop("depth_dependent_data")
        depth_intervals = soil_data.pop("depth_intervals")
        deleted_depth_intervals = soil_data.pop("deleted_depth_intervals")

        try:
            site, reason = SoilDataPush.get_valid_site_for_soil_update(user=user, site_id=site_id)
            if site is None:
                return SoilDataPush.record_entry_failure(
                    history_entry=history_entry,
                    site_id=site_id,
                    reason=reason,
                )

            SoilDataPush.save_soil_data(site, soil_data)
            SoilDataPush.update_depth_intervals(site, depth_intervals)
            SoilDataPush.save_depth_dependent_data(site, depth_dependent_data)
            SoilDataPush.delete_depth_intervals(site, deleted_depth_intervals)

            history_entry.update_succeeded = True
            history_entry.save()
            return SoilDataPushEntry(site_id=site_id, result=SoilDataPushEntrySuccess(site=site))

        except (ValidationError, IntegrityError):
            return SoilDataPush.record_entry_failure(
                history_entry=history_entry,
                site_id=site_id,
                reason=SoilDataPushFailureReason.INVALID_DATA,
            )

    @classmethod
    def mutate_and_get_payload(cls, root, info, soil_data_entries: list[dict]):
        results = []
        user = info.context.user

        with transaction.atomic():
            history_entries = SoilDataPush.record_soil_data_push(user, soil_data_entries)

        with transaction.atomic():
            for entry, history_entry in zip(soil_data_entries, history_entries):
                results.append(
                    SoilDataPush.get_entry_result(
                        user=user, soil_data_entry=entry, history_entry=history_entry
                    )
                )

        return cls(results=results)

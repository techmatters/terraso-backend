# Copyright © 2023 Technology Matters
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

import django_filters
from django.db.models import Q, Subquery
from graphene_django.filter import DjangoFilterConnectionField

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core.models import Group, Landscape, SharedResource
from apps.shared_data.models import DataEntry


class MultipleChoiceField(django_filters.fields.MultipleChoiceField):
    def validate(self, value):
        pass


class MultipleInputFilter(django_filters.MultipleChoiceFilter):
    field_class = MultipleChoiceField


class SharedResourceFilterSet(django_filters.FilterSet):
    source__data_entry__resource_type__in = MultipleInputFilter(
        method="filter_source_data_entry",
    )

    class Meta:
        model = SharedResource
        fields = {}

    def filter_source_data_entry(self, queryset, name, value):
        data_entry_filter = name.replace("source__data_entry__", "")
        filters = {data_entry_filter: value}
        return queryset.filter(source_object_id__in=DataEntry.objects.filter(**filters))


class SharedResourcesMixin:
    shared_resources = DjangoFilterConnectionField(
        "apps.graphql.schema.shared_resources.SharedResourceNode",
        filterset_class=SharedResourceFilterSet,
    )

    def resolve_shared_resources(self, info, **kwargs):
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "shared_resources" in self._prefetched_objects_cache
        ):
            return self.shared_resources
        user_pk = getattr(info.context.user, "pk", False)
        user_groups_ids = Subquery(
            Group.objects.filter(
                membership_list__memberships__deleted_at__isnull=True,
                membership_list__memberships__user__id=user_pk,
                membership_list__memberships__membership_status=CollaborationMembership.APPROVED,
            ).values("id")
        )
        user_landscape_ids = Subquery(
            Landscape.objects.filter(
                membership_list__memberships__deleted_at__isnull=True,
                membership_list__memberships__user__id=user_pk,
                membership_list__memberships__membership_status=CollaborationMembership.APPROVED,
            ).values("id")
        )
        return self.shared_resources.filter(
            Q(target_object_id__in=user_groups_ids) | Q(target_object_id__in=user_landscape_ids)
        ).prefetch_related(
            "source",
        )

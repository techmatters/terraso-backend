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
from graphene_django.filter import DjangoFilterConnectionField

from apps.core.models import SharedResource
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
        return self.shared_resources.prefetch_related(
            "source",
        )

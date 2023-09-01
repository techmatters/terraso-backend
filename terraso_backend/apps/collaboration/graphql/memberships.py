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
import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import TerrasoConnection

from ..models import Membership, MembershipList

logger = structlog.get_logger(__name__)


class CollaborationMembershipListNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    account_membership = graphene.Field("apps.collaboration.graphql.CollaborationMembershipNode")
    memberships_count = graphene.Int()

    class Meta:
        model = MembershipList
        fields = (
            "memberships",
            "membership_type",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_account_membership(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        return self.memberships.filter(user=user).first()

    def resolve_memberships_count(self, info):
        user = info.context.user
        if user.is_anonymous:
            return 0
        return self.memberships.approved_only().count()


class CollaborationMembershipFilterSet(django_filters.FilterSet):
    user__email__not = django_filters.CharFilter(method="filter_user_email_not")

    class Meta:
        model = Membership
        fields = {
            "user": ["exact", "in"],
            "user_role": ["exact"],
            "user__email": ["icontains", "in"],
            "membership_status": ["exact"],
        }

    def filter_user_email_not(self, queryset, name, value):
        return queryset.exclude(user__email=value)


class CollaborationMembershipNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Membership
        fields = ("membership_list", "user", "user_role", "membership_status")
        filterset_class = CollaborationMembershipFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()

        return queryset

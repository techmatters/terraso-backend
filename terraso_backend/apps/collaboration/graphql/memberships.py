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

import graphene
import structlog
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import TerrasoConnection

from ..models import Membership, MembershipList

logger = structlog.get_logger(__name__)


class CollaborationMembershipListNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    account_membership = graphene.Field("apps.collaboration.graphql.CollaborationMembershipNode")
    memberships_count = graphene.Int()

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.filter(project__isnull=True)

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
        if hasattr(self, "account_memberships"):
            if len(self.account_memberships) > 0:
                return self.account_memberships[0]
            return None
        return self.memberships.filter(user=user).first()

    def resolve_memberships_count(self, info):
        if hasattr(self, "memberships_count"):
            return self.memberships_count

        # Nonmembers cannot see the number of members of a closed membership list
        if self.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED:
            is_member = (
                self.memberships.approved_only().filter(user__id=info.context.user.pk).exists()
            )
            if not is_member:
                return 0

        return self.memberships.approved_only().count()


class CollaborationMembershipNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Membership
        filter_fields = {
            "user": ["exact", "in"],
            "user_role": ["exact"],
            "user__email": ["icontains", "in"],
            "membership_status": ["exact"],
        }
        fields = ("membership_list", "user", "user_role", "membership_status")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()

        user_membership_list_ids = Membership.objects.filter(
            user=info.context.user, membership_status=Membership.APPROVED
        ).values_list("membership_list", flat=True)

        return queryset.filter(
            Q(membership_list__membership_type=MembershipList.MEMBERSHIP_TYPE_OPEN)
            | Q(membership_list__in=user_membership_list_ids)
            | Q(user=info.context.user)
        )


class BaseSaveInput:
    user_email = graphene.String(required=True)
    user_role = graphene.String()
    membership_status = graphene.String()

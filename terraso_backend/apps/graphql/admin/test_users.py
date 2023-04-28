import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.auth.services import JWTService
from apps.core.models import User
from apps.graphql.exceptions import GraphQLNotFoundException
from apps.graphql.schema.commons import BaseAdminMutation, TerrasoConnection

logger = structlog.get_logger(__name__)


class TestUserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = User
        filter_fields = {
            "email": ["exact", "icontains"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }
        fields = ("email", "first_name", "last_name", "profile_image", "memberships", "preferences")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.filter(is_test_user=True)


class GenerateTestUserTokenMutation(BaseAdminMutation):
    token = graphene.String()

    class Input:
        user_email = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user_email = kwargs["user_email"]

        try:
            user = User.objects.get(email=user_email, is_test_user=True)
        except User.DoesNotExist:
            logger.error(
                "User not found when generating test token",
                extra={"user_email": user_email},
            )
            raise GraphQLNotFoundException(field="user", model_name=User.__name__)

        token = JWTService().create_access_token(user)

        return cls(token=token)

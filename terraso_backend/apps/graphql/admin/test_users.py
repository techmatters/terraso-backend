import graphene
import structlog
from graphene import relay
from graphene_django import DjangoObjectType

from apps.auth.services import JWTService
from apps.core.models import User
from apps.e2e_tests.models import TestUser
from apps.graphql.exceptions import GraphQLNotFoundException
from apps.graphql.schema.commons import BaseAdminMutation, TerrasoConnection

logger = structlog.get_logger(__name__)


class TestUserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = TestUser
        filter_fields = {
            "user__email": ["exact", "icontains"],
            "user__first_name": ["icontains"],
            "user__last_name": ["icontains"],
        }
        fields = ("user", "enabled", "id")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class GenerateTestUserTokenMutation(BaseAdminMutation):
    token = graphene.String()

    class Input:
        user_email = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user_email = kwargs["user_email"]

        try:
            user = User.objects.get(email=user_email, test_user__isnull=False)
        except User.DoesNotExist:
            logger.error(
                "User not found when generating test token",
                extra={"user_email": user_email},
            )
            raise GraphQLNotFoundException(field="user", model_name=User.__name__)

        token = JWTService().create_test_access_token(user)

        return cls(token=token)

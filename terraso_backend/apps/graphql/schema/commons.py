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

import json
import re
from typing import Optional

import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from graphene import Connection, Field, Int, List, NonNull, ObjectType, String, relay
from graphene.types.generic import GenericScalar
from graphql import get_nullable_type

from apps.audit_logs import api as audit_log_api
from apps.audit_logs import services as audit_log_services
from apps.core.formatters import from_camel_to_snake_case
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)

from .constants import MutationTypes

logger = structlog.get_logger(__name__)


# we make TerrasoRelayNode.Field required by default since django's objects.get raises
# an error if the object is not found, so a nullable return result would be redundant
class TerrasoRelayNode(relay.Node):
    @classmethod
    def Field(cls, *args, **kwargs):
        kwargs["required"] = kwargs.pop("required", True)
        return super().Field(*args, **kwargs)

    @staticmethod
    def get_node_from_global_id(info, global_id, only_type=None):
        return get_nullable_type(info.return_type).graphene_type._meta.model.objects.get(
            pk=global_id
        )


class TerrasoConnection(Connection):
    class Meta:
        abstract = True

    total_count = Int(required=True)

    def resolve_total_count(self, info, **kwargs):
        queryset = self.iterable
        return queryset.count()

    # This will coax graphene to output more precise types for connections.
    # Context: https://github.com/graphql-python/graphene/pull/1504
    # Will be unnecessary after https://github.com/graphql-python/graphene-django/issues/901
    @classmethod
    def __init_subclass_with_meta__(cls, node=None, **options):
        type_name = re.sub("Connection$", "", cls.__name__)

        node_for_edge = node
        if node is not None and not isinstance(node, NonNull):
            node_for_edge = NonNull(node)

        class Edge(ObjectType):
            node = Field(node_for_edge, description="The item at the end of the edge")
            cursor = String(required=True, description="A cursor for use in pagination")

        class Meta:
            description = f"A Relay edge containing a `{type_name}` and its cursor."

        edge_type = type(f"{type_name}Edge", (Edge,), {"Meta": Meta})

        cls.Edge = edge_type

        cls.edges = Field(
            NonNull(List(NonNull(edge_type))),
            description="Contains the nodes in this connection.",
        )

        super().__init_subclass_with_meta__(node=node, **options)


class BaseMutation(relay.ClientIDMutation):
    class Meta:
        abstract = True

    errors = GenericScalar()

    @classmethod
    def Field(cls, *args, **kwargs):
        if "required" not in kwargs:
            kwargs["required"] = True
        return super().Field(*args, **kwargs)

    @classmethod
    def mutate(cls, root, info, input):
        try:
            return super().mutate(root, info, input)
        except Exception as error:
            logger.exception(
                "An error occurred while trying to execute mutation",
                extra={"error": str(error)},
            )
            return cls(errors=[{"message": str(error)}])

    @classmethod
    def get_or_throw(cls, model, field_name, id_):
        try:
            return model.objects.get(id=id_)
        except model.DoesNotExist:
            return GraphQLNotFoundException(field_name=field_name, model_name=model.__name__)

    @classmethod
    def not_allowed(cls, model, mutation_type=None, msg=None, extra=None):
        if not extra:
            extra = {}
        model_name = model.__name__
        if not msg:
            mutation_type = mutation_type.value if mutation_type else "change"
            msg = "Tried to {mutation_type} {model_name}, but user is not allowed"
        logger.error(msg, extra=extra)
        raise GraphQLNotAllowedException(model_name, operation=mutation_type)


class BaseAdminMutation(BaseMutation):
    class Meta:
        abstract = True

    @classmethod
    def mutate(cls, root, info, input):
        user = info.context.user

        if not user or not user.is_authenticated or not user.is_superuser:
            message = {
                "message": "You must be authenticated to perform this operation",
                "code": "unauthorized",
            }
            return cls(errors=[{"message": json.dumps([message])}])

        return super().mutate(root, info, input)


class BaseUnauthenticatedMutation(BaseMutation):
    class Meta:
        abstract = True


class BaseAuthenticatedMutation(BaseMutation):
    class Meta:
        abstract = True

    model_class = None

    @classmethod
    def mutate(cls, root, info, input):
        user = info.context.user

        if not user or not user.is_authenticated:
            message = {
                "message": "You must be authenticated to perform this operation",
                "code": "unauthorized",
            }
            return cls(errors=[{"message": json.dumps([message])}])

        return super().mutate(root, info, input)

    @classmethod
    def not_allowed(cls, mutation_type=None, msg=None, extra=None):
        raise super().not_allowed(cls.model_class, mutation_type=mutation_type, msg=msg, extra=None)

    @classmethod
    def not_allowed_create(cls, model, msg=None, extra=None):
        raise cls.not_allowed(MutationTypes.CREATE, msg, extra)


class BaseWriteMutation(BaseAuthenticatedMutation):
    logger: Optional[audit_log_api.AuditLog] = None
    skip_field_validation: Optional[str] = None

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        Since this is the base class for write operations, this method will be
        called both when adding and updating a model. The `kwargs` receives
        a dictionary with all inputs informed.
        """
        _id = kwargs.pop("id", None)

        if _id:
            model_instance = cls.model_class.objects.get(pk=_id)
        else:
            model_instance = cls.model_class()

        for attr, value in kwargs.items():
            setattr(model_instance, attr, value)

        try:
            kwargs = {}
            if cls.skip_field_validation is not None:
                kwargs["exclude"] = cls.skip_field_validation
            model_instance.full_clean(**kwargs)
        except ValidationError as exc:
            logger.info(
                "Attempt to mutate an model, but it's invalid",
                extra={"model": cls.model_class.__name__, "validation_error": exc},
            )
            raise GraphQLValidationException.from_validation_error(
                exc, model_name=cls.model_class.__name__
            )

        try:
            model_instance.save()
        except IntegrityError as exc:
            logger.info(
                "Attempt to mutate an model, but it's not unique",
                extra={"model": cls.model_class.__name__, "integrity_error": exc},
            )

            # It's not trivial identify the exact field(s) that originated the integrity errror
            # here, so we identify the error as NON_FIELD_ERROR with the unique code.
            validation_error = ValidationError(
                message={
                    NON_FIELD_ERRORS: ValidationError(
                        message=f"This {cls.model_class.__name__} already exists",
                        code="unique",
                    )
                },
            )
            raise GraphQLValidationException.from_validation_error(
                validation_error, model_name=cls.model_class.__name__
            )

        result_kwargs = {from_camel_to_snake_case(cls.model_class.__name__): model_instance}

        return cls(**result_kwargs)

    @classmethod
    def is_update(cls, data):
        return "id" in data

    @classmethod
    def get_logger(cls):
        """Returns the logger instance."""
        if not cls.logger:
            cls.logger = audit_log_services.new_audit_logger()
        return cls.logger


class BaseDeleteMutation(BaseAuthenticatedMutation):
    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        _id = kwargs.pop("id", None)

        if not _id:
            model_instance = None
        else:
            model_instance = cls.model_class.objects.get(pk=_id)
            model_instance.delete()

        result_kwargs = {from_camel_to_snake_case(cls.model_class.__name__): model_instance}
        return cls(**result_kwargs)

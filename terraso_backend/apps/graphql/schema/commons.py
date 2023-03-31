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

import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from graphene import Connection, Int, relay
from graphene.types.generic import GenericScalar

from apps.core.formatters import from_camel_to_snake_case
from apps.graphql.exceptions import GraphQLValidationException

logger = structlog.get_logger(__name__)


class TerrasoRelayNode(relay.Node):
    @staticmethod
    def get_node_from_global_id(info, global_id, only_type=None):
        return info.return_type.graphene_type._meta.model.objects.get(pk=global_id)


class TerrasoConnection(Connection):
    class Meta:
        abstract = True

    total_count = Int()

    def resolve_total_count(self, info, **kwargs):
        return self.length


class BaseMutation(relay.ClientIDMutation):
    class Meta:
        abstract = True

    errors = GenericScalar()

    @classmethod
    def mutate(cls, root, info, input):
        user = info.context.user

        if not user or not user.is_authenticated:
            return cls(errors=[{"message": "You must be authenticated to perform this operation"}])

        try:
            return super().mutate(root, info, input)
        except Exception as error:
            logger.exception(
                "An error occurred while trying to execute mutation",
                extra={"error": str(error)},
            )
            return cls(errors=[{"message": str(error)}])


class BaseWriteMutation(BaseMutation):
    model_class = None

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
            model_instance.full_clean()
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


class BaseDeleteMutation(BaseMutation):
    model_class = None

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

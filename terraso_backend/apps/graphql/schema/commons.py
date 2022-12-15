import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from graphene import Connection, Int, relay

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


class BaseWriteMutation(relay.ClientIDMutation):
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
            print("Validation error")
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
            print("Integrity error", exc)
            print(dir(exc))
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


class BaseDeleteMutation(relay.ClientIDMutation):
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

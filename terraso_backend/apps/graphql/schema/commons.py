import re

from django.core.exceptions import ValidationError
from graphene import relay

from apps.graphql.exceptions import GraphQLValidationException

RE_CAMEL_TO_SNAKE_CASE = re.compile(r"(?<!^)(?=[A-Z])")


def from_camel_to_snake_case(model_class):
    """
    Transforms camel case to snake case. MyModel becomes my_model.
    """
    model_class_name = model_class.__name__
    return RE_CAMEL_TO_SNAKE_CASE.sub("_", model_class_name).lower()


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
            raise GraphQLValidationException.from_validation_error(exc)

        model_instance.save()

        result_kwargs = {from_camel_to_snake_case(cls.model_class): model_instance}

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

        result_kwargs = {from_camel_to_snake_case(cls.model_class): model_instance}

        return cls(**result_kwargs)

import re

import graphql_relay
from graphene import relay

RE_CAMEL_TO_SNAKE_CASE = re.compile(r"(?<!^)(?=[A-Z])")


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
        graphql_id = kwargs.pop("id", None)

        if graphql_id:
            _, _pk = graphql_relay.from_global_id(graphql_id)
            model_instance = cls.model_class.objects.get(pk=_pk)
        else:
            model_instance = cls.model_class()

        for attr, value in kwargs.items():
            setattr(model_instance, attr, value)

        model_instance.save()

        result_kwargs = {cls.model_class.__name__.lower(): model_instance}

        return cls(**result_kwargs)


class BaseDeleteMutation(relay.ClientIDMutation):
    model_class = None

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        graphql_id = kwargs.pop("id", None)

        if not graphql_id:
            model_instance = None
        else:
            _, _pk = graphql_relay.from_global_id(graphql_id)
            model_instance = cls.model_class.objects.get(pk=_pk)
            model_instance.delete()

        result_kwargs = {cls._get_result_attribute_name(): model_instance}

        return cls(**result_kwargs)

    @classmethod
    def _get_result_attribute_name(cls):
        """
        Transforms model class name from camel case to snake case. MyModel
        becomes my_model.
        """
        model_class_name = cls.model_class.__name__
        return RE_CAMEL_TO_SNAKE_CASE.sub("_", model_class_name).lower()

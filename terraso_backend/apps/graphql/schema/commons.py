from django.core.exceptions import ValidationError
from graphene import Connection, Int, relay

from apps.graphql.exceptions import GraphQLValidationException
from apps.graphql.formatters import from_camel_to_snake_case


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
            raise GraphQLValidationException.from_validation_error(
                exc, model_name=cls.model_class.__name__
            )

        model_instance.save()

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

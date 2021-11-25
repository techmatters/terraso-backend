import graphene
import graphql_relay
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import Landscape


class LandscapeNode(DjangoObjectType):
    class Meta:
        model = Landscape
        filter_fields = ["name", "description", "groups"]
        interfaces = (relay.Node,)


class LandscapeWriteMutation(relay.ClientIDMutation):
    landscape = graphene.Field(LandscapeNode)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        """
        This is the method performed everytime this mutation is submitted.
        Since this is the base class for write operations, this method will be
        called both when adding and updating Landscapes. The `kwargs` receives
        a dictionary with all inputs informed.
        """
        graphql_id = kwargs.pop("id", None)

        if graphql_id:
            _, _pk = graphql_relay.from_global_id(graphql_id)
            landscape = Landscape.objects.get(pk=_pk)
        else:
            landscape = Landscape()

        for attr, value in kwargs.items():
            setattr(landscape, attr, value)

        landscape.save()

        return LandscapeWriteMutation(landscape=landscape)


class LandscapeAddMutation(LandscapeWriteMutation):
    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()


class LandscapeUpdateMutation(LandscapeWriteMutation):
    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        location = graphene.String()


class LandscapeDeleteMutation(relay.ClientIDMutation):
    landscape = graphene.Field(LandscapeNode)

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        graphql_id = kwargs.pop("id", None)

        if not graphql_id:
            return LandscapeDeleteMutation(landscape=None)

        _, _pk = graphql_relay.from_global_id(graphql_id)
        landscape = Landscape.objects.get(pk=_pk)
        landscape.delete()

        return LandscapeDeleteMutation(landscape=landscape)

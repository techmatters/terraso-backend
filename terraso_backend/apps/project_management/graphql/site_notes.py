# Copyright © 2023 Technology Matters
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
from django.db import transaction
from graphene_django import DjangoObjectType

from apps.graphql.schema.commons import BaseDeleteMutation, BaseWriteMutation
from apps.project_management.models.site_notes import SiteNote
from apps.project_management.models.sites import Site


class SiteNoteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = SiteNote
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class SiteNoteAddMutation(BaseWriteMutation):
    site_note = graphene.Field(SiteNoteNode, required=True)

    class Input:
        site_id = graphene.ID(required=True)
        content = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        try:
            site = Site.objects.get(pk=input["site_id"])
        except Site.DoesNotExist:
            return cls(errors={"site_id": ["Site not found"]})

        site_note = SiteNote.objects.create(site=site, content=input["content"], author=user)
        return SiteNoteAddMutation(site_note=site_note)


class SiteNoteUpdateMutation(BaseWriteMutation):
    site_note = graphene.Field(SiteNoteNode, required=True)

    class Input:
        id = graphene.ID(required=True)
        content = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site_note_id = kwargs["id"]
        site_note = cls.get_node(info, id=site_note_id)

        if site_note.author != user:
            cls.not_allowed("You do not have permission to update this note")

        site_note.content = kwargs["content"]
        site_note.save()
        return SiteNoteUpdateMutation(site_note=site_note)


class SiteNoteDeleteMutation(BaseDeleteMutation):
    ok = graphene.Boolean()

    class Input:
        id = graphene.ID(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site_note_id = kwargs["id"]
        site_note = cls.get_node(info, id=site_note_id)

        if site_note.author != user:
            cls.not_allowed("You do not have permission to delete this note")

        site_note.delete()
        return SiteNoteDeleteMutation(ok=True)

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

from apps.core.models.users import deleted_user_stub
from apps.graphql.schema.commons import (
    BaseDeleteMutation,
    BaseWriteMutation,
    TerrasoConnection,
)
from apps.graphql.schema.users import UserNode
from apps.project_management.models.site_notes import SiteNote
from apps.project_management.models.sites import Site
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import SiteAction, check_site_permission


class SiteNoteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    # Explicit field declaration so resolve_author below is honored.
    # graphene_django's auto-generated FK field does not pick up
    # resolve_<field> methods on the class (the default resolver path
    # bypasses them). With an explicit graphene.Field here, the Type
    # metaclass binds resolve_author as the field's resolver.
    author = graphene.Field(UserNode, required=True)

    class Meta:
        model = SiteNote
        # saved_author is an internal shadow for author restore-on-undelete;
        # never expose it through the API.
        exclude = ("saved_author",)
        interfaces = (graphene.relay.Node,)

        connection_class = TerrasoConnection

    def resolve_author(self, info):
        # SiteNote.author is SET_NULL when the authoring user is deleted and
        # site still exists.
        # Return an in-memory stub so the schema's non-null author contract
        # holds and old clients (which dereference author.id) don't crash.
        # See terraso-backend-research/deleted_user_stub_plan.md.
        if self.author_id is None:
            return deleted_user_stub()
        return self.author


class SiteNoteAddMutation(BaseWriteMutation):
    site_note = graphene.Field(SiteNoteNode, required=True)

    model_class = SiteNote

    class Input:
        site_id = graphene.ID(required=True)
        content = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        user = info.context.user
        site_id = input["site_id"]
        site = cls.get_or_throw(Site, "id", site_id)
        if not check_site_permission(user, SiteAction.CREATE_NOTE, Context(site=site)):
            cls.not_allowed_create(SiteNote)

        site_note = SiteNote.objects.create(site=site, content=input["content"], author=user)
        return SiteNoteAddMutation(site_note=site_note)


class SiteNoteUpdateMutation(BaseWriteMutation):
    site_note = graphene.Field(SiteNoteNode, required=True)

    model_class = SiteNote

    class Input:
        id = graphene.ID(required=True)
        content = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site_note_id = kwargs["id"]
        site_note = cls.get_or_throw(SiteNote, "id", site_note_id)
        if not check_site_permission(user, SiteAction.EDIT_NOTE, Context(site_note=site_note)):
            cls.not_allowed()

        site_note.content = kwargs["content"]
        site_note.save()
        return SiteNoteUpdateMutation(site_note=site_note)


class SiteNoteDeleteMutation(BaseDeleteMutation):
    ok = graphene.Boolean()

    model_class = SiteNote

    class Input:
        id = graphene.ID(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site_note_id = kwargs["id"]
        site_note = cls.get_or_throw(SiteNote, "id", site_note_id)
        if not check_site_permission(user, SiteAction.DELETE_NOTE, Context(site_note=site_note)):
            cls.not_allowed()

        site_note.delete()
        return SiteNoteDeleteMutation(ok=True)

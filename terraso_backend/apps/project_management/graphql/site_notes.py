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
from graphene_django import DjangoObjectType
from apps.project_management.models.sites import Site, SiteNote


class SiteNoteNode(DjangoObjectType):
    class Meta:
        model = SiteNote
        fields = '__all__'
        interfaces = (graphene.relay.Node,)


class SiteNoteAddMutation(graphene.Mutation):
    class Arguments:
        site_id = graphene.ID(required=True)
        content = graphene.String(required=True)

    site_note = graphene.Field(lambda: SiteNoteNode)

    def mutate(self, info, site_id, content):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("You must be logged in to add a note")

        site = Site.objects.get(pk=site_id)
        site_note = SiteNote.objects.create(site=site, content=content, author=user)
        return SiteNoteAddMutation(site_note=site_note)


class SiteNoteUpdateMutation(graphene.Mutation):
    class Arguments:
        site_note_id = graphene.ID(required=True)
        content = graphene.String(required=True)

    site_note = graphene.Field(lambda: SiteNoteNode)

    def mutate(self, info, site_note_id, content):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("You must be logged in to update a note")

        site_note = SiteNote.objects.get(pk=site_note_id)
        if site_note.author != user:
            raise Exception("You do not have permission to update this note")

        site_note.content = content
        site_note.save()
        return SiteNoteUpdateMutation(site_note=site_note)


class SiteNoteDeleteMutation(graphene.Mutation):
    class Arguments:
        site_note_id = graphene.ID(required=True)

    ok = graphene.Boolean()

    def mutate(self, info, site_note_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("You must be logged in to delete a note")

        site_note = SiteNote.objects.get(pk=site_note_id)
        if site_note.author != user:
            raise Exception("You do not have permission to delete this note")

        site_note.delete()
        return SiteNoteDeleteMutation(ok=True)

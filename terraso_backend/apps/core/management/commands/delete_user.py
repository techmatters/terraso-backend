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

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, ProtectedError

from apps.core.models import User
from apps.project_management.models import Project
from apps.project_management.models.sites import Site


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--user", help="ID or email of a user whose data should be removed")

    def handle(self, *args, **options):
        user_id = options.get("user")
        if not user_id:
            raise CommandError("Please specify a user ID or email")

        if "@" in user_id:
            try:
                user = User.objects.get(email=user_id)
            except User.DoesNotExist:
                user = None

        if user is None:
            try:
                user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValidationError):
                raise CommandError(f"Please specify a valid user ID [input: {user_id}]")

        # projects where the user is the only member
        projects = Project.objects.annotate(members_count=Count("group__members__id")).filter(
            members_count=1, group__members__id=user.id
        )

        for project in projects:
            project.delete()

        # sites created by the user
        sites = Site.objects.filter(owner_id=user.id)

        for site in sites:
            site.delete()

        # NOTE: user deletion currently fails due to audit logs
        try:
            user.delete()
        except ProtectedError:
            raise CommandError(f"Unable to delete user {user}")

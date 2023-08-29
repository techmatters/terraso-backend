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

from apps.core.models import User


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

        user.delete()

# Copyright © 2024 Technology Matters
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

from django.core.management.base import BaseCommand, CommandError

from apps.core.hubspot import create_account_deletion_ticket
from apps.core.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="The test user email")

    def handle(self, *args, **options):
        email = options["email"]
        if not email:
            raise CommandError("Please provide an email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"No user found with email address f{email}")

        print(f"Creating acccount deletion ticket for f{user.email}")
        create_account_deletion_ticket(user)

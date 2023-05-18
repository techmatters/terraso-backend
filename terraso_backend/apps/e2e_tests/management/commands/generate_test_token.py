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

from django.core.management.base import BaseCommand, CommandError

from apps.auth.services import JWTService
from apps.core.models import User


class Command(BaseCommand):
    help = "Generates a test token for a test user"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="The test user email")

    def handle(self, *args, **kwargs):
        email = kwargs["email"]
        if not email:
            raise CommandError("Please provide an email")

        try:
            user = User.objects.get(email=email, test_user__isnull=False)
        except User.DoesNotExist:
            raise CommandError("User not found when generating test token")

        token = JWTService().create_test_access_token(user)

        self.stdout.write(self.style.SUCCESS(f"Token: {token}"))

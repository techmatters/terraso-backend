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

from django.dispatch import receiver

from apps.auth.signals import user_signup_signal

from .models.memberships import Membership


@receiver(user_signup_signal)
def handle_pending_memberships(sender, **kwargs):
    user = kwargs["user"]
    pending_memberships = Membership.objects.filter(pending_email__iexact=user.email)
    for membership in pending_memberships:
        membership.pending_email = None
        membership.user = user
        membership.save()

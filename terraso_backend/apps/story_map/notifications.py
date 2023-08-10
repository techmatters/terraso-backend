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

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apps.notifications.email import TRACKING_PARAMETERS, EmailNotification


def send_memberships_invite_email(memberships, story_map):
    params = urlencode(TRACKING_PARAMETERS)
    story_map_url = (
        f"{settings.WEB_CLIENT_URL}/tools/story-maps/"
        f"{story_map.story_map_id}/{story_map.slug}/edit?"
        f"{params}"
    )
    users = [
        membership.user for membership in memberships if membership.user.notifications_enabled()
    ]
    for user in users:
        recipients = [user.name_and_email()]
        context = {
            "firstName": user.first_name,
            "storyMapTitle": story_map.title,
            "storyMapUrl": story_map_url,
            "unsubscribeUrl": EmailNotification.unsubscribe_url(user),
        }

        with translation.override(user.language()):
            subject = _(
                "Membership in “%(storyMapTitle)s” has been approved"
                % {"storyMapTitle": story_map.title}
            )
            body = render_to_string("story-map-membership-invite.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

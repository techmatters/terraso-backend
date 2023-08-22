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

from apps.auth.services import JWTService
from apps.notifications.email import TRACKING_PARAMETERS, EmailNotification


def accept_invite_url(user, membership):
    params = TRACKING_PARAMETERS
    params["token"] = JWTService().create_token(
        user,
        extra_payload={
            "membershipId": str(membership.id),
            "pendingEmail": membership.pending_email if user is None else None,
        },
    )
    return f"{settings.WEB_CLIENT_URL}/tools/story-maps/accept?{urlencode(params)}"


def send_memberships_invite_email(requestor, memberships, story_map):
    signed_up_memberships = [
        membership
        for membership in memberships
        if membership.user is not None and membership.user.notifications_enabled()
    ]
    for membership in signed_up_memberships:
        user = membership.user
        recipients = [user.name_and_email()]
        context = {
            "firstName": user.first_name,
            "storyMapTitle": story_map.title,
            "acceptInviteUrl": accept_invite_url(user, membership),
            "unsubscribeUrl": EmailNotification.unsubscribe_url(user),
        }

        with translation.override(user.language()):
            subject = _(
                "Membership in “%(storyMapTitle)s” has been approved"
                % {"storyMapTitle": story_map.title}
            )
            body = render_to_string("story-map-membership-invite.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

    not_signed_up_memberships = [
        membership for membership in memberships if membership.user is None
    ]
    for membership in not_signed_up_memberships:
        recipients = [membership.pending_email]
        context = {
            "firstName": membership.pending_email,
            "storyMapTitle": story_map.title,
            "acceptInviteUrl": accept_invite_url(None, membership),
        }

        with translation.override(requestor.language()):
            subject = _(
                "Membership in “%(storyMapTitle)s” has been approved"
                % {"storyMapTitle": story_map.title}
            )
            body = render_to_string("story-map-membership-invite.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

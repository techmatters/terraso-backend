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
    params["token"] = JWTService().create_story_map_membership_approve_token(membership)
    return f"{settings.WEB_CLIENT_URL}/tools/story-maps/accept?{urlencode(params)}"


def send_memberships_invite_email(inviter, memberships, story_map):
    member_signups = [
        membership
        for membership in memberships
        if membership.user is not None and membership.user.notifications_enabled()
    ]
    base_context = {
        "storyMapOwnerFirstName": story_map.created_by.first_name,
        "inviterFirstName": inviter.first_name,
        "storyMapTitle": story_map.title,
        "unsubscribeUrl": EmailNotification.unsubscribe_url(inviter),
    }
    for membership in member_signups:
        user = membership.user
        recipients = [user.name_and_email()]
        context = {
            "firstName": user.first_name,
            "acceptInviteUrl": accept_invite_url(user, membership),
            **base_context,
        }

        with translation.override(user.language()):
            subject = _(
                "%(firstName)s, you are invited to edit “%(storyMapTitle)s” in Terraso" % context
            )
            body = render_to_string("story-map-membership-invite.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

    nonmember_signups = [
        membership for membership in memberships if membership.user is None
    ]
    for membership in nonmember_signups:
        recipients = [membership.pending_email]
        context = {
            "firstName": membership.pending_email,
            "acceptInviteUrl": accept_invite_url(None, membership),
            **base_context,
        }

        with translation.override(inviter.language()):
            subject = _("You are invited to edit “%(storyMapTitle)s” in Terraso" % context)
            body = render_to_string("story-map-membership-invite.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

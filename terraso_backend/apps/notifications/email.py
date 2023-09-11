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

import os
from base64 import b64encode
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apps.auth.services import JWTService

TRACKING_PARAMETERS = {"utm_source": "notification", "utm_medium": "email"}


class EmailNotification:
    @classmethod
    def sender(cls):
        return f"'{settings.EMAIL_FROM_NAME}' <{settings.EMAIL_FROM_ADDRESS}>"

    @classmethod
    def unsubscribe_url(cls, user):
        params = TRACKING_PARAMETERS
        params["token"] = JWTService().create_unsubscribe_token(user)
        return f"{settings.WEB_CLIENT_URL}/notifications/unsubscribe/?{urlencode(params)}"

    @classmethod
    def encode_image(cls, file_path):
        encoded_string = ""
        with open(file_path, "rb") as image_file:
            encoded_string = b64encode(image_file.read()).decode("ascii")

        if not encoded_string:
            return None

        extension = os.path.splitext(file_path)[1][1:]

        return f"data:image/{extension};base64,{encoded_string}"

    @classmethod
    def send_membership_request(cls, user, group):
        params = urlencode(TRACKING_PARAMETERS)
        requestUrl = f"{settings.WEB_CLIENT_URL}/groups/{group.slug}/members?{params}"
        context = {
            "memberName": user.full_name(),
            "groupName": group.name,
            "requestUrl": requestUrl,
        }

        managerList = [
            membership.user
            for membership in group.memberships.managers_only()
            if membership.user.group_notifications_enabled()
        ]

        for manager in managerList:
            recipients = [manager.name_and_email()]
            context["firstName"] = manager.first_name
            context["unsubscribeUrl"] = EmailNotification.unsubscribe_url(manager)

            with translation.override(manager.language()):
                body = render_to_string("group-pending.html", context)
                subject = _(
                    "%(user)s has requested to join “%(group)s”"
                    % {"user": user.full_name(), "group": group.name},
                )

            send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

    @classmethod
    def send_membership_approval(cls, user, group):
        if not user.group_notifications_enabled():
            return

        params = urlencode(TRACKING_PARAMETERS)
        groupUrl = f"{settings.WEB_CLIENT_URL}/groups/{group.slug}?{params}"
        recipients = [user.name_and_email()]
        context = {
            "firstName": user.first_name,
            "groupName": group.name,
            "groupUrl": groupUrl,
            "unsubscribeUrl": EmailNotification.unsubscribe_url(user),
        }

        with translation.override(user.language()):
            subject = _("Membership in “%(group)s” has been approved" % {"group": group.name})
            body = render_to_string("group-approved.html", context)

        send_mail(subject, None, EmailNotification.sender(), recipients, html_message=body)

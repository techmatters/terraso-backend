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

from django.conf import settings
from django.core.mail import send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext_lazy as _


class EmailNotification:
    @classmethod
    def SendMembershipRequest(cls, user, group):
        sender = f"'{settings.EMAIL_FROM_NAME}' <{settings.EMAIL_FROM_ADDRESS}>"
        messageList = []

        context = {
            "memberName": user.first_name,
            "groupName": group.name,
            "requestUrl": f"{settings.WEB_CLIENT_URL}/groups/{group.slug}",
        }

        managerList = [membership.user for membership in group.memberships.managers_only()]
        for manager in managerList:
            if not manager.notifications_enabled():
                continue

            recipients = [f"'{manager.full_name}' <{manager.email}>"]
            context["firstName"] = manager.first_name
            context[
                "unsubscribeUrl"
            ] = f"{settings.WEB_CLIENT_URL}/notifications/unsubscribe/{manager.id}"

            with translation.override(manager.language()):
                body = render_to_string("group-manager.html", context)
                subject = _(
                    "%(user)s has requested to join “%(group)s”",
                    {user: user.full_name, group: group.name},
                )

            messageList.append((subject, body, sender, recipients))

        send_mass_mail(messageList)

    @classmethod
    def SendMembershipApproval(cls, user, group):
        if not user.notifications_enabled():
            return

        sender = f"'{settings.EMAIL_FROM_NAME}' <{settings.EMAIL_FROM_ADDRESS}>"
        recipients = [f"'{user.full_name}' <{user.email}>"]
        context = {
            "memberName": user.first_name,
            "groupName": group.name,
            "requestUrl": f"{settings.WEB_CLIENT_URL}/groups/{group.slug}",
            "unsubscribeUrl": f"{settings.WEB_CLIENT_URL}/notifications/unsubscribe/{user.id}",
        }

        with translation.override(user.language()):
            subject = _("Membership in “%(group)s” has been approved", {group: group.name})
            body = render_to_string("group-member.html", context)

        send_mail(subject, body, sender, recipients)

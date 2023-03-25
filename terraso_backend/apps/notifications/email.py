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
from django.core.mail import send_mass_mail
from django.template.loader import render_to_string


class EmailNotification:
    @classmethod
    def say_hello(cls, **kwargs):
        print("hello world")

    @classmethod
    def SendMembershipRequest(cls, user, group):
        sender = f"'{settings.EMAIL_FROM_NAME}' <{settings.EMAIL_FROM_ADDRESS}>"
        subject = "Membership in {group.name} is pending approval"
        messageList = []

        context = {
            "memberName": user.first_name,
            "groupName": group.name,
            "requestUrl": f"{settings.WEB_CLIENT_URL}/groups/{group.slug}",
        }

        managerList = [membership.user for membership in group.memberships.managers_only()]

        for manager in managerList:
            # TODO: check notifications permissions
            # TODO: localize email per user's language preference

            context["firstName"] = manager.first_name
            context[
                "unsubscribeUrl"
            ] = f"{settings.WEB_CLIENT_URL}/notifications/unsubscribe/{manager.id}"
            body = render_to_string("group-member.html", context)
            recipients = [f"'{manager.first_name} {manager.last_name}' <{manager.email}>"]
            messageList.append((subject, body, sender, recipients))

        # TODO: send mail to member making request
        # TODO: check notifications permissions
        # TODO: localize email per user's language preference

        send_mass_mail(messageList)

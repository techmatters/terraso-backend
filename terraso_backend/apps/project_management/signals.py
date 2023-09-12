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

from datetime import datetime

from django.dispatch import receiver

from apps.audit_logs import api as audit_log_api
from apps.audit_logs import services
from apps.graphql.signals import membership_added_signal, membership_updated_signal

audit_logger = services.new_audit_logger()


def _handle_membership_log(user, action, membership, client_time):
    try:
        project = membership.group.project
    except Exception:
        project = None

    if project is None:
        return

    audit_logger.log(
        user=user,
        action=action,
        resource=membership,
        metadata={
            "user_email": membership.user.email,
            "user_role": membership.user_role,
            "project_id": str(project.id),
        },
        client_time=client_time,
    )


@receiver(membership_added_signal)
def handle_membership_added(sender, **kwargs):
    membership = kwargs["membership"]
    user = kwargs["user"]
    client_time = datetime.now()

    _handle_membership_log(user, audit_log_api.CREATE, membership, client_time)


@receiver(membership_updated_signal)
def handle_membership_updated(sender, **kwargs):
    membership = kwargs["membership"]
    user = kwargs["user"]
    client_time = datetime.now()

    _handle_membership_log(user, audit_log_api.CHANGE, membership, client_time)

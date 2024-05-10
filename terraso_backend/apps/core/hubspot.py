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


import requests
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


def create_account_deletion_ticket(user):
    if not user or not user.email:
        return False

    subject = f"Deletion request for {user.email}"
    body = f"LandPKS account deletion request:\nName: {user.full_name()}\nEmail: {user.email}"

    headers = {"Content-type": "application/json", "Authorization": settings.HUBSPOT_AUTH_TOKEN}
    data = {
        "fields": [
            {"objectTypeId": "0-1", "name": "email", "value": user.email},
            {"objectTypeId": "0-1", "name": "ticket.subject", "value": subject},
            {"objectTypeId": "0-1", "name": "ticket.content", "value": body},
        ]
    }

    try:
        response = requests.post(
            settings.HUBSPOT_ACCOUNT_DELETION_FORM_API_URL,
            headers=headers,
            json=data,
        )
        response.raise_for_status()
        result = response.json()
        if "inlineMessage" not in result:
            logger.error("HubSpot:no confirmation message found")
            return False

        return True

    except requests.ConnectionError as err:
        logger.error(f"HubSpot: failed to connect: {err}")
    except requests.Timeout:
        logger.error("HubSpot: timed out")
    except requests.RequestException as err:
        logger.error(f"HubSpot: error: {err}")

    return False

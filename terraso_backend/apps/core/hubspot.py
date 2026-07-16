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


def _normalize_env(env):
    """Map settings.ENV → one of HubSpot's `environment` radio values
    (`production` / `staging` / `dev` / `unknown`). Any value HubSpot
    doesn't recognize would be rejected by the form's radio validation,
    so we normalize on our side and fall back to `unknown`."""
    normalized = (env or "").lower()
    if normalized == "production":
        return "PROD"
    if normalized == "staging":
        return "STAGING"
    if normalized in ("development", "dev", "local"):
        return "DEV"
    return "?"


def create_account_deletion_ticket(user):
    """Open a HubSpot ticket asking support to delete the user's account.

    Support runs `python manage.py show_deletion_blockers <email>` to see
    what data is blocking automated deletion for this user.
    """
    if not user or not user.email:
        return False

    environment = _normalize_env(settings.ENV)
    subject = f"Deletion request for {user.email}"
    body_lines = [
        f"[{environment}] LandPKS account deletion request:",
        f"Name: {user.full_name()}",
        f"Email: {user.email}",
    ]
    body = "\n".join(body_lines)

    if settings.HUBSPOT_DRY_RUN:
        logger.info("HubSpot dry-run: skipping ticket creation", subject=subject, body=body)
        return True
    else:
        logger.info("Creating HubSpot ticket", subject=subject, body=body)

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

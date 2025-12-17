# Copyright © 2021-2025 Technology Matters
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

import graphene

from ..models import ExportToken
from .types import ExportToken as ExportTokenType


class Query(graphene.ObjectType):
    all_export_tokens = graphene.Field(graphene.List(graphene.NonNull(ExportTokenType)))

    @staticmethod
    def resolve_all_export_tokens(root, info):
        """Get all export tokens for the current user."""
        user = info.context.user
        return ExportToken.objects.filter(user_id=str(user.id))

# Copyright © 2026 Technology Matters
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

import pytest
from django.db import InternalError
from mixer.backend.django import mixer

from apps.core.management.read_only import read_only_session
from apps.core.models import User

# transaction=True because the default db fixture runs each test inside an already-open transaction, which default_transaction_read_only doesn't affect.
pytestmark = pytest.mark.django_db(transaction=True)


def test_blocks_writes_then_restores_read_write():
    with read_only_session(), pytest.raises(InternalError, match="read-only transaction"):
        mixer.blend(User)

    mixer.blend(User)


def test_restores_read_write_when_block_raises():
    with pytest.raises(ValueError), read_only_session():
        raise ValueError

    mixer.blend(User)

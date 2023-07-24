from datetime import datetime, timedelta, timezone

import pytest

from apps.core.management.commands.harddelete import Command


@pytest.fixture
def deletion_gap():
    return Command.DEFAULT_DELETION_GAP


@pytest.fixture
def delete_date(deletion_gap):
    return datetime.now(timezone.utc) - (deletion_gap + timedelta(days=1))


@pytest.fixture
def no_delete_date(deletion_gap):
    return datetime.now(timezone.utc) - (deletion_gap - timedelta(days=1))

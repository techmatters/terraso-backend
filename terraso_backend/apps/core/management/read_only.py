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

from contextlib import contextmanager, suppress

from django.db import DatabaseError, connection


@contextmanager
def read_only_session():
    """Make the default DB connection refuse writes inside the block, as a guard for reporting commands run against staging/prod.

    Only transactions started inside the block are read-only, so it has no effect on one already open (e.g. inside atomic()).
    """
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = on")
    try:
        yield
    finally:
        # If the block failed on a DB problem, the RESET likely fails too; suppress it so the traceback ends on the original error.
        with suppress(DatabaseError), connection.cursor() as cursor:
            cursor.execute("RESET default_transaction_read_only")

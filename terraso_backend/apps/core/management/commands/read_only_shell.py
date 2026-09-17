from django.core.management.commands.shell import Command as ShellCommand
from django.db import connection


class Command(ShellCommand):
    help = (
        "Like 'shell', but the default DB connection is read-only. "
        "Use the regular 'shell' command to make changes."
    )

    def handle(self, **options):
        # Session-level (not transaction-scoped) so we don't hold a
        # long-running open transaction for the whole shell session.
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")

        try:
            super().handle(**options)
        finally:
            # Reset before the connection ever gets reused/returned to a pool.
            # Not needed against the current dev/prod setup (direct Postgres),
            # but insurance against future proxying connection poolers
            # (e.g. PgBouncer in transaction mode) sharing backends.
            try:
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:
                        cursor.execute("RESET default_transaction_read_only")
            except Exception:
                pass
            connection.close()

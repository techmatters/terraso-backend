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

"""
One-off migration: move customer field data that landed in the STAGING database
(because a public iOS build was compiled against staging) into PRODUCTION.

Reads from a second DB connection ("staging", configured via STAGING_DATABASE_URL)
and writes into the primary ("default") connection. See the migration runbook and
Phase 1 report kept with the ops artifacts for the full story. Key properties:

  * Row PKs (random UUIDs) are preserved, so all non-user foreign keys stay
    valid without any remapping.
  * The ONLY identity remap is user ids: staging users are matched to existing
    prod users by apple_sub -> email; matched users' data is re-pointed onto the
    prod user id, unmatched users are inserted fresh (PK preserved).
  * Timestamps (created_at/updated_at/...) are preserved by disabling auto_now
    during insert.
  * Idempotent: rows whose PK already exists in prod are skipped, so repeat
    passes (for stragglers still on the bad build) are safe.
  * DRY-RUN BY DEFAULT: everything runs inside a transaction that is rolled back
    unless --commit is passed. The dry run still exercises every INSERT, so
    constraint violations surface without persisting anything.

Rehearse locally against the two loaded DBs, e.g. (inside the web container):

    DATABASE_URL=postgres://postgres@db:5432/terraso_prod \\
    STAGING_DATABASE_URL=postgres://postgres@db:5432/terraso_staging \\
    python terraso_backend/manage.py merge_staging_to_prod --cutoff 2026-10-14
"""

import csv
import datetime
from contextlib import contextmanager

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.collaboration.models import Membership, MembershipList
from apps.core.models import User
from apps.core.models.users import UserPreference
from apps.e2e_tests.models import TestUser
from apps.project_management.models.projects import Project
from apps.project_management.models.site_notes import SiteNote
from apps.project_management.models.sites import Site
from apps.soil_id.models.depth_dependent_soil_data import DepthDependentSoilData
from apps.soil_id.models.project_soil_settings import ProjectDepthInterval, ProjectSoilSettings
from apps.soil_id.models.soil_data import SoilData, SoilDataDepthInterval
from apps.soil_id.models.soil_data_history import SoilDataHistory
from apps.soil_id.models.soil_metadata import SoilMetadata

DEFAULT_CUTOFF = "2026-10-14"

# Internal/testers excluded from the migration. Domains catch org accounts; the
# explicit list is for testers on personal addresses. Extend as the team
# confirms more (see the Phase 1 review list).
EXCLUDED_DOMAINS = {"terraso.org", "techmatters.org"}
EXCLUDED_EMAILS = {"derektestcaelin@gmail.com"}

# Models whose auto timestamps must be frozen so we can write the staging values.
TIMESTAMP_MODELS = [
    User,
    UserPreference,
    MembershipList,
    Membership,
    Project,
    Site,
    ProjectSoilSettings,
    ProjectDepthInterval,
    SoilData,
    SoilMetadata,
    SoilDataDepthInterval,
    DepthDependentSoilData,
    SiteNote,
    SoilDataHistory,
]

# Best-effort human-readable label per row for the --manifest CSV.
MANIFEST_LABELERS = {
    User: lambda d: d.get("email", ""),
    Site: lambda d: d.get("name", ""),
    Project: lambda d: d.get("name", ""),
    SiteNote: lambda d: (d.get("content") or "")[:50],
    UserPreference: lambda d: d.get("key", ""),
    Membership: lambda d: d.get("user_role", ""),
}
# Attnames checked (in order) to attribute a manifest row to a user.
MANIFEST_USER_ATTNS = ("user_id", "owner_id", "changed_by_id", "author_id", "saved_author")


@contextmanager
def preserve_timestamps(*models_):
    """Disable auto_now/auto_now_add on the given models so bulk_create writes
    the timestamp values we set on the instances instead of 'now'."""
    patched = []
    for m in models_:
        for f in m._meta.get_fields():
            if isinstance(f, models.DateTimeField) and (
                getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False)
            ):
                patched.append((f, f.auto_now, f.auto_now_add))
                f.auto_now = False
                f.auto_now_add = False
    try:
        yield
    finally:
        for f, auto_now, auto_now_add in patched:
            f.auto_now = auto_now
            f.auto_now_add = auto_now_add


class Command(BaseCommand):
    help = "Merge customer data misdirected to staging into the production DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cutoff",
            default=DEFAULT_CUTOFF,
            help=f"ISO date; staging users created on/after this are in scope (default {DEFAULT_CUTOFF}).",
        )
        parser.add_argument("--staging-alias", default="staging")
        parser.add_argument("--default-alias", default="default")
        parser.add_argument(
            "--exclude-email",
            action="append",
            default=[],
            help="Additional tester email to exclude (repeatable).",
        )
        parser.add_argument(
            "--exclude-file", help="Path to a newline-delimited file of tester emails to exclude."
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually persist. Without it, the run is a dry run (rolled back).",
        )
        parser.add_argument(
            "--manifest",
            help="Write a CSV of exactly which rows would be migrated to PATH, plus a "
            "per-user classification to PATH.users.csv. Works in dry-run.",
        )

    # ---- scope / classification ------------------------------------------

    def handle(self, *args, **opts):
        staging = opts["staging_alias"]
        default = opts["default_alias"]
        commit = opts["commit"]
        cutoff_date = parse_date(opts["cutoff"])
        if cutoff_date is None:
            raise CommandError(f"Invalid --cutoff: {opts['cutoff']!r}")
        # Make the boundary tz-aware (midnight in the project TZ) so it compares
        # cleanly against the tz-aware created_at columns.
        cutoff = timezone.make_aware(datetime.datetime.combine(cutoff_date, datetime.time.min))
        if staging not in connections.databases:
            raise CommandError(
                f"No '{staging}' DB connection. Set STAGING_DATABASE_URL (points at the "
                "staging DB) before running this command."
            )
        dflt_sd, stag_sd = connections[default].settings_dict, connections[staging].settings_dict
        if (dflt_sd["NAME"], dflt_sd["HOST"], dflt_sd["PORT"]) == (
            stag_sd["NAME"],
            stag_sd["HOST"],
            stag_sd["PORT"],
        ):
            raise CommandError(
                "Refusing to run: 'default' and 'staging' point at the same database."
            )

        excluded_emails = {e.lower() for e in EXCLUDED_EMAILS}
        excluded_emails.update(e.lower() for e in opts["exclude_email"])
        if opts["exclude_file"]:
            with open(opts["exclude_file"]) as fh:
                excluded_emails.update(line.strip().lower() for line in fh if line.strip())

        self.stdout.write(
            f"Cutoff: {cutoff_date}  |  mode={'COMMIT' if commit else 'DRY-RUN (rollback)'}"
        )
        self.stdout.write(f"  write -> default DB '{dflt_sd['NAME']}'")
        self.stdout.write(f"  read  <- staging DB '{stag_sd['NAME']}'")

        report = {}
        warnings = []
        self._manifest_enabled = bool(opts["manifest"])
        self._manifest_rows = []
        self._email_by_user = {}

        with preserve_timestamps(*TIMESTAMP_MODELS):
            with transaction.atomic(using=default):
                id_map, a_new, b_existing, ambiguous, backfills = self._classify(
                    staging, default, cutoff, excluded_emails, warnings
                )
                self._run_migration(staging, default, id_map, a_new, backfills, report, warnings)
                if not commit:
                    transaction.set_rollback(True)

        self._print_report(a_new, b_existing, ambiguous, backfills, report, warnings, commit)
        if opts["manifest"]:
            self._write_manifest(opts["manifest"], a_new, b_existing, ambiguous, backfills)

    def _classify(self, staging, default, cutoff, excluded_emails, warnings):
        """Return (id_map, a_new_users, b_existing[list of (staging_user, prod_id)],
        ambiguous[list], backfills[list of (prod_id, apple_sub)])."""
        test_user_ids = set(TestUser.objects.using(staging).values_list("user_id", flat=True))

        def is_excluded(email):
            email = (email or "").lower()
            if email in excluded_emails:
                return True
            domain = email.rsplit("@", 1)[-1] if "@" in email else ""
            return domain in EXCLUDED_DOMAINS

        scope_users = [
            u
            for u in User.objects.using(staging).filter(
                created_at__gte=cutoff, deleted_at__isnull=True
            )
            if u.id not in test_user_ids and not is_excluded(u.email)
        ]

        prod_by_email, prod_by_sub, prod_sub_of = {}, {}, {}
        for row in (
            User.objects.using(default)
            .filter(deleted_at__isnull=True)
            .values("id", "email", "apple_sub")
        ):
            prod_by_email[row["email"].lower()] = row["id"]
            prod_sub_of[row["id"]] = row["apple_sub"]
            if row["apple_sub"]:
                prod_by_sub[row["apple_sub"]] = row["id"]

        id_map, a_new, b_existing, ambiguous, backfills = {}, [], [], [], []
        for u in scope_users:
            by_sub = prod_by_sub.get(u.apple_sub) if u.apple_sub else None
            by_email = prod_by_email.get(u.email.lower())
            if by_sub and by_email and by_sub != by_email:
                ambiguous.append((u, by_sub, by_email))
                continue  # excluded from the migration; needs hand review
            prod_id = by_sub or by_email
            if prod_id:
                id_map[u.id] = prod_id
                b_existing.append((u, prod_id))
                # Backfill apple_sub onto the prod account when staging has one the
                # prod account lacks (and it is free) — needed because Apple omits
                # the email claim for already-authorized Services IDs, so the prod
                # account must carry the sub to be findable on the next login.
                if u.apple_sub and not prod_sub_of.get(prod_id) and u.apple_sub not in prod_by_sub:
                    backfills.append((prod_id, u.apple_sub))
            else:
                id_map[u.id] = u.id  # inserted fresh, PK preserved
                a_new.append(u)
        # Map each migrated row's (remapped) user id -> a human email, for the manifest.
        self._email_by_user = {u.id: u.email for u in a_new}
        self._email_by_user.update({prod_id: u.email for u, prod_id in b_existing})
        return id_map, a_new, b_existing, ambiguous, backfills

    # ---- migration -------------------------------------------------------

    def _run_migration(self, staging, default, id_map, a_new, backfills, report, warnings):
        scope_user_ids = set(id_map.keys())

        # A_new users (B_existing users already exist in prod — do NOT insert).
        self._copy(User, a_new, default, report, "core_user")

        # UserPreference for scope users; skip (key, user) that already exists in prod.
        prefs = list(UserPreference.objects.using(staging).filter(user_id__in=scope_user_ids))
        existing_pref_keys = set(
            UserPreference.objects.using(default)
            .filter(user_id__in=set(id_map.values()))
            .values_list("user_id", "key")
        )
        self._copy(
            UserPreference,
            prefs,
            default,
            report,
            "core_userpreference",
            hard_user={"user_id"},
            id_map=id_map,
            extra_skip=lambda o: (id_map.get(o.user_id), o.key) in existing_pref_keys,
        )

        # Projects the scope users belong to -> their membership lists.
        user_ml_ids = set(
            Membership.objects.using(staging)
            .filter(user_id__in=scope_user_ids, deleted_at__isnull=True)
            .values_list("membership_list_id", flat=True)
        )
        scope_projects = list(
            Project.objects.using(staging).filter(
                membership_list_id__in=user_ml_ids, deleted_at__isnull=True
            )
        )
        scope_project_ids = {p.id for p in scope_projects}
        scope_ml_ids = {p.membership_list_id for p in scope_projects}

        membership_lists = list(
            MembershipList.objects.using(staging).filter(
                id__in=scope_ml_ids, deleted_at__isnull=True
            )
        )
        self._copy(
            MembershipList, membership_lists, default, report, "collaboration_membershiplist"
        )

        memberships = list(
            Membership.objects.using(staging).filter(
                membership_list_id__in=scope_ml_ids, deleted_at__isnull=True
            )
        )
        self._copy(
            Membership,
            memberships,
            default,
            report,
            "collaboration_membership",
            hard_user={"user_id"},
            id_map=id_map,
            warnings=warnings,
            warn_unmapped="membership of in-scope project references a non-migrated user",
        )

        self._copy(Project, scope_projects, default, report, "project_management_project")
        self._copy_m2m_seen_by(Project, scope_project_ids, staging, default, id_map, report)

        # Sites: personal (owner in scope) or in an in-scope project.
        sites = list(
            Site.objects.using(staging)
            .filter(deleted_at__isnull=True)
            .filter(
                models.Q(owner_id__in=scope_user_ids) | models.Q(project_id__in=scope_project_ids)
            )
        )
        scope_site_ids = {s.id for s in sites}
        self._copy(
            Site,
            sites,
            default,
            report,
            "project_management_site",
            hard_user={"owner_id"},
            id_map=id_map,
            warnings=warnings,
            warn_unmapped="site owned by a non-migrated user",
        )
        self._copy_m2m_seen_by(Site, scope_site_ids, staging, default, id_map, report)

        # Soil settings / depth intervals under in-scope projects.
        settings = list(
            ProjectSoilSettings.objects.using(staging).filter(
                project_id__in=scope_project_ids, deleted_at__isnull=True
            )
        )
        settings_ids = {s.id for s in settings}
        self._copy(ProjectSoilSettings, settings, default, report, "soil_id_projectsoilsettings")
        self._copy(
            ProjectDepthInterval,
            list(
                ProjectDepthInterval.objects.using(staging).filter(
                    project_id__in=settings_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "soil_id_projectdepthinterval",
        )

        # Soil data under in-scope sites.
        soil_data = list(
            SoilData.objects.using(staging).filter(
                site_id__in=scope_site_ids, deleted_at__isnull=True
            )
        )
        soil_data_ids = {s.id for s in soil_data}
        self._copy(SoilData, soil_data, default, report, "soil_id_soildata")

        # Soil metadata (user's soil-match ratings / selected match) — 1:1 with
        # Site, no user FK, so the same site-scoped copy pattern as SoilData.
        self._copy(
            SoilMetadata,
            list(
                SoilMetadata.objects.using(staging).filter(
                    site_id__in=scope_site_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "soil_id_soilmetadata",
        )
        self._copy(
            SoilDataDepthInterval,
            list(
                SoilDataDepthInterval.objects.using(staging).filter(
                    soil_data_id__in=soil_data_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "soil_id_soildatadepthinterval",
        )
        self._copy(
            DepthDependentSoilData,
            list(
                DepthDependentSoilData.objects.using(staging).filter(
                    soil_data_id__in=soil_data_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "soil_id_depthdependentsoildata",
        )

        # Site notes (author SET_NULL/soft) and soil-data history (changed_by hard).
        self._copy(
            SiteNote,
            list(
                SiteNote.objects.using(staging).filter(
                    site_id__in=scope_site_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "project_management_sitenote",
            soft_user={"author_id", "saved_author"},
            id_map=id_map,
        )
        self._copy(
            SoilDataHistory,
            list(
                SoilDataHistory.objects.using(staging).filter(
                    site_id__in=scope_site_ids, deleted_at__isnull=True
                )
            ),
            default,
            report,
            "soil_id_soildatahistory",
            hard_user={"changed_by_id"},
            id_map=id_map,
            warnings=warnings,
            warn_unmapped="soil-data history changed_by a non-migrated user",
        )

        # apple_sub backfills onto matched prod users.
        done = 0
        for prod_id, sub in backfills:
            done += User.objects.using(default).filter(id=prod_id).update(apple_sub=sub)
        report["apple_sub_backfills"] = {"inserted": done, "source": len(backfills)}

    def _copy(
        self,
        model,
        instances,
        default,
        report,
        label,
        hard_user=None,
        soft_user=None,
        id_map=None,
        extra_skip=None,
        warnings=None,
        warn_unmapped=None,
    ):
        """Insert staging `instances` into `default`, preserving PKs/timestamps.
        hard_user attnames are remapped and the row is SKIPPED if unmapped;
        soft_user attnames are remapped or set None if unmapped (kept)."""
        hard_user = hard_user or set()
        soft_user = soft_user or set()
        pks = [o.pk for o in instances]
        existing = set(model.objects.using(default).filter(pk__in=pks).values_list("pk", flat=True))
        to_create, skipped_existing, skipped_unmapped, skipped_other = [], 0, 0, 0
        for o in instances:
            if o.pk in existing:
                skipped_existing += 1
                continue
            if extra_skip and extra_skip(o):
                skipped_other += 1
                continue
            data, ok = {}, True
            for f in model._meta.concrete_fields:
                v = getattr(o, f.attname)
                if v is not None and f.attname in hard_user:
                    mapped = id_map.get(v)
                    if mapped is None:
                        ok = False
                        break
                    v = mapped
                elif v is not None and f.attname in soft_user:
                    v = id_map.get(v)  # None if unmapped -> stale pointer cleared
                data[f.attname] = v
            if not ok:
                skipped_unmapped += 1
                if warnings is not None and warn_unmapped:
                    warnings.append(f"{label}: skipped row {o.pk} — {warn_unmapped}")
                continue
            to_create.append(model(**data))
            if self._manifest_enabled:
                self._manifest_rows.append(self._manifest_entry(model, label, data))
        model.objects.using(default).bulk_create(to_create)
        report[label] = {
            "source": len(instances),
            "inserted": len(to_create),
            "skipped_existing": skipped_existing,
            "skipped_unmapped": skipped_unmapped,
            "skipped_other": skipped_other,
        }

    def _copy_m2m_seen_by(self, model, scope_ids, staging, default, id_map, report):
        """Copy the seen_by M2M join rows. Auto-int PKs are NOT preserved (would
        clash with prod sequences); rows are deduped by (owner, user) pair."""
        through = model._meta.get_field("seen_by").remote_field.through
        src = next(f for f in through._meta.fields if f.is_relation and f.related_model is model)
        usr = next(f for f in through._meta.fields if f.is_relation and f.related_model is User)
        rows = list(through.objects.using(staging).filter(**{f"{src.attname}__in": scope_ids}))
        existing = set(
            through.objects.using(default)
            .filter(**{f"{src.attname}__in": scope_ids})
            .values_list(src.attname, usr.attname)
        )
        to_create, skipped = [], 0
        for r in rows:
            mapped_user = id_map.get(getattr(r, usr.attname))
            src_id = getattr(r, src.attname)
            if mapped_user is None or (src_id, mapped_user) in existing:
                skipped += 1
                continue
            to_create.append(through(**{src.attname: src_id, usr.attname: mapped_user}))
        through.objects.using(default).bulk_create(to_create)
        report[f"{model._meta.db_table}.seen_by"] = {
            "source": len(rows),
            "inserted": len(to_create),
            "skipped_existing_or_unmapped": skipped,
        }

    # ---- manifest --------------------------------------------------------

    def _manifest_entry(self, model, table_label, data):
        if model is User:
            user_email = data.get("email", "")
        else:
            uid = next((data[a] for a in MANIFEST_USER_ATTNS if data.get(a) is not None), None)
            user_email = self._email_by_user.get(uid, "")
        labeler = MANIFEST_LABELERS.get(model)
        return {
            "table": table_label,
            "pk": str(data.get("id", "")),
            "user": user_email,
            "label": labeler(data) if labeler else "",
        }

    def _write_manifest(self, path, a_new, b_existing, ambiguous, backfills):
        backfill_ids = {prod_id for prod_id, _ in backfills}
        with open(path, "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["table", "pk", "attached_user", "label"])
            for r in self._manifest_rows:
                wr.writerow([r["table"], r["pk"], r["user"], r["label"]])
        users_path = f"{path}.users.csv"
        with open(users_path, "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(
                ["classification", "email", "staging_user_id", "prod_user_id", "apple_sub_backfill"]
            )
            for u in a_new:
                wr.writerow(["A_new", u.email, u.id, u.id, ""])
            for u, prod_id in b_existing:
                wr.writerow(
                    ["B_existing", u.email, u.id, prod_id, "yes" if prod_id in backfill_ids else ""]
                )
            for u, by_sub, by_email in ambiguous:
                wr.writerow(["C_ambiguous", u.email, u.id, f"sub={by_sub};email={by_email}", ""])
        self.stdout.write(
            f"Manifest: {path} ({len(self._manifest_rows)} rows)  and  {users_path} "
            f"({len(a_new) + len(b_existing) + len(ambiguous)} users)"
        )

    # ---- reporting -------------------------------------------------------

    def _print_report(self, a_new, b_existing, ambiguous, backfills, report, warnings, commit):
        w = self.stdout.write
        w("")
        w("=" * 64)
        w("USER CLASSIFICATION")
        w("=" * 64)
        w(f"  A_new (inserted fresh):     {len(a_new)}")
        w(f"  B_existing (re-pointed):    {len(b_existing)}")
        w(f"  C_ambiguous (SKIPPED):      {len(ambiguous)}")
        w(f"  apple_sub backfills queued: {len(backfills)}")
        for u, by_sub, by_email in ambiguous:
            w(f"    ! ambiguous {u.email}: sub->{by_sub} email->{by_email}")
        w("")
        w("=" * 64)
        w("ROWS MIGRATED")
        w("=" * 64)
        w(f"  {'table':40s} {'src':>6} {'ins':>6} {'exist':>6} {'unmap':>6} {'other':>6}")
        for label, c in report.items():
            w(
                f"  {label:40s} {c.get('source', 0):6d} {c.get('inserted', 0):6d} "
                f"{c.get('skipped_existing', 0):6d} {c.get('skipped_unmapped', 0):6d} "
                f"{c.get('skipped_other', c.get('skipped_existing_or_unmapped', 0)):6d}"
            )
        if warnings:
            w("")
            w("=" * 64)
            w(f"WARNINGS ({len(warnings)})")
            w("=" * 64)
            for msg in warnings:
                w(f"  ! {msg}")
        w("")
        if commit:
            w("COMMITTED.")
        else:
            w("DRY RUN — transaction rolled back, no data changed.")

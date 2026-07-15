# User soft-delete — design and current state

This doc was written by Claude in 2026 July when the user deletion feature was first created.
It was updated as the feature was implemented, but no guarantees that it's up-to-date.

## TL;DR

When a User is soft-deleted (via Django admin, the GraphQL `UserDeleteMutation`, or a shell `user.delete()`):

- If the user has any **undeletable data** — a non-project APPROVED
  Group/Landscape membership, or any active PROTECT/RESTRICT reverse FK
  (Group, Landscape, TaxonomyTerm, VisualizationConfig, StoryMap, or
  DataEntry `created_by`) — the soft-delete is refused with
  `UserDeletionBlockedError`. The error message is generic and points at
  `make show-deletion-blockers user=<email>` for specifics. Callers
  (admin, GraphQL) surface it as a banner or fall through to the
  manual-cleanup HubSpot ticket flow.
- Otherwise → soft-delete. The user's landpks footprint cascades cleanly:
  unaffiliated owned sites (with their soil data, depth intervals, notes,
  push history) via `Site.owner = CASCADE`, sole-manager projects (with
  their sites and the project's MembershipList + Memberships) via an
  explicit cascade step.
- 30 days later the existing `harddelete` cron purges those rows.

The same gate applies to the GraphQL `UserDeleteMutation` so the mobile
"delete my account" flow behaves consistently.

This work only writes code that runs on the **soft-delete** path.
Hard-delete is the existing cron's job and is intentionally untouched.

## Background

### Soft-delete is mostly already in place

The codebase uses [`django-safedelete`](https://django-safedelete.readthedocs.io).
`BaseModel` ([core/models/commons.py](../terraso_backend/apps/core/models/commons.py))
is a `SafeDeleteModel` with `_safedelete_policy = SOFT_DELETE_CASCADE`.
Effectively every domain model extends `BaseModel`. `User`
([core/models/users.py](../terraso_backend/apps/core/models/users.py))
is also a `SafeDeleteModel` (not via `BaseModel`).

Tearing down related rows is mostly: "call `.delete()` on the right entry
points; the FK cascade handles the rest." The gate adds one explicit
step (sole-manager projects) where the schema can't express the cascade
we want.

### The harddelete cron is generic — and stays untouched

[harddelete.py](../terraso_backend/apps/core/management/commands/harddelete.py)
walks every model with a `deleted_at` field and hard-deletes rows past
the cutoff. Because all cleanup in this design happens at soft-delete
time, every row that should die is soft-deleted alongside the user and
the cron purges it on its own clock. **No cron changes required, and
the new gate does not fire on `force_policy=HARD_DELETE`** — keeping the
cron untouched and robust.

### Where this fits in the existing deletion flow

There is already an account-deletion _request_ path: a user sets the
`account_deletion_request` UserPreference to "true", which fires
`create_account_deletion_ticket()`
([core/hubspot.py](../terraso_backend/apps/core/hubspot.py)) and opens a
HubSpot support ticket. The team triages those tickets. **This work is
the automated execution step** for tickets where the user has no
undeletable data: instead of a fully-manual deletion, the user can
immediately soft-delete their account from the User Settings screen.
(Devs can also press the delete button in the Django admin panel to
similar effect.) Users _with_ undeletable data still fall back to
manual handling — same HubSpot ticket path, filed from the mutation's
catch branch.

### Schema prerequisites (as shipped)

Three schema changes ship alongside the gate:

1. **`Site.owner`** changed from `SET_NULL` to `CASCADE`. This was made
   `SET_NULL` recently by separate in-progress work (the "Deleted User"
   author handling) to let public unaffiliated sites survive their
   owner's deletion as orphans. We're deliberately overriding that here:
   a deleted user's unaffiliated sites should die with them, public ones
   included. `SiteNote.author` stays `SET_NULL` — notes on shared
   project sites must survive the author's deletion with the author
   nulled; that's a different scenario. The `site_owned_by_at_most_one`
   check constraint (added alongside the SET_NULL work to permit orphans)
   is re-tightened to `site_must_be_owned_once` (XOR) since no runtime
   path produces orphans under CASCADE.

2. **`ProjectSettings` is removed entirely.** The model was vestigial —
   its docstring said _"These settings are currently ignored, and might
   be removed later"_, no GraphQL exposure, zero references in
   `mobile-client` or `client-shared`. The `Project.settings` OneToOne
   was `PROTECT`, which would otherwise be the one PROTECT FK inside
   the user-deletion subtree; removing the model eliminates the FK and
   the risk together.

3. **`DataEntry.created_by` and `StoryMap.created_by`** migrated from
   `DO_NOTHING` to `PROTECT`. Motivated by two things: (a) DO_NOTHING
   silently passes safedelete's collector so the gate had to walk FKs
   manually to catch these, and (b) DO_NOTHING would leave dangling FKs
   at hard-delete time. PROTECT lets safedelete raise `ProtectedError`
   naturally, and the runtime gate now catches that instead of
   maintaining its own FK walker.

## Behavior specification

### Two-layer architecture: gate + diagnostic

```
                     ┌────────────────────────────────┐
                     │        User.delete()           │
                     │   1. HARD_DELETE bypass        │
                     │   2. Membership policy check   │
                     │   3. super().delete() in       │
                     │      try / except              │
                     │      (Protected/RestrictedErr) │
                     └──────────────┬─────────────────┘
                                    │ raises
                                    ▼
                     ┌────────────────────────────────┐
                     │  UserDeletionBlockedError      │
                     │  (generic message pointing at  │
                     │   show_deletion_blockers cmd)  │
                     └──────┬───────────────────┬─────┘
                            │                   │
                       caught by            caught by
                            ▼                   ▼
                 ┌───────────────┐    ┌──────────────────────┐
                 │ UserAdmin     │    │ UserDeleteMutation   │
                 │ .delete_model │    │ (fires HubSpot ticket│
                 │ .delete_queryset  │ + sets pending pref)  │
                 │ (red banner)  │    │                      │
                 └───────────────┘    └──────────────────────┘

     Separate, not called at runtime:
     ┌─────────────────────────────────────────────────────┐
     │ show_deletion_blockers management command           │
     │ - Uses Django's NestedObjects collector directly    │
     │ - Reads _non_project_approved_memberships()         │
     │ - Same sources the gate reads from → can't drift    │
     └─────────────────────────────────────────────────────┘
```

**Rationale:** the runtime path only needs to know _whether_ to refuse.
Enumerating _which rows_ is a diagnostic concern — support / engineers
run it out-of-band before manual cleanup. Keeping that logic out of
`User.delete()` means the gate has no FK-classification code of its own
to maintain, and by construction the diagnostic can't disagree with the
gate.

### The gate — `User.delete()`

Two block sources:

1. **Non-project APPROVED Memberships.** `Membership.user` is CASCADE at
   the DB layer so safedelete's collector won't raise for them, but
   Group/Landscape membership is web-side data we don't want silently
   dropped. Checked upfront in `User.delete()` via
   `_non_project_approved_memberships()`.

2. **PROTECT/RESTRICT reverse FKs.** `safedelete`'s
   `soft_delete_cascade_policy_action` uses Django's `NestedObjects`
   collector; when it finds an active protected row, it raises
   `ProtectedError` (or `RestrictedError`) from `super().delete()`. We
   catch that and re-raise as our own `UserDeletionBlockedError`.

`force_policy=HARD_DELETE` bypasses the gate entirely — that path
belongs to the cron and must stay robust.

### The exception

```python
class UserDeletionBlockedError(ValidationError):
    """Raised by `User.delete()` (soft path) when the user has data that
    would block deletion — either a policy blocker (non-project APPROVED
    Membership) or a PROTECT/RESTRICT reverse FK that safedelete's
    collector refused.

    Details of what's blocking aren't carried on the exception; callers
    who need them run the `show_deletion_blockers` management command.
    """
```

The exception has no structured payload. Callers who catch it only need
the fact of the block (mutation → fall back to manual flow; admin →
show banner). Enumeration is out of band.

### Defining "undeletable data" — the rule

A user is blocked from soft-delete if either:

1. Any active row is reachable from the user via a PROTECT/RESTRICT FK
   (directly on a reverse FK to User, or transitively through the
   cascade tree — Django's `NestedObjects` walks the whole thing).
2. Any active non-project APPROVED `collaboration.Membership` exists
   pointing at the user.

Rule 1 is enforced by safedelete's collector; the gate doesn't have to
know which specific FKs count. Rule 2 is a policy override — CASCADE at
the DB layer, but semantically undeletable at our layer.

### How this maps onto the current schema

| Relation                                                        | on_delete | Result                              | Why                                                  |
| --------------------------------------------------------------- | --------- | ----------------------------------- | ---------------------------------------------------- |
| `core.UserPreference.user`                                      | CASCADE   | allow                               | safe + infra                                         |
| `core.BackgroundTask.created_by`                                | CASCADE   | allow                               | safe + infra                                         |
| `core.Group.created_by`                                         | PROTECT   | **block**                           | undeletable web data                                 |
| `core.Landscape.created_by`                                     | PROTECT   | **block**                           | undeletable web data                                 |
| `core.TaxonomyTerm.created_by`                                  | PROTECT   | **block**                           | undeletable web data                                 |
| `shared_data.DataEntry.created_by`                              | PROTECT   | **block**                           | undeletable web data                                 |
| `shared_data.VisualizationConfig.created_by`                    | PROTECT   | **block**                           | undeletable web data                                 |
| `story_map.StoryMap.created_by`                                 | PROTECT   | **block**                           | undeletable web data                                 |
| `collaboration.Membership.user`                                 | CASCADE   | **block** if non-project + APPROVED | policy override                                      |
| `core.Membership.user` (deprecated)                             | CASCADE   | allow                               | deprecated system; lingering rows are CASCADE-safe   |
| `MembershipList.members`, `Group.members`, `Site.seen_by` (M2M) | —         | allow                               | auto-cleaned through-rows                            |
| `project_management.*`, `soil_id.*`                             | various   | allow                               | explicit cascade in `User._soft_delete_with_cascade` |
| `auth.*`, `admin.LogEntry`, `sessions.*`                        | various   | allow                               | Django internals                                     |

### The gate — code sketch

```python
class UserDeletionBlockedError(ValidationError):
    """Generic block signal; details via show_deletion_blockers."""


class User(SafeDeleteModel, AbstractUser):
    def delete(self, *args, **kwargs):
        if kwargs.get("force_policy") == HARD_DELETE:
            return super().delete(*args, **kwargs)

        if self._special_blockers_exist():
            raise UserDeletionBlockedError(self._blocked_message())

        try:
            result = self._soft_delete_with_cascade(*args, **kwargs)
        except (ProtectedError, RestrictedError):
            logger.warning(
                "user.delete_blocked",
                target_user_id=str(self.id),
                reason="protected_fk",
            )
            raise UserDeletionBlockedError(self._blocked_message())

        logger.info("user.soft_deleted", target_user_id=str(self.id))
        return result

    def _special_blockers_exist(self):
        """Wrapper for non-on_delete-derived blockers. Currently just the
        non-project APPROVED Membership check; kept as a named seam so
        future policy blockers can slot in without touching delete()."""
        if self._non_project_approved_memberships().exists():
            logger.warning(
                "user.delete_blocked",
                target_user_id=str(self.id),
                reason="non_project_approved_membership",
            )
            return True
        return False

    def _non_project_approved_memberships(self):
        from apps.collaboration.models import Membership
        return self.collaboration_memberships.filter(
            membership_list__project__isnull=True,
            membership_status=Membership.APPROVED,
        )

    def _blocked_message(self):
        return (
            f"Cannot delete user {self.email!r}: undeletable data exists. "
            f"For details, run 'python manage.py show_deletion_blockers {self.email}' "
            f"or 'make show-deletion-blockers user={self.email}'."
        )
```

### The diagnostic command — `show_deletion_blockers`

Not called at runtime. Support / engineers use it to enumerate a specific
user's blockers before manual cleanup.

**Usage:**

```
make show-deletion-blockers user=foo@example.com   # local dev
python manage.py show_deletion_blockers foo@example.com   # production shell
```

**Implementation:** the command uses Django's `NestedObjects` collector
directly (the same source safedelete raises `ProtectedError` from) plus
`user._non_project_approved_memberships()` (the same method the gate
uses). No parallel FK-classification logic to drift. Output shape:

```
Deletion blockers for 'foo@example.com':
  - shared_data.DataEntry (created_by): 3 row(s); IDs: abc, def, ghi
  - collaboration.Membership (non-project, approved) (user): 1 row(s); IDs: xyz
```

Blocker dicts are `{model, qualifier, field, count, ids}`. `ids` is
capped at `BLOCKER_ID_CAP = 50`; `count` is the true total for the
"+N more" hint when truncated.

### Mandatory structural tests (CI drift detectors)

Both live in `tests/core/models/test_user_deletion_gate.py`:

**Test A: every reverse FK to User is correctly classified.** Iterate
`User._meta.related_objects`, assert each falls into exactly one bucket:

1. LandPKS app (`LANDPKS_APP_LABELS`) — orchestrated explicitly in
   `_soft_delete_with_cascade` / `Project.soft_delete_policy_action`.
2. System app (`SYSTEM_APP_LABELS`) — Django internals.
3. `collaboration.Membership.user` — policy special case.
4. `CASCADE` / `SET_NULL` / `SET_DEFAULT` / `SET(...)` — auto-allowed
   (referentially safe).
5. `PROTECT` / `RESTRICT` — auto-blocked (safedelete raises).

M2M reverse relations are also iterated and asserted to be skipped. The
test additionally asserts **no DO_NOTHING FKs to User outside
LANDPKS_APP_LABELS** — new blockers must use PROTECT so safedelete's
collector raises them (DO_NOTHING silently passes and would leave the
harddelete cron holding a dangling ref).

The `BLOCKING_ON_DELETE`, `LANDPKS_APP_LABELS`, and `SYSTEM_APP_LABELS`
constants live in the test file, since after the diagnostic-command
refactor no runtime code path reads them.

**Test B: the user-deletion closure is hard-delete-safe.** Walk the
transitive closure of models soft-deleted by `user.delete()`. For every
closure model, assert no incoming FK is PROTECT / RESTRICT / DO*NOTHING
— such an FK could raise ProtectedError (ORM) or IntegrityError (DB)
when the harddelete cron later purges the closure. The soft-delete gate
catches PROTECT/RESTRICT via safedelete's collector, but the closure
test also protects against FKs added \_during* someone's grace window
(where the cron sees them but the gate is already past).

Together these prove the schema can't drift into a state where the gate
either over-blocks (Test A) or under-protects (Test B).

### Cascade scope (when delete proceeds)

Inside `User._soft_delete_with_cascade`, after the gate has cleared:

1. **Unaffiliated sites**: handled by the default cascade via
   `Site.owner = CASCADE`. Safedelete's `SOFT_DELETE_CASCADE` on User
   soft-deletes all owned sites, which cascade to SoilData →
   SoilDataDepthInterval / DepthDependentSoilData, SoilMetadata,
   SiteNote, SitePushHistory, SoilDataHistory. **No explicit loop
   needed.** (By the existing check constraint, `owner=self` ⟹ `project`
   is null, so this covers exactly the unaffiliated set.)

2. **Sole-manager projects**: explicitly soft-deleted in a Python loop.
   `Project.soft_delete_policy_action` (added in this work) cleans up
   the project's MembershipList; the default cascade handles its Sites
   and ProjectSoilSettings.

3. **Surviving sites and notes** (project-affiliated sites; projects
   with co-managers): the user's Membership is soft-deleted by the
   default cascade (`Membership.user` is CASCADE + SafeDeleteModel).
   `SiteNote.author` on surviving rows is nulled by its `SET_NULL` FK —
   no extra code needed.

### Inside `Project.soft_delete_policy_action`

`Project.membership_list` is a forward `OneToOneField` (FK column lives
on Project), so neither Django's collector nor safedelete's
`SOFT_DELETE_CASCADE` reach it when the Project is deleted. The cleanup
lives in `Project.soft_delete_policy_action` so it holds for **every**
project deletion path (user-deletion cascade, admin bulk soft-delete,
future code) — safedelete's `SafeDeleteQueryset.delete()` iterates and
calls per-instance `.delete()`, which invokes the override.

Order matters: soft-delete the Project first (cascades to Sites and the
soil-settings subtree), then soft-delete the now-orphaned MembershipList
(cascades to its Memberships). Doing it the other way would have the
MembershipList's `CASCADE` toward Project try to soft-delete the Project
a second time.

### Special cases (or lack thereof)

**DataEntry re-link** (removed) — the old `soft_delete_policy_action`
re-attached `DataEntry.created_by` to the soft-deleted user. Under the
gate, any user with active DataEntries is refused, so this branch is
unreachable on the success path. The re-link is gone.

**Site notes** — `SiteNote.author` is `on_delete=SET_NULL`. When the
user is hard-deleted, every SiteNote they authored has `author` nulled
automatically. Notes on the user's own unaffiliated sites die with those
sites (`SiteNote.site` is CASCADE).

**Project pinned note** — `Project.site_instructions` is a plain
`TextField` on Project. **It has no author column.** Either the project
soft-deletes with the user (sole-manager case, note goes with it) or the
project survives (text survives, no one to null). Nothing to do.

**Note on undelete** — `SiteNote.author` is blanked by the `SET_NULL` cascade when the user soft-deletes, but the author id is stashed into `SiteNote.saved_author` first (in `User._soft_delete_with_cascade`), so `User.undelete()` restores the author and clears the shadow. Only a hard-delete makes the anonymization permanent (the user row is gone).

### Logging

Both outcomes emit a structured log line via `structlog`.
`django_structlog` attaches `request_id` and the requesting `user_id` to
every line, so we only need the target and the result:

- On successful soft-delete:
  `logger.info("user.soft_deleted", target_user_id=str(self.id))`
- On refusal:
  `logger.warning("user.delete_blocked", target_user_id=str(self.id), reason="non_project_approved_membership" | "protected_fk")`

The `reason` field distinguishes the two block paths without leaking row-
level data — engineers who need row-level detail run the diagnostic.

Logs render as JSON to stdout and warnings/errors also reach Sentry.

## Implementation (as shipped)

### Schema changes

Three FK moves and one new column: `Site.owner` (SET_NULL → CASCADE, with
its check constraint re-tightened to XOR); `DataEntry.created_by` and
`StoryMap.created_by` (DO_NOTHING → PROTECT); `ProjectSettings` model +
`Project.settings` field dropped; and a `SiteNote.saved_author` shadow
column added so `User.undelete()` can restore authorship that the
`SET_NULL` cascade would otherwise blank out (see "Note on undelete" above).

### Files touched

**The gate** lives on `User.delete()`: `_special_blockers_exist()` for
the Membership policy check, a try/except around `super().delete()` for
PROTECT/RESTRICT, and `_soft_delete_with_cascade()` which owns the
sole-manager-project loop and the `SiteNote.saved_author` stash.
`User.undelete()` restores both. `request_account_deletion(user)` is the
pref+ticket side-effect the mutation calls on the blocked branch.

**Callers** wrap the gate with per-surface UX. `UserAdmin` — single and
bulk delete surface a banner pointing at the diagnostic command;
per-user try/except so a batch keeps going past blocked users.
`UserDeleteMutation` — blocked branch fires the ticket, returns
`user=null`; clean branch returns the user; no `blockers` payload
field (client only needs which branch fired). `create_account_deletion_ticket`
renders identity-only (name + email + subject); support runs the
diagnostic for row detail.

**The diagnostic** is `apps/core/management/commands/show_deletion_blockers.py`,
invoked as `make show-deletion-blockers user=<email>` (dev) or
`python manage.py show_deletion_blockers <email>` (prod). Uses Django's
`NestedObjects` collector plus `_non_project_approved_memberships()` — the
same two sources the gate reads from, so it can't drift.

**Model changes**: `Project.soft_delete_policy_action` for MembershipList
cleanup; `SiteNote.saved_author` UUID field; `ProjectSettings` gone.

### Tests

Model layer (`tests/core/models/test_user_deletion_gate.py`):

- Structural Test A: every reverse FK to User is classified into one of
  the five buckets; no DO_NOTHING FKs outside `LANDPKS_APP_LABELS`.
- Structural Test B: the user-deletion closure has no incoming
  PROTECT/RESTRICT/DO_NOTHING FKs.
- `User.delete()` raises `UserDeletionBlockedError` for a user with any
  kind of blocker.
- `User.delete()` succeeds for a landpks-only user.
- `force_policy=HARD_DELETE` bypasses the gate — proves the cron path
  is unaffected.
- **Behavioral cascade test**: full nested footprint (sole-managed
  project → MembershipList + Memberships → sites → soil data → notes),
  soft-delete the user, assert the whole subtree comes down.
- Sole-manager detection: sole, co-managed, non-manager.
- **`Project.soft_delete_policy_action` cleans up MembershipList**:
  directly soft-delete a Project, assert MembershipList + Memberships
  soft-deleted.

Diagnostic command (`tests/core/commands/test_show_deletion_blockers.py`):

- Per-blocker-kind coverage: DataEntry, VisualizationConfig, StoryMap,
  Group.created_by, Landscape.created_by, TaxonomyTerm.created_by,
  non-project APPROVED Membership.
- Negative cases: pending Membership doesn't block, project Membership
  doesn't block, soft-deleted referencer doesn't block, LandPKS-only
  user has no blockers.
- ID cap enforcement.
- Command E2E: email lookup, ID lookup, error paths, output format.

Cron resilience (`tests/core/commands/test_harddelete.py`):

- Parametrized over all 6 blocker models — soft-delete the referencer,
  then the user, assert both are gone within 2 cron runs.

Presentation layer (`tests/graphql/test_user_deletion_gate.py`):

- Mutation clean-delete returns the user.
- Mutation blocked-delete returns `user=null` and fires the HubSpot
  ticket + pending pref.
- HubSpot-down branch layers a `TicketCreationError` into the payload.
- Admin single-delete: `delete_view` fires the diagnostic banner;
  `delete_model` surfaces a "run script" banner and doesn't delete.
- Admin bulk-delete: `get_actions` wraps `delete_selected` to fire the
  banner; `delete_queryset` partitions clean vs. blocked.

HubSpot (`tests/core/test_hubspot.py`):

- Ticket body is identity-only; no blocker rendering.
- Dry-run + no-email short-circuits.

## Open questions

None blocking. Coordination items resolved:

1. **`Site.owner` → CASCADE**: coordinated with the Deleted-User author
   work; public unaffiliated sites intentionally die with their owner.
2. **Runbook for manual cleanup**: lives in the team wiki, not code.
3. **Mobile copy revision**: `TODO(designer)` markers ship on affected
   strings; revised copy in a follow-up.

## Settled decisions (do not re-litigate)

- **"Undeletable data" is defined by two things** — safedelete's
  collector output (PROTECT/RESTRICT) plus one explicit policy override
  (non-project APPROVED Membership). No parallel FK-classification code
  in the gate; the gate reuses safedelete's collector as source of
  truth.
- **The exception carries no structured payload.** Callers get a
  message pointing at the diagnostic command; they don't get a
  `blockers=[...]` array to render. This was tried; nothing consumed
  the structured list beyond a boolean check.
- **Gate fires only on soft-delete**, not on `force_policy=HARD_DELETE`.
  The cron path stays robust; cleanup happens at the soft-delete
  boundary by design.
- **`Site.owner` → CASCADE**, drop the explicit unaffiliated-sites loop.
  Public unaffiliated sites die with their owner alongside private ones.
- **`ProjectSettings` removed entirely** — model + table + FK + admin +
  save-time autocreate. Eliminates the only PROTECT FK inside the
  user-deletion subtree.
- **`DataEntry.created_by` and `StoryMap.created_by`** migrated
  DO_NOTHING → PROTECT. Aligns them with the other 4 web-data blockers
  and lets safedelete's collector raise for them so the gate has no
  DO_NOTHING special case.
- **MembershipList cleanup lives in `Project.soft_delete_policy_action`**,
  not in the user cascade. Holds for every project-deletion path
  (safedelete queryset honors per-instance `.delete()`). No `post_delete`
  signal — soft-delete is the only event that matters.
- **DataEntry re-link removed** from `User.soft_delete_policy_action`.
  Under the gate, any user with DataEntries is refused; re-link
  unreachable.
- **Pending memberships don't block**: only APPROVED, non-project
  memberships count (`Membership.user` is CASCADE so pending invites
  are hard-delete-safe regardless).
- **Refuse rather than partially-delete** when a user has undeletable
  data. Manual cleanup via the existing HubSpot-ticket flow.
- **Sole-manager semantics**: count only `membership_status=APPROVED`,
  non-soft-deleted Memberships. Exclude `pending_email`-only invites.
- **No "project-level notes" special case.** `Project.site_instructions`
  has no author; nothing to null.
- **Both structural tests are part of the deliverable**, not
  "nice to have."
- **Enumeration lives in a diagnostic command**, not in the User model.
  The command uses Django's `NestedObjects` and the same
  `_non_project_approved_memberships` method the gate uses, so its
  output is by-construction consistent with the gate.
- **Blocker shape (internal to the command) is `{model, qualifier,
field, count, ids}`.** `qualifier` is Optional[str] (used by the
  Membership override). `ids` is capped at `BLOCKER_ID_CAP = 50`;
  `count` is the true total. Renderers compute "+N more" from
  `count - len(ids)`.
- **Blockers are NOT displayed in-app.** Mobile shows the same generic
  pending screen as today regardless of whether the user was blocked or
  just requesting support handling.
- **`request_account_deletion(user)` is the shared side-effect helper.**
  Sets the pref + files the HubSpot ticket exactly once (no-op if pref
  is already `"true"`). Called by `UserPreferenceUpdate(ACCOUNT_DELETION,
"true")` for legacy clients and by `UserDeleteMutation`'s blocked
  branch. Caller is responsible for permission gating.
- **HubSpot ticket body is identity-only** (name + email + subject).
  Support runs `show_deletion_blockers` out-of-band for row-level
  detail. Keeping row detail out of the ticket body means support has
  one canonical enumeration source (the command) and no risk of the
  ticket showing stale data if rows are cleaned up between ticket
  filing and triage.
- **Mobile clean-delete UX**: sign out → route to login → "Account
  deleted" modal. No second confirmation screen after the mutation
  succeeds.
- **Mobile blocked-delete UX**: route to existing
  `DeleteAccountPendingContent` screen. No blocker rendering on mobile.
  Matches the existing pref-update flow exactly.
- **Re-authentication is handled by existing model design.** JWT
  middleware bounces soft-deleted users by default (SafeDelete default
  manager); `unique_active_email` constraint is conditional on
  `deleted_at IS NULL` so re-signup with the same email creates a
  fresh active user; no new code needed for either case.
- **`UserDeleteMutation` catches `UserDeletionBlockedError` only** —
  not generic `ValidationError` or other exceptions. Other exceptions
  surface for Sentry.
- **Admin confirmation-page banner** fires from `delete_view`
  (single-delete) and a wrapped `delete_selected` action (bulk),
  pointing staff at `show_deletion_blockers`. Django's default
  "protected related objects" list still renders below but may be
  incomplete or misleading — the banner directs staff to the canonical
  source.
- **Harddelete cron is resilient to per-row failures.** Each iteration:
  sort by `deleted_at`, wrap `obj.delete(force_policy=HARD_DELETE)` in
  `transaction.atomic()`, broad `try/except`, structured
  `harddelete.row_failed` log. Proxy models skipped in `all_objects()`.
- **"Account deleted" modal copy includes the deleted email.**
  Pass-through via navigation state.
- **Delete account button is disabled when offline.** Mobile mutations
  aren't queue-safe.

## Concerns and risks

1. **`SoilDataHistory.changed_by` and `SitePushHistory.changed_by` are
   `CASCADE` to User**. When a landpks-only user is hard-deleted, those
   audit-log rows disappear with them. Open question for product: is
   that desired? Behaviorally fine for now; flag for future.

2. **Concurrent edits / double-delete**. `_soft_delete_with_cascade` is
   wrapped in `transaction.atomic`; soft-delete is idempotent (setting
   `deleted_at` twice is harmless), so concurrent attempts converge.
   `select_for_update` is available if this ever surfaces.

3. **Sole-manager detection performance**. For a user in many projects,
   naive iteration is N+1. Handled: single annotated query
   (`_solo_manager_projects`) annotates each project's manager
   Membership count and filters to count == 1 with user present.

4. **`Site` check constraint**. The `site_must_be_owned_once` constraint at
   [sites.py](../terraso_backend/apps/project_management/models/sites.py)
   enforces XOR: exactly one of `owner`/`project` must be set. With
   `owner=CASCADE` and `project=CASCADE`, no runtime path can produce an
   orphan, so the tighter invariant holds — `Site.is_unaffiliated`
   (`owner is not None`) and any caller inferring "affiliated ⇒ has
   project" stay sound.

5. **`hard_delete_soft_deleted` admin action**. Calls
   `.delete(force_policy=HARD_DELETE)`. The gate does NOT fire there.
   If staff use that action on an already-soft-deleted user whose
   dependencies still exist, the underlying schema behavior applies —
   PROTECT rows would raise ProtectedError. Pre-existing risk this work
   doesn't change. If gating that action ever becomes important,
   override the action itself (not the model's `delete()`).

6. **Apple `apple_sub` collision on undelete** (minor). `User.undelete()`
   checks for email collisions but not `apple_sub`. Very unlikely; not
   in scope.

7. **Shell users get raw `UserDeletionBlockedError`**. A developer
   running `user.delete()` in the shell sees the exception message,
   which points at the diagnostic command. Acceptable.

8. **Distant-app drift not caught by structural tests (the "A3" gap).**
   Structural Test A is one layer deep (direct reverse FKs from User);
   Structural Test B walks the user-deletion closure. A future web-data
   app that adds a `CASCADE` FK to User but has `PROTECT` / `DO_NOTHING`
   between its own models is not classified by either test. At runtime
   safedelete's collector _does_ walk the cascade tree, so the gate
   would still refuse via `ProtectedError`. The cron's per-row
   resilience makes this gap less load-bearing than it used to be.

## Self-service deletion (mobile-client)

### What the user sees

Today the mobile "Delete account" button in `UserSettingsScreen` opens
`DeleteAccountScreen`, the user types their email to confirm, and
submitting fires `UserDeleteMutation`. Two outcomes:

- **No blockers** → soft-delete runs immediately (cascade tears down
  LandPKS data + Terraso data). Mobile signs the user out, routes to the
  login screen, and shows an **"Account deleted"** modal. They cannot
  log back in to that account; if they OAuth with the same email, they
  get a fresh empty account (allowed by the `unique_active_email`
  conditional constraint on `User`).
- **Blockers present** → backend calls `request_account_deletion(user)`
  (sets the pref + files the HubSpot ticket, idempotently). Mutation
  returns `user=null`. Mobile shows the existing
  `DeleteAccountPendingContent` screen and the settings indicator flips
  to "Pending". This matches the legacy pref-update UX exactly — the
  user sees no UX difference between "blocked self-delete" and "explicit
  support-ticket request."

Blocker details are not displayed in-app — the user sees the same generic
pending screen as today. Blockers are looked up by support via
`show_deletion_blockers` when they triage the HubSpot ticket.

### Re-authentication is handled by existing model design (no new code)

Three sub-questions verified during planning:

- **Other devices**: `JWTAuthenticationMiddleware._get_user` uses
  `User.objects.get(pk=user_id)`, which goes through SafeDelete's default
  manager and excludes soft-deleted users. Existing JWTs on other
  devices fail on the next request with `User.DoesNotExist` →
  `ValidationError("User not found for JWT token")`.
- **Re-signup**: The `unique_active_email` constraint is conditional on
  `deleted_at IS NULL`. A soft-deleted user with email X does not block
  a new active user with the same email. OAuth login calls
  `User.objects.get_or_create(email=email)`; the soft-deleted user is
  filtered out by SafeDelete, a fresh active user is created. Same for
  `apple_sub` via `unique_active_apple_sub`.
- **Pending-pref users (legacy)**: today's pending users can still log
  in (they aren't deleted yet — they see the pending screen). New
  instant-delete users can't log in at all. Different UX paths but
  consistent with what each actually represents.

### client-shared / mobile-client

- `client-shared/src/account/accountService.ts` — `deleteUserAccount()`
  returns `{ kind: 'deleted'; email } | { kind: 'blocked' }`. No
  structured payload on the blocked branch.
- `client-shared/src/account/accountSlice.ts` — the fulfilled reducer
  only inspects `kind`; on `'blocked'` it flips the local pending pref
  so `isPending` becomes true and the screen re-renders as pending
  content.
- `mobile-client/dev-client/src/hooks/userDeletionRequest.ts` — on
  `'deleted'`, dispatches `userLoggedOut` + `signOut` +
  `setAccountDeletedEmail`. On `'blocked'`, no imperative work — the
  slice reducer already flipped the pref.

## Quick code reference

| Where                                                                                                                            | What lives there                                                                                                                                                    |
| -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [core/models/users.py](../terraso_backend/apps/core/models/users.py)                                                             | `User.delete()`, `_non_project_approved_memberships`, `_soft_delete_with_cascade`, `_solo_manager_projects`, `UserDeletionBlockedError`, `request_account_deletion` |
| [core/admin.py](../terraso_backend/apps/core/admin.py)                                                                           | `UserAdmin.delete_view`, `get_actions`, `delete_model`, `delete_queryset`                                                                                           |
| [core/models/commons.py](../terraso_backend/apps/core/models/commons.py)                                                         | `BaseModel = SafeDeleteModel` foundation                                                                                                                            |
| [core/management/commands/show_deletion_blockers.py](../terraso_backend/apps/core/management/commands/show_deletion_blockers.py) | Diagnostic command — collector-based enumeration                                                                                                                    |
| [core/management/commands/harddelete.py](../terraso_backend/apps/core/management/commands/harddelete.py)                         | Generic cron — untouched                                                                                                                                            |
| [core/hubspot.py](../terraso_backend/apps/core/hubspot.py)                                                                       | `create_account_deletion_ticket` — identity-only body                                                                                                               |
| [project_management/models/sites.py](../terraso_backend/apps/project_management/models/sites.py)                                 | `Site.owner = CASCADE`                                                                                                                                              |
| [project_management/models/projects.py](../terraso_backend/apps/project_management/models/projects.py)                           | `Project.soft_delete_policy_action` (MembershipList cleanup); ProjectSettings removed                                                                               |
| [collaboration/models/memberships.py](../terraso_backend/apps/collaboration/models/memberships.py)                               | `Membership`, `MembershipList`                                                                                                                                      |
| [graphql/schema/users.py](../terraso_backend/apps/graphql/schema/users.py)                                                       | `UserDeleteMutation` — catches `UserDeletionBlockedError`, falls back to `request_account_deletion`                                                                 |
| [shared_data/models/data_entries.py](../terraso_backend/apps/shared_data/models/data_entries.py)                                 | `DataEntry.created_by = PROTECT` (was DO_NOTHING)                                                                                                                   |
| [story_map/models/story_maps.py](../terraso_backend/apps/story_map/models/story_maps.py)                                         | `StoryMap.created_by = PROTECT` (was DO_NOTHING)                                                                                                                    |

## Out of scope

- Cascading deletion of undeletable data (Groups, Landscapes, StoryMaps,
  DataEntries, VisualizationConfigs, TaxonomyTerms). Explicitly deferred;
  manual via HubSpot ticket.
- Migrating PROTECT FKs (`Group.created_by`, `Landscape.created_by`,
  `TaxonomyTerm.created_by`, `VisualizationConfig.created_by`) to
  `SET_NULL`. Not needed — the gate prevents reaching hard-delete on
  users with rows pointing through those FKs.
- A snapshot/audit table of what was cascaded.
- Gating the `undelete_selected` and `hard_delete_soft_deleted` admin
  bulk actions. The gate is soft-delete-only by design (see Concerns #5).
- An "author" / "last editor" tracker on `Project.site_instructions`.
- Hard-delete-time logic of any kind. The cron is untouched.
- **Web-client user-deletion pathway.** No existing flow and no plans
  to add one.
- **In-app rendering of blocker details.** Mobile shows the generic
  pending screen, not a list of what's blocking. Future iteration if
  product wants self-service resolution of blockers.
- **In-app resolution affordances** for blockers (transfer manager
  role, leave group, delete story map, etc.). Phase 2 if product wants
  in-app self-service blocker cleanup; today blocked users are routed
  to HubSpot.

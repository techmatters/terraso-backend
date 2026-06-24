# User soft-delete from Django admin — design plan

## TL;DR

When a staff member presses **Delete** on a User in the Django admin panel:

- If the user has any **undeletable data** (Group, Landscape, TaxonomyTerm, DataEntry, StoryMap, VisualizationConfig, or non-project Group/Landscape memberships) → refuse the soft-delete with a clear error listing _exactly_ which models and how many rows are blocking it. Point at a runbook for manual cleanup.
- Otherwise → soft-delete the user. The user's landpks footprint cascades cleanly: unaffiliated owned sites (with their soil data, depth intervals, notes, push history) via `Site.owner = CASCADE`, sole-manager projects (with their sites and the project's MembershipList + Memberships) via an explicit cascade step.
- 30 days later the existing `harddelete` cron purges those rows. No cron changes needed.

The same gate applies to the GraphQL `UserDeleteMutation` so the mobile "delete my account" flow behaves consistently.

This plan only writes code that runs on the **soft-delete** path. Hard-delete is the existing cron's job and is intentionally untouched.

## Background

### Soft-delete is mostly already in place

The codebase uses [`django-safedelete`](https://django-safedelete.readthedocs.io). `BaseModel` ([core/models/commons.py:69](backend/terraso_backend/apps/core/models/commons.py#L69)) is a `SafeDeleteModel` with `_safedelete_policy = SOFT_DELETE_CASCADE`. Effectively every domain model extends `BaseModel`. `User` ([core/models/users.py:72](backend/terraso_backend/apps/core/models/users.py#L72)) is also a `SafeDeleteModel` (not via `BaseModel`).

Tearing down related rows is mostly: "call `.delete()` on the right entry points; the FK cascade handles the rest." This plan adds two small explicit steps where the schema can't express the cascade we want, and one schema change (`Site.owner` to CASCADE) to remove an explicit loop the original plan had.

### The harddelete cron is generic — and stays untouched

[harddelete.py](backend/terraso_backend/apps/core/management/commands/harddelete.py) walks every model with a `deleted_at` field and hard-deletes rows past the cutoff. Because all cleanup in this plan happens at soft-delete time, every row that should die is soft-deleted alongside the user and the cron purges it on its own clock. **No cron changes required, and the new gate does not fire on `force_policy=HARD_DELETE`** — keeping the cron untouched and robust.

### Today's User delete already does _something_

`User.soft_delete_policy_action` ([users.py:138](backend/terraso_backend/apps/core/models/users.py#L138)) re-links `DataEntry.created_by` so the link survives undelete. **This re-link is removed in this plan** — under the new gate, any user with DataEntries is refused at the soft-delete boundary, so the re-link branch is unreachable on the success path.

`SafeDeleteAdmin` ([core/admin.py:62](backend/terraso_backend/apps/core/admin.py#L62)) gives admin: soft-delete on press of "Delete", an "Undelete selected" bulk action, and a Deleted/Active filter sidebar.

`User.undelete()` ([users.py:149](backend/terraso_backend/apps/core/models/users.py#L149)) refuses to undelete if email collides with another active user. Undelete is rare in practice but shouldn't crash.

### Where this fits in the existing deletion flow

There is already an account-deletion _request_ path: a user sets the `account_deletion_request` UserPreference to "true", which fires `create_account_deletion_ticket()` ([core/hubspot.py:24](backend/terraso_backend/apps/core/hubspot.py#L24)) and opens a HubSpot support ticket ([graphql/schema/users.py:205-209](backend/terraso_backend/apps/graphql/schema/users.py#L205-L209)). The team triages those tickets. **This work is the automated execution step** for tickets where the user has no undeletable data: instead of a fully-manual deletion, the user can immediately soft-delete their account from the User Settings screen. (Devs can also press the delete button in the django admin panel to similar effect). Users _with_ undeletable data still fall back to manual handling.

### Schema prerequisites

This plan changes the schema in three places:

1. **`Site.owner`** changes from `SET_NULL` to `CASCADE`. This was made `SET_NULL` recently by separate in-progress work (the "Deleted User" author handling) to let public unaffiliated sites survive their owner's deletion as orphans. We're deliberately overriding that here: a deleted user's unaffiliated sites should die with them, public ones included. Coordinate with the Deleted-User work before merging — `SiteNote.author` stays `SET_NULL` (notes on shared project sites must survive the author's deletion with the author nulled; that's a different scenario).

2. **`ProjectSettings` is removed entirely.** The model is vestigial — its docstring says _"Theses settings are currently ignored, and might be removed later"_ ([projects.py:24](backend/terraso_backend/apps/project_management/models/projects.py#L24)), no GraphQL exposure, zero references in `mobile-client` or `client-shared`. The `Project.settings` OneToOne is `PROTECT`, which would otherwise be the one PROTECT FK inside the user-deletion subtree; removing the model eliminates the FK and the risk together.

3. **`Project.membership_list`** stays as-is (forward OneToOne, `CASCADE` toward Project). Cleanup happens in `Project.soft_delete_policy_action` — see below.

## Behavior specification

### Three-layer architecture: check, enforcement, presentation

The "undeletable data" rule has three layers, each in one place:

```
            deletion_blockers()        ← THE CHECK — just returns a list,
                  ▲      ▲              no enforcement
                  │      │
                  │      │
        UserAdmin │      │   UserDeleteMutation
        (pre-     │      │   (catches
         checks;  │      │    UserDeletionBlockedError
         skips    │      │    from User.delete();
         .delete  │      │    builds structured
         if       │      │    payload from e.blockers)
         blockers)│      │
                  │      │
                  ▼      ▼
                  User.delete()        ← THE ENFORCEMENT FLOOR —
                  (raises                raises UserDeletionBlockedError
                   UserDeletionBlocked-   if blockers exist
                   Error on soft path     (subclass of ValidationError)
                   only)
```

**The check** (`User.deletion_blockers()`) is data — it returns a list. It defines _what counts as undeletable data_.

**The enforcement** lives in `User.delete()` for the soft-delete path only: if blockers exist, the model raises `UserDeletionBlockedError` (a `ValidationError` subclass with `.blockers` attached). **The guard does NOT fire on `force_policy=HARD_DELETE`** — that path belongs to the cron, which is generic and must stay robust. Anyone hard-deleting a User in a shell bypasses the gate by design; the cascade only matters at the user-facing soft-delete boundary.

**The presentation** is per-caller. Admin pre-checks and renders an HTML list as a red banner (catching the exception post-super() would conflict with Django's framework bookkeeping — see `delete_model` comment in admin.py). GraphQL catches `UserDeletionBlockedError` from `user.delete()` and reads `e.blockers` to build the structured payload. Shell users (and any future caller) see the plain exception on the soft-delete path.

**Per-path flow:**

| Path                                                 | When user is clean                                             | When user has blockers                                                                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Admin "Delete"                                       | Pre-check returns `[]` → calls `.delete()` → user soft-deleted | Pre-check returns blockers → red banner shown → `.delete()` never called                                                        |
| GraphQL mutation                                     | `user.delete()` runs → user soft-deleted                       | `user.delete()` raises `UserDeletionBlockedError` → caught → `request_account_deletion(blockers)` → returns `user=null, blockers` |
| Shell `user.delete()` (soft)                         | `deletion_blockers()` returns `[]` → user soft-deleted         | `deletion_blockers()` returns `[...]` → raises `UserDeletionBlockedError`                                                       |
| Shell `user.delete(force_policy=HARD_DELETE)` / cron | Hard-deleted (existing cron path, gate does not fire)          | Same — gate does not fire                                                                                                       |

### Defining "undeletable data" — the rule

A reverse relation from another model to `User` is a **deletion blocker** if and only if:

1. It's a **ForeignKey** (M2M reverse relations skip — through-rows auto-clean), **and**
2. Its `on_delete` is **PROTECT**, **RESTRICT**, or **DO_NOTHING** (the three behaviors that would either raise or orphan at hard-delete), **and**
3. The model isn't in the **explicit-cascade allowlist** (`project_management`, `soil_id` — we tear those down ourselves) or the **Django-internals allowlist** (`admin`, `auth`, `contenttypes`, `sessions`), **and**
4. There are matching **active** rows. Soft-deleted referencing rows do NOT block — the resilient harddelete cron (sort by `deleted_at`, per-row `transaction.atomic` + broad `try/except`, daily retry) handles them in subsequent runs without crashing the batch. See "Cron resilience and the dropped rule 5" in the Concerns section.

Plus one **policy override** layered on top:

5. `collaboration.Membership.user` is CASCADE (so it auto-allows by clause 2), but we deliberately count non-project, APPROVED memberships as blockers — being a member of a Group or Landscape is undeletable data and warrants manual review.

The on_delete-floor (clause 2) is what makes the rule self-maintaining. CASCADE/SET_NULL relations are _by definition_ safe to hard-delete; you can't get an allowlist wrong if you're reading the database's own behavior. A future model added with PROTECT/DO_NOTHING automatically blocks (good); one added with CASCADE auto-allows (correct for infrastructure like UserPreference/BackgroundTask).

### How this maps onto the current schema

| Relation                                                        | on_delete  | Result                              | Why                                                  |
| --------------------------------------------------------------- | ---------- | ----------------------------------- | ---------------------------------------------------- |
| `core.UserPreference.user`                                      | CASCADE    | allow                               | safe + infra                                         |
| `core.BackgroundTask.created_by`                                | CASCADE    | allow                               | safe + infra                                         |
| `core.Group.created_by`                                         | PROTECT    | **block**                           | undeletable web data                                 |
| `core.Landscape.created_by`                                     | PROTECT    | **block**                           | undeletable web data                                 |
| `core.TaxonomyTerm.created_by`                                  | PROTECT    | **block**                           | undeletable web data                                 |
| `shared_data.DataEntry.created_by`                              | DO_NOTHING | **block**                           | undeletable web data                                 |
| `shared_data.VisualizationConfig.created_by`                    | PROTECT    | **block**                           | undeletable web data                                 |
| `story_map.StoryMap.created_by`                                 | DO_NOTHING | **block**                           | undeletable web data                                 |
| `collaboration.Membership.user`                                 | CASCADE    | **block** if non-project + APPROVED | policy override (clause 5)                           |
| `core.Membership.user` (deprecated)                             | CASCADE    | allow                               | deprecated system; lingering rows are CASCADE-safe   |
| `MembershipList.members`, `Group.members`, `Site.seen_by` (M2M) | —          | allow                               | auto-cleaned through-rows                            |
| `project_management.*`, `soil_id.*`                             | various    | allow                               | explicit cascade in `User.soft_delete_policy_action` |
| `auth.*`, `admin.LogEntry`, `sessions.*`                        | various    | allow                               | Django internals                                     |

```python
from safedelete.models import SafeDeleteModel

LANDPKS_APP_LABELS = {"project_management", "soil_id"}
SYSTEM_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}
BLOCKING_ON_DELETE = {"PROTECT", "RESTRICT", "DO_NOTHING"}


BLOCKER_ID_CAP = 50  # admin/HubSpot rendering truncates beyond this


class User(SafeDeleteModel, AbstractUser):
    def deletion_blockers(self):
        """Returns a list of blocker dicts for any rows that would block this
        user's deletion. Empty = safe to soft-delete.

        Each blocker is `{model, qualifier, field, count, ids}`:
          - `model`: Django model label (e.g. "collaboration.Membership").
          - `qualifier`: Optional[str], None for most. Used for the policy
            override to distinguish e.g. "non-project, approved" memberships
            without embedding prose in `model`.
          - `field`: reverse-FK field name (e.g. "created_by", "user").
          - `count`: total matching row count (incl. soft-deleted).
          - `ids`: up to BLOCKER_ID_CAP pk strings, for rendering as links
            in admin / HubSpot ticket. Use `count - len(ids)` to compute the
            "and N more" hint when display-truncated.

        See the rule above for what counts as a blocker. Counts soft-deleted
        rows. Only active rows count — soft-deleted referencers are
        purged by the resilient harddelete cron in subsequent runs."""
        blockers = []
        for rel in User._meta.related_objects:
            if rel.many_to_many:
                continue  # through-rows auto-cleaned
            related_model = rel.related_model
            app = related_model._meta.app_label
            if app in LANDPKS_APP_LABELS or app in SYSTEM_APP_LABELS:
                continue

            if related_model._meta.label == "collaboration.Membership":
                # Policy override: non-project APPROVED memberships block
                # (Group/Landscape membership = undeletable web data).
                # ProjectMembershipList is a proxy of MembershipList, so we
                # distinguish project lists by `membership_list__project__isnull`
                # (the established pattern — see UserFilter at
                # graphql/schema/users.py).
                qs = self.collaboration_memberships.filter(
                    membership_list__project__isnull=True,
                    membership_status=Membership.APPROVED,
                )
                count = qs.count()
                if count > 0:
                    blockers.append({
                        "model": "collaboration.Membership",
                        "qualifier": "non-project, approved",
                        "field": "user",
                        "count": count,
                        "ids": [str(pk) for pk in qs.values_list("pk", flat=True)[:BLOCKER_ID_CAP]],
                    })
                continue

            on_delete_name = rel.on_delete.__name__.upper()
            if on_delete_name not in BLOCKING_ON_DELETE:
                continue

            if issubclass(related_model, SafeDeleteModel):
                base_qs = related_model.objects.all()
            else:
                base_qs = related_model.objects.all()
            qs = base_qs.filter(**{rel.field.name: self})
            count = qs.count()
            if count > 0:
                blockers.append({
                    "model": related_model._meta.label,
                    "qualifier": None,
                    "field": rel.field.name,
                    "count": count,
                    "ids": [str(pk) for pk in qs.values_list("pk", flat=True)[:BLOCKER_ID_CAP]],
                })
        return blockers
```

### Mandatory structural tests (CI drift detectors)

Two structural tests run in CI to catch schema drift:

**Test A: every reverse FK to User is correctly classified.** Iterate `User._meta.related_objects`, assert each falls into exactly one bucket:

1. Landpks app (`LANDPKS_APP_LABELS`) — orchestrated explicitly in `soft_delete_policy_action`.
2. System app (`SYSTEM_APP_LABELS`) — Django internals.
3. `collaboration.Membership.user` — policy special case.
4. `CASCADE` / `SET_NULL` / `SET_DEFAULT` / `SET(...)` — auto-allowed (referentially safe).
5. `PROTECT` / `RESTRICT` / `DO_NOTHING` — auto-blocked, and `deletion_blockers()` must produce it for a user who has matching rows.

M2M reverse relations are also iterated and asserted to be skipped. Anything unclassified → test fails. This catches a future PR that adds, say, a new web app with a `PROTECT` FK to User and forgets to wire it through `deletion_blockers()`.

**Test B: the landpks deletion subtree is hard-delete-safe.** Walk every FK in `project_management` + `soil_id`. Assert each FK _to User_ is `CASCADE`/`SET_NULL`/M2M, and each FK _within the deletion subtree_ (the transitive closure from Site / Project / SoilData / etc.) is `CASCADE`/`SET_NULL`. Anything `PROTECT`/`RESTRICT`/`DO_NOTHING` in the landpks subtree → test fails. This catches a future PR that adds, say, a `PROTECT` FK in `soil_id` and would otherwise wedge the user-deletion cascade at hard-delete time.

Together these prove the schema can't drift into a state where the gate either over-blocks (Test A) or under-protects (Test B).

### Cascade scope (when delete proceeds)

Inside `User.soft_delete_policy_action`, after the gate has cleared:

1. **Unaffiliated sites**: handled by the default cascade via `Site.owner = CASCADE`. Safedelete's `SOFT_DELETE_CASCADE` on User soft-deletes all owned sites, which cascade to SoilData → SoilDataDepthInterval / DepthDependentSoilData, SoilMetadata, SiteNote, SitePushHistory, SoilDataHistory. **No explicit loop needed.** (By the existing check constraint, `owner=self` ⟹ `project` is null, so this covers exactly the unaffiliated set.)

2. **Sole-manager projects**: explicitly soft-deleted in a Python loop. `Project.soft_delete_policy_action` (added in this plan) cleans up the project's MembershipList; the default cascade handles its Sites and ProjectSoilSettings.

3. **Surviving sites and notes** (project-affiliated sites; projects with co-managers): the user's Membership is soft-deleted by the default cascade (`Membership.user` is CASCADE + SafeDeleteModel). `SiteNote.author` on surviving rows is nulled by its `SET_NULL` FK — no extra code needed.

### Inside `Project.soft_delete_policy_action`

`Project.membership_list` is a forward `OneToOneField` (FK column lives on Project), so neither Django's collector nor safedelete's `SOFT_DELETE_CASCADE` reach it when the Project is deleted. The cleanup lives in `Project.soft_delete_policy_action` so it holds for **every** project deletion path (user-deletion cascade, admin bulk soft-delete, future code) — safedelete's `SafeDeleteQueryset.delete()` iterates and calls per-instance `.delete()`, which invokes the override.

Order matters: soft-delete the Project first (cascades to Sites and the soil-settings subtree), then soft-delete the now-orphaned MembershipList (cascades to its Memberships). Doing it the other way would have the MembershipList's `CASCADE` toward Project try to soft-delete the Project a second time.

### Special cases (or lack thereof)

**DataEntry re-link** (removed) — the existing `soft_delete_policy_action` re-attaches `DataEntry.created_by` to the soft-deleted user. Under the new gate, any user with DataEntries is refused at the soft-delete boundary, so this branch is unreachable on the success path. The re-link is removed.

**Site notes** — `SiteNote.author` is `on_delete=SET_NULL` ([site_notes.py:30-36](backend/terraso_backend/apps/project_management/models/site_notes.py#L30-L36)). When the user is hard-deleted, every SiteNote they authored has `author` nulled automatically. Notes on the user's own unaffiliated sites die with those sites (`SiteNote.site` is CASCADE).

**Project pinned note** — `Project.site_instructions` ([projects.py:79](backend/terraso_backend/apps/project_management/models/projects.py#L79)) is a plain `TextField` on Project. **It has no author column.** Either the project soft-deletes with the user (sole-manager case, note goes with it) or the project survives (text survives, no one to null). Nothing to do.

**Note on undelete asymmetry** — undelete restores the User row and soft-deleted Memberships, but does _not_ restore `SiteNote.author` rows nulled at hard-delete. Per current product direction (undelete is rare), this is accepted. Documented at [admin.py:71-77](backend/terraso_backend/apps/core/admin.py#L71-L77).

### Logging

Both outcomes emit a structured log line via the existing `structlog` setup ([settings.py:270](backend/terraso_backend/config/settings.py#L270)). `django_structlog` already attaches `request_id` and the requesting `user_id` to every line, so we only need the target and the result:

- On successful soft-delete: `logger.info("user.soft_deleted", target_user_id=str(self.id))`
- On refusal: `logger.warning("user.delete_blocked", target_user_id=str(self.id), blockers=blockers)`

Logs render as JSON to stdout and warnings/errors also reach Sentry. Put the log calls in `User.delete()` / `soft_delete_policy_action` so they fire from every soft-delete path, not just admin.

## Implementation plan

### Schema changes (do these first)

1. **Migration: change `Site.owner` to `CASCADE`** ([sites.py:50-56](backend/terraso_backend/apps/project_management/models/sites.py#L50-L56)). Coordinate with the Deleted-User author-handling work before merging. The existing check constraint and orphan-handling code in `filter_visible_sites` can stay — orphans from before this change still exist and the public-branch visibility still works; no new orphans are created by user deletion under CASCADE.

2. **Migration: remove `ProjectSettings`** — drop the `settings` field on `Project`, drop the `ProjectSettings` model + table.

### Files to change

1. **`apps/core/models/users.py`** — the rule and the enforcement floor.
    - Add module-level constants `LANDPKS_APP_LABELS`, `SYSTEM_APP_LABELS`, `BLOCKING_ON_DELETE`.
    - Add `User.deletion_blockers()` (the function above).
    - Override `User.delete()` to pre-check `deletion_blockers()` and raise `ValidationError` if non-empty **only when `force_policy` is not `HARD_DELETE`**.
    - Rewrite `soft_delete_policy_action()` to just iterate `_solo_manager_projects()` and call `super()` (wrap in `@transaction.atomic`). Remove the DataEntry re-link.
    - Add `_solo_manager_projects()` helper (annotated query to avoid N+1).
    - Add the structured log lines.

2. **`apps/core/admin.py`** — admin presentation layer.
    - Override `UserAdmin.delete_model` to pre-check via `obj.deletion_blockers()`. If blockers exist, render with `format_html` + `format_html_join` and show via `self.message_user(..., level=messages.ERROR)`. Don't call super.
    - Override `UserAdmin.delete_queryset` to partition into deletable and blocked users. Delete the deletable ones, show a single banner message listing the skipped users.
    - Add helper `_format_blocker_message(user, blockers)`.

3. **`apps/graphql/schema/users.py`** — GraphQL presentation layer.
    - Add `BlockerType` (graphene `ObjectType` with `model: String`, `qualifier: String` (nullable), `field: String`, `count: Int`, `ids: [ID]`).
    - Add `blockers = graphene.List(BlockerType)` to `UserDeleteMutation`'s payload.
    - Override `mutate_and_get_payload` to pre-check via `user.deletion_blockers()`. If non-empty, **call `request_account_deletion(user)` to fire the existing HubSpot/pref side effects** (so blocked self-delete falls back to the manual support flow), and return `cls(user=None, blockers=[...])`. Otherwise call `user.delete()` and return `cls(user=user, blockers=[])`.
    - This departs from `BaseDeleteMutation`'s default flow — `UserDeleteMutation` no longer falls through to the parent's `mutate_and_get_payload`.

4. **`apps/project_management/models/projects.py`** — Project cleanup + ProjectSettings removal.
    - Remove the `ProjectSettings` class.
    - Remove `default_settings()` and the `self.settings = ...` line in `Project.save()`.
    - Remove the `Project.settings` field.
    - Add `Project.soft_delete_policy_action` override that captures `self.membership_list`, calls `super()`, then `membership_list.delete()`.

5. **`apps/project_management/admin.py`** — drop `admin.site.register(ProjectSettings)` and the import.

6. **`apps/project_management/models/__init__.py`** — drop `ProjectSettings` from imports and `__all__`.

7. **`apps/project_management/models/sites.py`** — change `Site.owner = ForeignKey(..., on_delete=models.CASCADE)`.

8. **Tests** (`tests/`):
    - **Structural Test A**: every reverse FK to User is classified (5 buckets above). M2Ms skipped. Test fails on drift.
    - **Structural Test B**: every FK in `project_management` + `soil_id` is CASCADE/SET_NULL/M2M (no PROTECT/RESTRICT/DO_NOTHING in the deletion subtree).
    - `User.deletion_blockers()` returns expected blockers for each kind of undeletable data (DataEntry, VisualizationConfig, StoryMap, Group.created_by, Landscape.created_by, TaxonomyTerm.created_by, non-project APPROVED Membership).
    - `User.deletion_blockers()` returns `[]` for a landpks-only user.
    - `User.delete()` raises `ValidationError` (soft path) for a user with blockers.
    - `User.delete()` succeeds for a landpks-only user.
    - **`force_policy=HARD_DELETE` is NOT gated**: `user_with_blockers.delete(force_policy=HARD_DELETE)` does not raise (proves the cron path is unaffected).
    - **Membership classification**: one project membership and one Group/Landscape membership for the same user; project one is _not_ a blocker, the other _is_. (Locks the proxy-model traversal.)
    - **Pending membership doesn't block**: a `PENDING`, non-project membership is not counted; an `APPROVED` one is.
    - **Soft-deleted blockers do NOT block** (rule 5 dropped): soft-delete a user's `StoryMap`, assert `deletion_blockers()` no longer reports it. Locks in the new behavior and prevents accidental rule-5 re-introduction.
    - **Cron resilience**: parametrized over all 6 blocker models — soft-delete the referencer, then the user, assert both are gone within at most 2 cron runs. Covers DO_NOTHING (one run) and PROTECT (two runs, retry convergence). See `tests/core/commands/test_harddelete.py::test_cron_converges_within_two_runs`.
    - **Behavioral cascade test (the big one)**: build the full nested footprint (user → sole-managed project → MembershipList + Memberships → sites → soil data → depth intervals → notes → history) plus a co-managed project (sites + notes), soft-delete the user, assert: (a) sole-managed project + all its descendants soft-deleted, (b) project's MembershipList + Memberships soft-deleted, (c) co-managed project survives, (d) user's Membership in co-managed project soft-deleted, (e) co-managed project's sites survive, (f) DataEntry-re-link branch is _not_ exercised (no DataEntries for this user).
    - Sole-manager detection: sole, co-managed, non-manager.
    - **`Project.soft_delete_policy_action` cleans up MembershipList**: directly soft-delete a Project (outside the user cascade), assert its MembershipList + Memberships are soft-deleted.
    - **Admin single-delete**: pressing Delete on a user-with-blockers shows the red banner with the blocker list and does NOT soft-delete the user.
    - **Admin bulk delete**: select a mix of users-with-blockers and clean users → the clean ones delete, the blocked ones show in a warning banner, no exceptions raised.
    - **GraphQL mutation**: returns `user=null, blockers=[...]` for a user-with-blockers; returns `user=<obj>, blockers=[]` for a clean delete.
    - **Suggested fixture**: a shared pytest fixture (using `mixer`, matching `test_user_deletion_unblock.py`) that builds `user → sole-managed project → sites → soil data → depth intervals`, so cascade tests don't each rebuild the nested scenario.

### Sketch (illustrative, not final)

```python
# apps/core/models/users.py
from safedelete.models import HARD_DELETE, SafeDeleteModel

LANDPKS_APP_LABELS = {"project_management", "soil_id"}
SYSTEM_APP_LABELS = {"admin", "auth", "contenttypes", "sessions"}
BLOCKING_ON_DELETE = {"PROTECT", "RESTRICT", "DO_NOTHING"}


class User(SafeDeleteModel, AbstractUser):
    ...

    def delete(self, *args, **kwargs):
        # Gate fires only on the soft-delete path. Hard-delete (cron,
        # admin hard_delete_soft_deleted, shell force_policy=HARD_DELETE)
        # is intentionally not gated — cleanup happens at soft-delete time.
        if kwargs.get("force_policy") != HARD_DELETE:
            blockers = self.deletion_blockers()
            if blockers:
                logger.warning("user.delete_blocked",
                               target_user_id=str(self.id),
                               blockers=blockers)
                raise ValidationError(
                    f"Cannot delete user {self.email!r}: has undeletable data "
                    f"({len(blockers)} blocking model(s))."
                )
            logger.info("user.soft_deleted", target_user_id=str(self.id))
        return super().delete(*args, **kwargs)

    def deletion_blockers(self):
        # see the function in the Behavior spec above
        ...

    @transaction.atomic
    def soft_delete_policy_action(self, **kwargs):
        # Unaffiliated owned sites: handled by Site.owner=CASCADE +
        # safedelete's SOFT_DELETE_CASCADE. Their soil/notes/history
        # subtrees cascade automatically.
        # Sole-manager projects: explicit — there's no FK that says
        # "this project belongs to this user".
        for project in self._solo_manager_projects():
            project.delete()
        return super().soft_delete_policy_action()

    def _solo_manager_projects(self):
        # Annotated single-query: projects where the user has an APPROVED,
        # non-soft-deleted Membership with manager role AND the project's
        # manager-Membership count is 1.
        ...


# apps/project_management/models/projects.py
class Project(BaseModel):
    ...
    # NOTE: ProjectSettings removed; Project.settings field removed;
    # Project.save() no longer auto-creates settings.

    @transaction.atomic
    def soft_delete_policy_action(self, **kwargs):
        # MembershipList is a forward OneToOne, so neither Django's
        # collector nor safedelete's SOFT_DELETE_CASCADE reach it when
        # Project is deleted. Clean it up explicitly so the guarantee
        # holds for every project-deletion code path.
        membership_list = self.membership_list
        result = super().soft_delete_policy_action()
        membership_list.delete()  # cascades to its Memberships
        return result
```

```python
# apps/core/admin.py
class UserAdmin(SafeDeleteAdmin, DjangoUserAdmin):
    ...

    def delete_model(self, request, obj):
        blockers = obj.deletion_blockers()
        if blockers:
            self.message_user(
                request,
                self._format_blocker_message(obj, blockers),
                level=messages.ERROR,
            )
            return  # don't call super; user remains undeleted
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        deletable, blocked = [], []
        for user in queryset:
            if user.deletion_blockers():
                blocked.append(user)
            else:
                deletable.append(user)
        for user in deletable:
            user.delete()
        if blocked:
            emails = ", ".join(u.email for u in blocked)
            self.message_user(
                request,
                f"Skipped {len(blocked)} user(s) with undeletable data: {emails}. "
                "These require manual cleanup before deletion.",
                level=messages.WARNING,
            )

    def _format_blocker_message(self, user, blockers):
        items = format_html_join(
            "",
            "<li>{} ({}): {} row(s)</li>",
            ((b["model"], b["field"], b["count"]) for b in blockers),
        )
        return format_html(
            "Cannot delete user <strong>{}</strong>: user has undeletable "
            "data and must be cleaned up manually first.<ul>{}</ul>",
            user.email,
            items,
        )
```

```python
# apps/graphql/schema/users.py
class BlockerType(graphene.ObjectType):
    model = graphene.String()
    qualifier = graphene.String()  # nullable
    field = graphene.String()
    count = graphene.Int()
    ids = graphene.List(graphene.ID)


class UserDeleteMutation(BaseDeleteMutation):
    user = graphene.Field(UserNode)
    blockers = graphene.List(BlockerType)
    model_class = User

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        _id = kwargs.get("id")

        if str(request_user.id) != _id:
            logger.error("Attempt to delete a User by another user, not allowed",
                         extra={"request_user_id": request_user.id, "target_user_id": _id})
            raise GraphQLNotAllowedException(
                model_name=User.__name__, operation=MutationTypes.DELETE
            )

        # Single code path: try to soft-delete; if blockers exist, the model
        # raises UserDeletionBlockedError with the blocker list attached. We
        # catch ONLY that specific subclass — it's our own designed signal
        # that "deletion_blockers() returned non-empty." Other exceptions
        # (DB errors, A3 distant drift, cascade bugs) carry no semantic
        # certainty about user state — they must surface honestly for
        # Sentry + manual investigation.
        #
        # No pre-check is needed: the model's internal check at User.delete()
        # is authoritative, and reusing its already-computed blocker list via
        # the exception avoids both a redundant DB query and the TOCTOU gap
        # the old pre-check pattern created.
        user = User.objects.get(pk=_id)
        try:
            user.delete()
        except UserDeletionBlockedError as e:
            # Fall back to the manual-cleanup flow: set the pending-deletion
            # pref and file a HubSpot ticket (including blockers in the body
            # so support has context). Idempotent — helper no-ops if pref
            # is already "true".
            request_account_deletion(user, blockers=e.blockers)
            return cls(user=None, blockers=e.blockers)
        return cls(user=user, blockers=[])
```


```python
# apps/core/models/users.py — new exception class
class UserDeletionBlockedError(ValidationError):
    """Raised by User.delete() (soft path) when deletion_blockers() is
    non-empty. Subclass of ValidationError for backwards compatibility
    with existing `except ValidationError` callers (tests, shell users).
    Carries the blocker list so callers can render structured responses
    without re-querying."""

    def __init__(self, message, blockers):
        super().__init__(message)
        self.blockers = blockers


# apps/core/models/users.py — User.delete() override (updated)
def delete(self, *args, **kwargs):
    if kwargs.get("force_policy") != HARD_DELETE:
        blockers = self.deletion_blockers()
        if blockers:
            logger.warning("user.delete_blocked",
                           target_user_id=str(self.id),
                           blockers=blockers)
            raise UserDeletionBlockedError(
                f"Cannot delete user {self.email!r}: has undeletable data "
                f"({len(blockers)} blocking model(s)).",
                blockers=blockers,
            )
        logger.info("user.soft_deleted", target_user_id=str(self.id))
    return super().delete(*args, **kwargs)
```


```python
# apps/core/admin.py — admin path KEEPS pre-check (Django framework reasons)
class UserAdmin(SafeDeleteAdmin, DjangoUserAdmin):
    def delete_model(self, request, obj):
        # We pre-check here rather than catching UserDeletionBlockedError
        # from super().delete_model() because Django's _delete_view wraps
        # this call with log_deletion() and response_delete() that emit a
        # "Successfully deleted" message based on framework state, not on
        # whether the delete actually happened. Returning before super()
        # prevents the LogEntry write and the contradictory success banner.
        # The mutation path doesn't have this constraint and uses catch-only.
        blockers = obj.deletion_blockers()
        if blockers:
            self.message_user(
                request,
                self._format_blocker_message(obj, blockers),
                level=messages.ERROR,
            )
            return  # don't call super; user remains undeleted
        super().delete_model(request, obj)
```

```python
# apps/core/models/users.py (or apps/core/hubspot.py)
def request_account_deletion(user, blockers=None):
    """Set the pending-deletion pref and file the HubSpot ticket exactly
    once. Idempotent if the pref is already "true" (no second ticket).

    Called from two paths:
      - UserPreferenceUpdate(ACCOUNT_DELETION, "true") — explicit pref-set
        from older mobile builds.
      - UserDeleteMutation's exception-catch branch — for users whose
        User.delete() raised UserDeletionBlockedError.

    The blockers list, if provided, is included in the HubSpot ticket body
    so support reps see exactly which rows are blocking the user.

    No permission check — the caller is responsible for gating.

    Order matters: file the ticket BEFORE saving the pref. If HubSpot is
    down, the pref stays "false", the call raises, and the caller's error
    path lets the user retry. If we saved the pref first and HubSpot then
    failed, the idempotence check would silently block all future retries
    — a user-hostile permanent failure. The reverse race (ticket succeeds,
    then pref.save() fails) creates a duplicate ticket on next retry;
    accepted because pref.save() failing after a successful HubSpot call
    requires the DB to drop mid-function and is vanishingly rare."""
    pref, _ = UserPreference.objects.get_or_create(
        user=user, key=USER_PREFS_KEY_ACCOUNT_DELETION
    )
    if pref.value.lower() == "true":
        return  # already requested; no duplicate ticket
    create_account_deletion_ticket(user, blockers=blockers)  # may raise; pref unchanged on failure
    pref.value = "true"
    pref.save()
```

## Open questions

None blocking. Three coordination items:

1. **`Site.owner` → CASCADE** touches an FK that the separate "Deleted User" author-handling work owns. Confirm with that work before merging that public unaffiliated sites _not_ surviving the owner's deletion is acceptable.
2. **Runbook for manual cleanup** of users with undeletable data is owned by the team in the wiki — not a code deliverable.
3. **Mobile copy revision.** Today's `DeleteAccountConfirmContent` copy promises the user's Terraso account is preserved — no longer true on the unblocked path. Designer revising in parallel; we ship with a `TODO(designer)` marker on the affected strings and a follow-up PR lands the revised copy.

## Settled decisions (do not re-litigate)

- **"Undeletable data" defined by an `on_delete`-floor rule + one policy override**, not a hand-maintained model list. CASCADE/SET_NULL/M2M never block (self-maintaining); PROTECT/RESTRICT/DO_NOTHING auto-block; landpks/system apps skip; collaboration.Membership non-project APPROVED blocks via policy override. New future models classify themselves correctly by their `on_delete` choice.
- ~~**Soft-deleted blockers still block**~~ — **Re-litigated June 2026**: rule 5 was dropped. Now only **active** rows block at the gate. The harddelete cron was hardened (per-row `transaction.atomic` + broad `try/except`, sort by `deleted_at`, proxy-model skip, structured `harddelete.row_failed` log) to handle the cases this rule was originally protecting against. The original concern ("a not-yet-purged PROTECT/DO_NOTHING row would crash the cron") proved less load-bearing than the doc claimed: PROTECT blockers do raise `ProtectedError` on first iteration, but the resilient cron retries them next run after the dependency is purged; DO_NOTHING blockers don't appear to crash at all in our test setup (mechanism unclear — possibly test-mode FK-deferral, possibly a `null=True`-related Django collector path, accepted as a known unknown since the cron's resilience covers either case). Net win for users: the 30-day blocked window after soft-deleting a story map is gone. See `tests/core/commands/test_harddelete.py::test_cron_converges_within_two_runs`.
- **Gate fires only on soft-delete**, not on `force_policy=HARD_DELETE`. The cron path stays robust; cleanup happens at the soft-delete boundary by design.
- **`Site.owner` → CASCADE**, drop the explicit unaffiliated-sites loop. Public unaffiliated sites die with their owner alongside private ones.
- **`ProjectSettings` removed entirely** — model + table + FK + admin + save-time autocreate. Eliminates the only PROTECT FK inside the user-deletion subtree.
- **MembershipList cleanup lives in `Project.soft_delete_policy_action`**, not in the user cascade. Holds for every project-deletion path (safedelete queryset honors per-instance `.delete()`). No `post_delete` signal — soft-delete is the only event that matters here.
- **DataEntry re-link removed** from `User.soft_delete_policy_action`. Under the gate, any user with DataEntries is refused at soft-delete; the re-link branch is unreachable.
- **Pending memberships don't block**: only APPROVED, non-project memberships count (`Membership.user` is CASCADE so pending invites are hard-delete-safe regardless).
- **Refuse rather than partially-delete** when a user has undeletable data. Manual cleanup via the existing HubSpot-ticket flow; no runbook URL hardcoded in the app.
- **Sole-manager semantics**: count only `membership_status=APPROVED`, non-soft-deleted Memberships. Exclude `pending_email`-only invites.
- **No "project-level notes" special case.** `Project.site_instructions` has no author; nothing to null.
- **Both structural tests are part of the deliverable**, not "nice to have." Test A guards the user-FK classification; Test B guards the landpks subtree.
- **Three-layer architecture**: `deletion_blockers()` (check) + `User.delete()` (enforcement, soft path only) + admin/GraphQL pre-check (presentation). The rule lives once.
- **GraphQL response shape is structured**: mutation payload has a `blockers` list, not just a string error.
- **Admin error renders as HTML** via `format_html` + the messages framework with `level=messages.ERROR`.
- **Bulk admin delete partitions** the batch: clean users delete, blocked users are skipped with a single summary banner. No exceptions raised mid-batch.
- **Structured logging** on both outcomes.
- **TaxonomyTerm.created_by counts as undeletable data** — falls out of the on_delete-floor (PROTECT) without special handling.
- **Legacy `core.Membership` is deprecated and ignored** — the active membership system for Groups/Landscapes is `collaboration.Membership`, already caught by the policy override. Lingering `core.Membership` rows are CASCADE-safe.
- **Blocker shape is `{model, qualifier, field, count, ids}`**. `qualifier` is Optional[str] (used by the membership policy override; `None` for everything else). `ids` is a list of up to `BLOCKER_ID_CAP = 50` pk strings; `count` is the true total. Renderers compute "and N more" from `count - len(ids)` when truncated.
- **Blockers are NOT displayed in-app.** Mobile shows the same generic pending screen as today regardless of whether the user is blocked or just requesting support handling. Blocker details travel to support via the HubSpot ticket body.
- **`request_account_deletion(user, blockers=None)` is the shared side-effect helper.** Sets the pref + files the HubSpot ticket exactly once (no-op if pref already `"true"`). Called by `UserPreferenceUpdate(ACCOUNT_DELETION, "true")` and by `UserDeleteMutation`'s blocked branch. Caller is responsible for permission gating.
- **HubSpot ticket body includes blockers** when supplied. Support reps see exactly which rows are blocking, with up to 50 pk strings per blocker plus an "and N more" hint when truncated.
- **Mobile clean-delete UX**: sign out → route to login → "Account deleted" modal. No second confirmation screen after the mutation succeeds.
- **Mobile blocked-delete UX**: route to existing `DeleteAccountPendingContent` screen. No blocker rendering on mobile. Matches the existing pref-update flow exactly.
- **Re-authentication is handled by existing model design.** JWT middleware bounces soft-deleted users by default (SafeDelete default manager); `unique_active_email` constraint is conditional on `deleted_at IS NULL` so re-signup with the same email creates a fresh active user; no new code needed for either case. (See "Self-service deletion (mobile-client)" section.)
- **`UserDeleteMutation` catches `UserDeletionBlockedError` only — not generic `ValidationError` or other exceptions.** The dedicated exception subclass is the specific signal our own code raises when blockers are detected; catching it (and reading `e.blockers`) lets us fall back to the manual-cleanup helper with semantic certainty. Generic `ValidationError` from unrelated code paths (signal handlers, downstream validators) doesn't trigger the fallback. Other exceptions (DB errors, A3 distant drift, cascade bugs) carry no such guarantee — they surface honestly so Sentry triggers and engineers diagnose at the source.
- **`UserDeletionBlockedError(ValidationError)`** is a `ValidationError` subclass with `.blockers` attached. Subclassing keeps backwards compatibility with existing `except ValidationError` callers (tests, shell users); the dedicated class locks the contract for the mutation. Raised exclusively from `User.delete()`.
- **Mutation uses single-path catch-only; admin path keeps pre-check.** Different patterns by surface: GraphQL builds its own response, so the catch-only flow is clean; Django admin's `_delete_view` wraps `delete_model` with framework bookkeeping (`log_deletion`, `response_delete`) that would emit a contradictory "Successfully deleted" message if we let the model raise. Pre-check on admin returns before that bookkeeping runs.
- **`request_account_deletion` helper files the HubSpot ticket BEFORE saving the pref.** If HubSpot is down, the pref stays "false" and the call raises — caller's error path lets the user retry. Reverse ordering would create a silent permanent failure if HubSpot were down (pref=true blocks all future retries, no ticket ever exists). The remaining race (pref.save() failing after HubSpot succeeds → duplicate ticket on retry) is vanishingly rare and accepted.
- **Mobile reuses existing sign-out infrastructure** (`userLoggedOut` action + `signOut` from terraso-client-shared) for the post-delete sign-out path. Bypasses the `hasUnsyncedChanges` guard from `SignOutModal` — unsynced data is being abandoned by definition when the account is deleted.
- **Harddelete cron is resilient to per-row failures.** Each iteration: sort by `deleted_at` (dependents purged before dependencies in the common case → one-run convergence), wrap `obj.delete(force_policy=HARD_DELETE)` in `transaction.atomic()` so a per-row rollback can't poison subsequent iterations, broad `try/except` so one row's failure doesn't abort the batch, and emit a structured `harddelete.row_failed` log (which Sentry picks up) with model + pk + error info. Proxy models are skipped in `all_objects()` because they share a table with their concrete parent and would otherwise queue the same row twice. The original "no try/except, no sort, abort-on-first-error" cron architecture was the load-bearing reason rule 5 existed; with this hardening rule 5 is no longer needed.
- **"Account deleted" modal copy includes the deleted email.** Pass-through via navigation state from the post-delete sign-out flow, since the user is signed out by the time the modal renders and we'd otherwise have no identifier to show.
- **Delete account button is disabled when offline.** Mobile mutations aren't queue-safe; tapping Delete with no network would fail anyway, and a disabled state is clearer UX than a generic error toast after the tap.

## Concerns and risks

1. **`SoilDataHistory.changed_by` and `SitePushHistory.changed_by` are `CASCADE` to User**. When a landpks-only user is hard-deleted, those audit-log rows disappear with them. Open question for product: is that desired, or should they be preserved with a nulled FK? Behaviorally fine for now; flag for future.

2. ~~**Self-service deletion via mobile**~~ — now in scope; see "Self-service deletion (mobile-client)" section.

3. **Concurrent edits / double-delete**. `soft_delete_policy_action` is wrapped in `transaction.atomic` on both User and Project; soft-delete is idempotent (setting `deleted_at` twice is harmless), so concurrent attempts converge. Not a real risk; `select_for_update` is available if one ever surfaces.

4. **Sole-manager detection performance**. For a user in many projects, naive iteration is N+1. Use a single annotated query (annotate each project's manager Membership count, filter to count == 1 with user present).

5. **`Site` check constraint**. The constraint at [sites.py:38-41](backend/terraso_backend/apps/project_management/models/sites.py#L38-L41) ensures at most one of `owner`/`project` is set. With `owner=CASCADE` no new orphans are produced by user deletion; existing orphans from before this change still satisfy the constraint. Verify with the behavioral test.

6. **`hard_delete_soft_deleted` admin action**. Calls `.delete(force_policy=HARD_DELETE)`. Under this plan the gate does NOT fire there. If staff use that action on an already-soft-deleted user with stale undeletable data (e.g., from before this gate existed), the underlying schema behavior applies — DO_NOTHING / PROTECT rows could crash the hard-delete. That's a pre-existing risk this plan doesn't change. If we want that action explicitly gated in the future, override the action itself (not the model's `delete()`).

7. **Apple `apple_sub` collision on undelete (minor).** `User.undelete()` checks for email collisions but not `apple_sub`. Very unlikely given undelete is rare; not in scope here.

8. **Shell users get raw `ValidationError`**. A developer running `user.delete()` in the shell sees a plain Python traceback rather than the formatted blocker list. Acceptable.

9. **Distant-app drift not caught by structural tests (the "A3" gap).** Structural Test A is one layer deep (direct reverse FKs from User); Structural Test B walks the landpks subtree only. A future web-data app that adds a `CASCADE` FK to User but has `PROTECT` / `DO_NOTHING` between its own models is not classified by either test. Soft-delete succeeds; the harddelete cron's per-row error handler logs the failure to Sentry, the row sits soft-deleted (recoverable) until the bug is fixed, and the user-facing operation has already completed. The cron-resilience hardening makes this gap less load-bearing than it used to be — partial state is the failure mode, not a crashed cron.

10. **DO_NOTHING crash hypothesis (the rule-5 motivator) — partially debunked.** The original rule 5 assumed that hard-deleting a User with a soft-deleted DO_NOTHING referrer (e.g. a StoryMap) would crash the cron with `IntegrityError`. The hardening work in June 2026 included an empirical convergence test parametrized over all 6 blocker models. Findings:
   - **PROTECT** referrers do raise `ProtectedError` on first-iteration hard-delete (Django collector behavior) — the cron's try/except + retry handles this, converging within 2 runs.
   - **DO_NOTHING** referrers (`StoryMap.created_by`, `DataEntry.created_by`) did NOT raise in tests. Possible explanations: test-mode FK-deferral, a `null=True`-related Django collector path, or some safedelete interaction the test environment exposes differently from production. The convergence test passes regardless of mechanism.
   - **Net**: the cron-resilience architecture handles both cases. The "rule 5 prevents a crash" rationale was only ever load-bearing for PROTECT, and even there the new retry mechanism resolves it. The DO_NOTHING mystery is documented as a known unknown — worth digging into only if production cron failures actually appear.

11. **TOCTOU between pre-check and `user.delete()`**. Between `deletion_blockers()` returning `[]` and the model's internal re-check, the same user could create a blocking row from another device (e.g. submit a StoryMap). The model raises `ValidationError`; the mutation catches it specifically, re-fetches the blocker list, files the ticket via `request_account_deletion`, and returns the structured `{user: null, blockers: [...]}` response. Mobile sees the same UX as the pre-check blocked path — no error, just routed to the pending screen. See the "TOCTOU safety" comment in the `UserDeleteMutation` sketch.

## Self-service deletion (mobile-client)

This section was originally an "Extensibility" future-step note. Product confirmed the direction (June 2026) and it is now in scope alongside the admin flow.

### What changes for the user

Today the mobile "Delete account" button in `UserSettingsScreen` opens `DeleteAccountScreen`, the user types their email to confirm, and submitting fires `UserPreferenceUpdate(key=ACCOUNT_DELETION, value="true")`. The backend sets the pref + opens a HubSpot ticket; the user sees the `DeleteAccountPendingContent` screen ("we'll delete within 5 business days") and a "Pending" indicator on the settings button. Their Terraso account is explicitly _not_ deleted by this flow today.

Post-change, the same button fires `UserDeleteMutation` instead. Two outcomes:

- **No blockers** → soft-delete runs immediately (cascade tears down LandPKS data + Terraso data). Mobile signs the user out, routes to the login screen, and shows an **"Account deleted"** modal. They cannot log back in to that account; if they OAuth with the same email, they get a fresh empty account (allowed by the `unique_active_email` conditional constraint on `User`).
- **Blockers present** → backend calls `request_account_deletion(user, blockers=...)` (sets the pref + files the HubSpot ticket, idempotently). Mutation returns `user=null, blockers=[...]`. Mobile shows the existing `DeleteAccountPendingContent` screen and the settings indicator flips to "Pending". This matches today's behavior exactly — the user sees no UX difference between "blocked self-delete" and "explicit support-ticket request."

Blocker details are not displayed in-app — the user sees the same generic pending screen as today. Blockers travel to support via the HubSpot ticket body.

### Re-authentication is handled by existing model design (no new code)

Three sub-questions verified during planning:

- **Other devices**: `JWTAuthenticationMiddleware._get_user` ([middleware.py:123-125](backend/terraso_backend/apps/auth/middleware.py#L123-L125)) uses `User.objects.get(pk=user_id)`, which goes through SafeDelete's default manager and excludes soft-deleted users. Existing JWTs on other devices fail on the next request with `User.DoesNotExist` → `ValidationError("User not found for JWT token")`. **No new code.**
- **Re-signup**: The `unique_active_email` constraint at [users.py:131-136](backend/terraso_backend/apps/core/models/users.py#L131-L136) is conditional on `deleted_at IS NULL`. A soft-deleted user with email X does not block a new active user with the same email. `OAuth login` calls `User.objects.get_or_create(email=email)` ([services.py:137](backend/terraso_backend/apps/auth/services.py#L137)); the soft-deleted user is filtered out by SafeDelete, a fresh active user is created. Same for `apple_sub` via `unique_active_apple_sub`. **The model was deliberately designed for this.**
- **Pending-pref users (existing)**: today's pending users can still log in (they aren't deleted yet — they see the pending screen). New instant-delete users can't log in at all. Different UX paths but consistent with what each actually represents.

### Files to change (mobile-client)

1. **`dev-client/src/screens/DeleteAccountScreen/components/DeleteAccountConfirmForm.tsx`** — swap the mutation call from `UserPreferenceUpdate(ACCOUNT_DELETION, "true")` to `UserDeleteMutation`. Handle the two response shapes:
    - `user != null` → call sign-out → navigate to login → present `AccountDeletedModal`.
    - `user == null && blockers.length > 0` → existing behavior (route to `DeleteAccountPendingContent`).

2. **New: `AccountDeletedModal` component on the login screen.** Shown once after successful self-delete. Dismisses to normal login UI.

3. **Copy updates in `dev-client/src/translations/{en,es,...}.json`** — `delete_account.confirm.p4.b1` currently says _"your Terraso account (including groups, landscapes, and story maps)"_ will NOT be deleted. That's no longer true on the unblocked path. **Stub with `TODO(designer): revise post product confirmation`** and proceed; designer's revision lands in a follow-up.

4. **Tests** — at minimum, mock the mutation returning each of the two success shapes and assert the correct downstream nav/UI. Existing snapshot tests for `DeleteAccountScreen` regenerated.

### Files to change (web-client)

None. Per current product direction, the web-client has no user-deletion pathway and isn't getting one in this work.

### Helper extraction (`request_account_deletion`)

The existing inline block at [graphql/schema/users.py:218-223](backend/terraso_backend/apps/graphql/schema/users.py#L218-L223) (inside `UserPreferenceUpdate.mutate_and_get_payload`) is extracted into a helper so the blocked branch of `UserDeleteMutation` can reuse it. See sketch above. The helper is idempotent — re-calling it when the pref is already `"true"` is a no-op, so no duplicate tickets.

`create_account_deletion_ticket` signature gains an optional `blockers` keyword. The ticket body renders blockers as a readable list (model + qualifier + count + truncated IDs). Support sees exactly which rows need cleanup.

## Quick code reference

| Where                                                                                                                     | What lives there                                                                               |
| ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [core/models/users.py:72](backend/terraso_backend/apps/core/models/users.py#L72)                                          | `User` model — `delete()` override, `deletion_blockers()`, `soft_delete_policy_action` rewrite |
| [core/models/users.py:138](backend/terraso_backend/apps/core/models/users.py#L138)                                        | Existing `soft_delete_policy_action` — rewrite (drop DataEntry re-link)                        |
| [core/models/users.py:149](backend/terraso_backend/apps/core/models/users.py#L149)                                        | `User.undelete` — unchanged                                                                    |
| [core/admin.py:62](backend/terraso_backend/apps/core/admin.py#L62)                                                        | `UserAdmin` — add `delete_model`, `delete_queryset`, `_format_blocker_message`                 |
| [core/models/commons.py:69](backend/terraso_backend/apps/core/models/commons.py#L69)                                      | `BaseModel = SafeDeleteModel` foundation                                                       |
| [core/management/commands/harddelete.py](backend/terraso_backend/apps/core/management/commands/harddelete.py)             | Generic cron — untouched                                                                       |
| [project_management/models/sites.py:50-56](backend/terraso_backend/apps/project_management/models/sites.py#L50-L56)       | `Site.owner` — change to CASCADE (migration)                                                   |
| [project_management/models/projects.py:23-31](backend/terraso_backend/apps/project_management/models/projects.py#L23-L31) | `ProjectSettings` — remove (migration)                                                         |
| [project_management/models/projects.py:77](backend/terraso_backend/apps/project_management/models/projects.py#L77)        | `Project.settings` field — remove                                                              |
| [project_management/models/projects.py:81-93](backend/terraso_backend/apps/project_management/models/projects.py#L81-L93) | `Project.default_settings()` + `self.settings = ...` in `save()` — remove                      |
| [project_management/models/projects.py:48](backend/terraso_backend/apps/project_management/models/projects.py#L48)        | `Project` — add `soft_delete_policy_action` override                                           |
| [project_management/admin.py:19-21](backend/terraso_backend/apps/project_management/admin.py#L19-L21)                     | `admin.site.register(ProjectSettings)` — remove                                                |
| [project_management/models/**init**.py](backend/terraso_backend/apps/project_management/models/__init__.py)               | Drop `ProjectSettings` import + `__all__` entry                                                |
| [collaboration/models/memberships.py](backend/terraso_backend/apps/collaboration/models/memberships.py)                   | `Membership`, `MembershipList`; sole-manager query lives here                                  |
| [graphql/schema/users.py:136](backend/terraso_backend/apps/graphql/schema/users.py#L136)                                  | `UserDeleteMutation` — add `BlockerType` and `blockers` payload field                          |
| [graphql/schema/commons.py:294](backend/terraso_backend/apps/graphql/schema/commons.py#L294)                              | `BaseDeleteMutation.mutate_and_get_payload` (no longer parent of new flow)                     |

## Out of scope

- Cascading deletion of undeletable data (Groups, Landscapes, StoryMaps, DataEntries, VisualizationConfigs, TaxonomyTerms). Explicitly deferred; manual via HubSpot ticket.
- Migrating PROTECT FKs (`Group.created_by`, `Landscape.created_by`, `TaxonomyTerm.created_by`, `VisualizationConfig.created_by`) to `SET_NULL`. Not needed — the gate prevents reaching hard-delete on users with rows pointing through those FKs.
- Migrating DO_NOTHING FKs (`DataEntry.created_by`, `StoryMap.created_by`) to safer behavior. Same reasoning. Worth fixing for code-quality reasons but not blocking this work.
- Restoring `SiteNote.author` on undelete. Undelete is rare; partial-restoration is the accepted tradeoff.
- A snapshot/audit table of what was cascaded.
- Gating the `undelete_selected` and `hard_delete_soft_deleted` admin bulk actions. The gate is soft-delete-only by design (see Concerns #6).
- An "author" / "last editor" tracker on `Project.site_instructions`.
- Pre-confirmation-page UX in admin (showing blockers before the staff member confirms the delete). The post-confirmation banner is sufficient for v1.
- ~~**JWT / session invalidation**~~ — verified that the existing JWT middleware bounces soft-deleted users by default. No new code needed. (See "Self-service deletion (mobile-client)" section.)
- Hard-delete-time logic of any kind. The cron is untouched.
- **Web-client user-deletion pathway.** No existing flow and no plans to add one.
- **In-app rendering of blocker details.** Mobile shows the generic pending screen, not a list of what's blocking. Future iteration if product wants self-service resolution of blockers.
- **In-app resolution affordances** for blockers (transfer manager role, leave group, delete story map, etc.). Phase 2 if product wants in-app self-service blocker cleanup; today blocked users are routed to HubSpot.
- **Admin confirmation-page warning for custom-policy blockers.** Today the Django confirmation screen lists `on_delete=PROTECT` blockers but is silent about the `collaboration.Membership` policy override. Could be addressed by overriding `get_deleted_objects` on `UserAdmin` — deferred for a separate change so we ship the mobile flow first.
- **Misleading "Successfully deleted N user(s)" admin success message** when the bulk action skips a blocked user. Django's built-in `delete_selected` reports the original queryset count, not the actually-deleted count. Fix via `get_actions` override on `UserAdmin`. Deferred alongside the confirmation-page improvement above.

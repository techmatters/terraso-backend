# PostHog Analytics (server-side)

Server-side PostHog event capture from terraso-backend, on the **same PostHog
project as the mobile client** so events merge onto one person and one
DAU/WAU/MAU. Implemented in `apps/core/analytics.py`; hooked into auth, export,
soil-id, and the user/site/project delete mutations.

> Code comments reference the section numbers below (`§4`, `§5`). Keep them stable.

---

## 1. Config

`settings.py` (prettyconf `config()`), values from `~/secrets/terraso-backend/.env`:

- `POSTHOG_API_KEY` (default `""`) — same project key as mobile. Never committed.
- `POSTHOG_HOST` (default `https://us.i.posthog.com`, PostHog Cloud US).
- `POSTHOG_ENABLED` (default `false`).

Capture is a **no-op unless `POSTHOG_ENABLED` is true AND `POSTHOG_API_KEY` is
set**. Tests hard-disable it via an autouse fixture in `tests/conftest.py`, so
dev/test/CI never emit regardless of `.env`.

`analytics.capture()` is **fail-safe / fire-and-forget**: wrapped in try/except,
batches and sends on a background thread, and must never break a request.

---

## 2. Identity & person properties

- `distinct_id` = the **Terraso user UUID** (`User.id`) — same key mobile uses, so
  backend + mobile events land on the same person.
- Person props via `$set` (`analytics.user_person_properties(user)`): `email`,
  `email_domain`, `name` — matching mobile. Attached wherever we have `request.user`.
- **Token-based exports** resolve to the token **owner** via `_setup_token_user()`
  (`apps/export/views.py`), so `request.user` is always a real `User` — no
  anonymous/marker id needed.

Every backend event also carries `source: "backend"` and `platform` (= deploy
environment: `development`/`staging`/`production`, same key/values as mobile).

---

## 3. Division of labor with mobile

**No duplication** — each event has exactly one home. The backend captures only
the gaps mobile can't cover:

- **Server-only / lifecycle** events mobile can't see (refreshes, deletes).
- **Direct-to-backend** actions (`soil_id_lookup`, `export_file_download`) that
  also occur via web, partner API, shared links, and direct GraphQL — the backend
  is the only place that sees *every* one.

Backend does **not** emit: `login`, `site_created`, `project_created`,
`team_member_added`, `site_transfer` (mobile owns these).

> `soil_id_lookup` / `export_file_download` currently overlap mobile's copies.
> Backend is intended to be their single home; mobile's copies get retired later
> (§6). Don't double-count in insights meanwhile — split by `source`.

---

## 4. Backend events

| Event | Hook point | Properties (besides `source`/`platform` + `$set`) |
|---|---|---|
| `session_refreshed` | `RefreshAccessTokenView` (`apps/auth/views.py`) | `service_account` (bool) — active-user heartbeat (§5) |
| `soil_id_lookup` | `resolve_soil_id_result()` (`apps/soil_id/graphql/soil_id/resolvers.py`) | `latitude`, `longitude`, `status`, `data_region`, `has_input_data`, `match_count`, `cache_hit` |
| `export_file_download` | export views (`apps/export/views.py`) | `resource_type` (USER/PROJECT/SITE), `resource_name`, `format`, `via` (token/id) |
| `site_deleted` | `SiteDeleteMutation` | `site_name`, `in_project` (bool) |
| `project_deleted` | `ProjectDeleteMutation` | `project_name`, `transferred_sites` (bool) |
| `user_created` | OAuth first sign-up / `TokenExchangeView` / `UserAddMutation` | `auth_provider` (google/apple/microsoft/admin) |
| `user_deleted` | `UserDeleteMutation` | — (name/email on `$set`) |

> **PII note:** `export_file_download.resource_name` is a person's name/email when
> `resource_type == USER`. Accepted for now.

`soil_id_lookup` computes `cache_hit` before the lookup warms the cache, and only
runs that extra (index-only) query when `analytics.is_enabled()`.

Phase-2 candidates: `soil_data_recorded`, `story_map_created`/`published`,
`export_token_created`, `login_failed`/`signup_failed`.

---

## 5. Active users via `session_refreshed`

An active client hits `/auth/tokens` ~once per access-token lifetime, giving
PostHog's built-in DAU/WAU/MAU a heartbeat that covers **all** clients (incl.
web) — something mobile can't see.

- Resolution tracks `JWT_ACCESS_EXP_DELTA_SECONDS`. Treat it as a **lower bound**:
  the longer the TTL, the more active sessions go uncounted (a still-valid token
  triggers no refresh). Render is currently 1 day, planned 2h — shorter is better.
- Partner long-lived refresh tokens are tagged `service_account: true` (set in
  `apps/core/admin.py:create_partner_refresh_token`) so service accounts can be
  filtered out of human active-user counts.

---

## 6. Open items

1. **Retire mobile's `soil_id_lookup` / `export_file_download`** (mobile cleanup)
   once the backend owns them, to avoid double-counting.
2. **GDPR person-deletion** — optionally call PostHog's delete-person API on user
   hard-delete (phase-2 nicety).
3. **Mobile `login` quirk:** mobile overloads `platform` with the OS on its
   `login` event; backend always sets `platform` = environment. Worth aligning
   mobile later (move OS to its own `os` property).

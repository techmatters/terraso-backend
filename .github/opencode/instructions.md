# CI environment notes

Facts about this runner that the task prompt does not cover. Applies to you and
to every subagent you launch.

- **This job has no GitHub credentials.** You cannot push, cannot create remote
  branches, and cannot open or comment on pull requests. Do all of your work as
  local commits. A later step (running with credentials you never see) pushes
  your branches and opens the pull requests.
- **Branch names are load-bearing.** A later script finds your work by listing
  local branches matching `deps/*` and ordering them by commit ancestry, then
  derives each PR's base from that order. Use exactly
  `deps/YYYY-MM-DD-HH-MM/<group-name>`, and make each branch a real descendant
  of the branch below it (create it from the current HEAD, do not rebase it onto
  an unrelated base).
- **`uv tree --outdated -d 1 --exclude-newer="7 days"` rewrites `uv.lock`.** It
  re-resolves and records the cutoff as an `[options] exclude-newer-span` entry,
  so `uv.lock` is dirty as a side effect of merely *looking* at outdated
  packages. Run it once for discovery and be deliberate about which lock changes
  you commit to which branch.
- **`pyproject.toml` and `uv.lock` must agree, every time.** The Docker images
  install with `uv sync --frozen`, so a branch whose lockfile is stale fails to
  build — with an error that looks like a Docker problem, not a lockfile
  problem. Commit the regenerated lock alongside each `pyproject.toml` change,
  and keep the 7-day cutoff when you regenerate it, e.g.
  `uv lock --exclude-newer "7 days"` (or `uv lock --upgrade-package <name>
  --exclude-newer "7 days"`).
- **Dependency pins are exact (`==`)**, so an upgrade is a literal string change
  in `pyproject.toml` plus the matching lock update.
- **The real Make targets are `make test_unit` and `make lint`** (underscore, not
  hyphen). Both run inside Docker via `docker compose` and both are slow. The
  base image may already be built; if it is not, the first invocation builds it.
  Set `SOIL_ID_DATABASE_ENABLED=false` on the make command line to skip pulling
  a ~2 GB soil database image when it is not needed.
- **Do not reach for `DC_ENV=ci`.** The repo's own workflow runs `make ...
  DC_ENV=ci`, but `docker-compose.ci.yml` has no source bind mount: it tests
  whatever source is baked into a prebuilt image, so your edits would be
  invisible to it. This runner is configured so that the default `DC_ENV=dev`
  path works, including translations.
- **`make lint` is not just lint.** It runs `check_api_schema` (the committed
  `schema.graphql` must match the live schema) and `check_migrations` (no
  ungenerated model migrations) before Ruff. A dependency bump that changes
  Django/GraphQL/serialization behaviour can legitimately fail either of those.
- **Do not start the dev server or the database.** Nothing here needs a running
  app; `make test_unit` and `make lint` bring up what they need themselves.

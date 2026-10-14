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
- **Reading the top of the stack matters.** The same script starts at whatever
  branch HEAD points to and walks *down* to its base. If HEAD is on a stray
  branch that is not part of the chain, that branch gets the PRs and the real top
  gets none. Finish with HEAD checked out at the top of the stack.
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
- **The lint group is installed on the host**, which is why linting needs no
  Docker image at all: `uv run --only-group lint ruff check terraso_backend` and
  `uv run --only-group lint ruff format --diff terraso_backend`. This is the same
  toolchain `make format` uses.
- **`make test_unit` is Docker-only and expensive.** It depends on
  `check_rebuild`, which rebuilds the image whenever `md5sum pyproject.toml
  uv.lock` differs from the gitignored `.rebuild` file — so *any* branch switch
  that changes the lock triggers a full rebuild. Run it only at the top of the
  stack. The first invocation also builds the base image.
- **Do not reach for `DC_ENV=ci`.** The repo's own workflow runs `make ...
  DC_ENV=ci`, but `docker-compose.ci.yml` has no source bind mount: it tests
  whatever source is baked into a prebuilt image, so your edits would be
  invisible to it. This runner is configured so that the default `DC_ENV=dev`
  path works, including translations.
- **The soil-id database is disabled here** (`SOIL_ID_DATABASE_ENABLED=false`),
  because it is a ~2 GB pull only needed for global (HWSD) lookups. Do not
  re-enable it: nothing in `make test_unit` needs it, and integration tests are
  not part of this workflow.
- **`make lint` is not available to you** (it is Docker-based, see above). Its
  `check_api_schema` and `check_migrations` steps therefore do not run here;
  `.github/workflows/build.yml` runs them on the pull requests you produce.
- **Do not start the dev server or the database.** Nothing here needs a running
  app; `make test_unit` brings up what it needs itself.

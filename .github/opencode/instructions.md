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
- **Never change the GDAL version.** Leave `gdal` in `pyproject.toml`, the
  `libgdal`/snapshot pinning in `Dockerfile`, and every `gdal` entry in
  `uv.lock` exactly as you find them. The Python bindings are compiled from
  source against the native `libgdal-dev` headers, so the two versions only work
  when they are equal, and the bindings' `setup.py` refuses to build when the
  binding is the newer of the two. Those numbers move by hand, together, and
  deliberately — never as part of a dependency bump. `fiona`, `pyogrio`,
  `libkml-dev` and the rest of the GDAL family are in the same boat: leave them
  alone.
- **Do not start the dev server or the database.** Nothing here needs a running
  app.

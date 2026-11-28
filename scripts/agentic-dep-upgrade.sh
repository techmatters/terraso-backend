#!/usr/bin/env bash
#
# agentic-dep-upgrade.sh -- run the monthly dependency-upgrade agent.
# It should leave this repo checked out to the top of a branch stack
# which includes all of the dependency updates.
#
# Usage:
#   scripts/agentic-dep-upgrade.sh [base-branch]
#
# The base branch defaults to the currently checked-out branch.
#
set -euo pipefail

read -r -d '' PROMPT <<'PROMPT_EOF' || true
you are doing a monthly dependency update for this repo.

please update the package versions in pyproject.toml to the latest versions. you can find the right packages to upgrade to by running `uv tree --outdated -d 1`. note that `UV_EXCLUDE_NEWER` has been set in your env to provide a consistent dependency cooldown for all `uv` commands.

come up with a grouping for related updates, and for each group launch a subagent to read through the changelogs for the updated packages and determine whether there are any issues for the codebase. triage the subagents' findings in order to create stacked branches based on the current branch in order of how impactful the upgrade is, with the most impactful upgrades highest in the stack. the branch name format is `deps/YYYY-MM-DD-HH-MM/{your-name-for-this-group}`.

create each branch and commit the `pyproject.toml`/`uv.lock` changes for it.

then, working one branch at a time from the bottom in serial, resume that branch's subagent, telling it to implement any changes it needs to make for those dependency updates. for the sake of runner time, DO NOT run verification commands or ANYTHING that could cause the docker images to build. a separate step runs `make format`, `make lint` and `make test` once you are finished, and re-prompts you with whatever fails.

when all the changes are in, rebase the branches on each other so the stack's shape is proper again.

conclude by ensuring that the repo is checked out at the top of the stack. also ensure throughout this process that commit messages contain a clear description of the changes made and why they were made.
PROMPT_EOF

export UV_EXCLUDE_NEWER="${UV_EXCLUDE_NEWER:-7 days}"

BASE_BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$REPO_ROOT/.github/opencode}"

RUN_DIR="${RUNNER_TEMP:-/tmp}/opencode-logs"
mkdir -p "$RUN_DIR"

log() { printf '[agentic-dep-upgrade] %s\n' "$*"; }

command -v opencode >/dev/null 2>&1 || {
  echo "::error::opencode is not on PATH" >&2
  exit 1
}
command -v uv >/dev/null 2>&1 || {
  echo "::error::uv is not on PATH" >&2
  exit 1
}

# Fail before spending any tokens if the binary is unusable.
log "opencode $(opencode --version 2>/dev/null || echo '(version unknown)')"
log "config:   $OPENCODE_CONFIG_DIR"
log "base:     $BASE_BRANCH"

git rev-parse --verify --quiet "refs/heads/${BASE_BRANCH}" >/dev/null || {
  echo "::error::base branch '${BASE_BRANCH}' is not checked out locally" >&2
  exit 1
}

log "starting agent run"
opencode run \
  --standalone \
  --title "monthly dependency upgrade $(date -u +%Y-%m-%d)" \
  --auto \
  "$PROMPT" 2>&1 | tee "$RUN_DIR/agentic-dep-upgrade.log"

log "agent run finished"
log "local branches now present:"
git for-each-ref --format='  %(refname:short)' 'refs/heads/'

#!/usr/bin/env bash
#
# agentic-dep-upgrade.sh -- run the monthly dependency-upgrade agent.
#
# Usage:
#   OPENCODE_API_KEY=... scripts/agentic-dep-upgrade.sh [base-branch]
#
# The base branch defaults to the currently checked-out branch. The agent runs
# with no GitHub credentials: it may only make local commits. Pushing the
# resulting branch stack and opening pull requests is a separate, later step
# (scripts/push-stack.sh) that runs in a different environment.
#
set -euo pipefail

BASE_BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

: "${OPENCODE_API_KEY:?OPENCODE_API_KEY must be set}"

# CI config lives under .github/ so it never shadows a developer's own
# opencode.json. OPENCODE_CONFIG_DIR is loaded after the global config and after
# any project .opencode/ directory, so it wins for CI without affecting them.
#
# The model and its reasoning-effort variant are whatever that config says: this
# script deliberately does not pass --model, so the two cannot drift apart.
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
log "model:    from the config above, not passed on the command line"
log "base:     $BASE_BRANCH"

git rev-parse --verify --quiet "refs/heads/${BASE_BRANCH}" >/dev/null || {
  echo "::error::base branch '${BASE_BRANCH}' is not checked out locally" >&2
  exit 1
}

# Note that this script deliberately does not configure a commit identity. The
# workflow does that (globally, on a disposable runner) before calling this, so
# that running this by hand can never rewrite a developer's git config. If you do
# run it locally and the repo has no identity, the agent's first `git commit` will
# fail with "Please tell me who you are".

# The agent must not be able to *push* even if it tries: there is no token in
# the environment, and the checkout was made with persist-credentials: false.
# It is told so explicitly in .github/opencode/instructions.md, and the prompt
# below expects local branches only.
if git config --get remote.origin.url >/dev/null 2>&1; then
  log "remote.origin.url is present but carries no credential"
fi

read -r -d '' PROMPT <<'PROMPT_EOF' || true
you are doing a monthly dependency update for this repo.

please update the package versions in pyproject.toml to the latest versions that have been released for at least a week. you can find the right packages to upgrade to by running `uv tree --outdated -d 1 --exclude-newer="7 days"`.

come up with a grouping for related updates, and for each group launch a subagent to read through the changelogs for the updated packages and determine whether there are any issues for the codebase. triage the subagents' findings in order to create stacked branches based on the current branch in order of how impactful the upgrade is, with the most impactful upgrades highest in the stack. the branch name format is `deps/YYYY-MM-DD-HH-MM/{your-name-for-this-group}`.

create each branch and commit the `pyproject.toml`/`uv.lock` changes for it. then create a separate worktree for each branch — outside the repo, because the repo is bind-mounted into docker — and resume each branch's group's subagent in parallel, telling it to implement any changes it needs to make for those dependency updates. when all the changes are in, remove the worktrees (git will not rebase a branch that is checked out in another worktree) and rebase the branches on each other so the stack's shape is proper again.

two constraints for the sake of runner time — please respect them exactly:

- linting must not require building a docker image. do not run `make lint`: run the linter directly on the host instead, on each branch as you build it, with `uv run --only-group lint ruff check terraso_backend` and `uv run --only-group lint ruff format --diff terraso_backend`.
- `make test_unit` must only ever be run while checked out on the top of the stack. every branch changes `pyproject.toml`/`uv.lock`, and checking out a different branch forces docker to rebuild the image, so the suite runs exactly once per verification round, at the top. if a fix belongs on a lower branch, commit it there, rebase the branches above it, then check out the top again before re-running.

once you have all branches stacked up, launch a subagent to run `make test_unit` and then do one round of follow-up fixes (committed to the appropriate branch in the stack). this should be the first time you run tests in this process, ensure subagents launched before this point know not to run the tests. the command may take a while since it will need to install the docker image.

note that the subagent should not then re-run the tests after it has committed the fixes, it should just report whether the original run was green and what changes it made, if any. then launch a new subagent with the same instructions as the previous until things are green, or until it seems the agents aren't able to make progress.

conclude by ensuring that the repo is checked out at the top of the stack. also ensure throughout this process that commit messages contain a clear but concise description of the changes made and why they were made.
PROMPT_EOF

drain_opencode_logs() {
  local log_dir="${XDG_DATA_HOME:-$HOME/.local/share}/opencode/log"
  [ -d "$log_dir" ] || return 0
  local newest
  newest="$(find "$log_dir" -type f -name '*.log' -printf '%T@ %p\n' 2>/dev/null |
    sort -n | tail -n1 | cut -d' ' -f2-)"
  [ -n "$newest" ] || return 0
  echo "::group::tail of $(basename "$newest")"
  tail -n 200 "$newest"
  echo "::endgroup::"
}

# --standalone gives the run a private server instead of the shared background
# service. This matters on a CI runner: the environment (including
# OPENCODE_API_KEY) belongs to this process, and the private server is the one
# that makes the model requests.
log "starting agent run"
set +e
opencode run \
  --standalone \
  --title "monthly dependency upgrade $(date -u +%Y-%m-%d)" \
  --auto \
  "$PROMPT" 2>&1 | tee "$RUN_DIR/agentic-dep-upgrade.log"
status="${PIPESTATUS[0]}"
set -e

if [ "$status" -ne 0 ]; then
  echo "::error::opencode exited with status ${status}"
  drain_opencode_logs
  exit "$status"
fi

log "agent run finished"
log "local branches now present:"
git for-each-ref --format='  %(refname:short)' 'refs/heads/'

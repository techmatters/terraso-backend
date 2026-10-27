#!/usr/bin/env bash
#
# agentic-dep-validate.sh -- validate a branch stack, and
# hand any failures back to an agent to repair.
#
# Usage:
#   scripts/agentic-dep-validate.sh <base-branch>
#
# Expects the repo checked out at the top of a stack of branches sitting on
# <base-branch>. Runs `make format`, `make lint` and `make test` there;
# if anything fails, a fresh agent run is given the output and expected to
# fix the layer that caused it and rebase the stack. Repeats up to two more
# times, then fails.
set -euo pipefail

read -r -d '' REPAIR_PROMPT <<'PROMPT_EOF' || true
the monthly dependency upgrade is laid out as a stack of branches, and a validation run at the top of the stack failed. the output is below.

fix each failure on the layer of the stack that introduced it, not at the top: if a test breaks for a package upgraded in the fourth layer, the fix belongs in the fourth layer's commit, so that every layer still builds and passes on its own.

commit each fix to the branch that owns it. after changing a branch, rebase the branches above it onto it, so that each branch stays a direct descendant of the layer below it and the bottom layer stays a direct descendant of the base branch.

do not change dependency versions to make a failure go away, and do not touch the gdal version at all. fix the code, not the pins. if a failure really is a behaviour change in an upgraded package, say so in the commit message.

do not run the validation yourself: `make test` rebuilds the docker images, and switching branches has to do that again, so it is not worth it. the caller re-runs validation when you are done.

finish with the repo checked out at the top of the stack.
PROMPT_EOF

export UV_EXCLUDE_NEWER="${UV_EXCLUDE_NEWER:-7 days}"

BASE_BRANCH="${1:-}"
if [ -z "$BASE_BRANCH" ]; then
  echo "usage: $(basename "$0") <base-branch>" >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$REPO_ROOT/.github/opencode}"

RUN_DIR="${RUNNER_TEMP:-/tmp}/opencode-logs"
mkdir -p "$RUN_DIR"

# One validation run, then up to two repair runs.
MAX_ATTEMPTS=3
# Enough of a pytest dump to see the failures; the full logs are on disk and get
# uploaded, and the repair prompt points at them.
TAIL_LINES=400

log() { printf '[agentic-dep-validate] %s\n' "$*"; }
die() { printf '::error::%s\n' "$*" >&2; exit 1; }

command -v opencode >/dev/null 2>&1 || die "opencode is not on PATH"

log "opencode $(opencode --version 2>/dev/null || echo '(version unknown)')"
log "config:   $OPENCODE_CONFIG_DIR"
log "base:     $BASE_BRANCH"

git rev-parse --verify --quiet "refs/heads/${BASE_BRANCH}" >/dev/null \
  || die "base branch '${BASE_BRANCH}' does not exist locally"

# Fails unless HEAD is the top of the stack: nothing else may sit above it.
assert_head_is_top() {
  local head top other
  head="$(git rev-parse --abbrev-ref HEAD)"
  case "$head" in
    deps/*) ;;
    *) die "HEAD is ${head}, which is not a deps/* branch" ;;
  esac
  top="$(git rev-parse "refs/heads/${head}")"
  while IFS= read -r other; do
    [ "$other" = "$head" ] && continue
    if git merge-base --is-ancestor "$top" "refs/heads/${other}"; then
      die "HEAD is ${head}, but ${other} is stacked above it; the stack must be left checked out at its top"
    fi
  done < <(git for-each-ref --format='%(refname:short)' 'refs/heads/')
}

# Every layer was created from the tip of the layer below it, so walking the top
# branch's history and picking out the commits with a branch pointing at them
# yields the layers. Printed bottom first.
stack_branches() {
  local base_tip top_tip sha name i
  local -a rev=()
  declare -A tip_name=()
  base_tip="$(git rev-parse "refs/heads/${BASE_BRANCH}")"
  top_tip="$(git rev-parse "refs/heads/$(git rev-parse --abbrev-ref HEAD)")"
  while read -r sha name; do
    tip_name["$sha"]="$name"
  done < <(git for-each-ref --format='%(objectname) %(refname:short)' 'refs/heads/')
  while read -r sha; do
    [ "$sha" = "$base_tip" ] && break
    [ -n "${tip_name[$sha]:-}" ] && rev+=("${tip_name[$sha]}")
  done < <(git rev-list --topo-order "$top_tip")
  for ((i = ${#rev[@]} - 1; i >= 0; i--)); do
    printf '%s\n' "${rev[i]}"
  done
}

# Writes the case for a repair run to $2, or leaves it empty if everything
# passed. Runs all three targets so that one repair run can address all of it.
run_validation() {
  local attempt="$1" out="$2" target logf
  for target in format lint test; do
    logf="${RUN_DIR}/validate-${attempt}-${target}.log"
    log "make ${target}"
    if ! make "$target" 2>&1 | tee "$logf"; then
      printf '### make %s failed\n\n%s\n\n' "$target" "$(tail -n "$TAIL_LINES" "$logf")" >>"$out"
    fi
  done
  # `make format` rewrites files in place, and uncommitted changes have nowhere
  # to live once the branches are pushed, so a dirty tree is a failure too.
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    {
      printf '### uncommitted changes after validation\n\n'
      git status --short --untracked-files=no
      printf '\n'
      git diff
      printf '\n'
    } >>"$out"
  fi
}

HEAD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$HEAD_BRANCH" = "$BASE_BRANCH" ]; then
  log "nothing to validate: HEAD is ${BASE_BRANCH}"
  exit 0
fi

assert_head_is_top

mapfile -t chain < <(stack_branches)
[ "${#chain[@]}" -gt 0 ] || die "no deps/* branches between ${BASE_BRANCH} and ${HEAD_BRANCH}"
log "stack (bottom -> top): ${chain[*]}"

passed=0
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  failures="${RUN_DIR}/validate-${attempt}-failures.txt"
  : >"$failures"
  run_validation "$attempt" "$failures"

  if [ ! -s "$failures" ]; then
    log "validation passed on attempt ${attempt}"
    passed=1
    break
  fi

  log "validation failed on attempt ${attempt}: ${failures}"
  [ "$attempt" -lt "$MAX_ATTEMPTS" ] || break

  prompt="${REPAIR_PROMPT}

the stack, bottom to top, sits on \`${BASE_BRANCH}\`:
$(printf '  %s\n' "${chain[@]}")

the full logs are in ${RUN_DIR}. what follows is the failing output.
$(printf -- '---\n')
$(cat "$failures")"

  log "starting repair run ${attempt} of $((MAX_ATTEMPTS - 1))"
  opencode run \
    --standalone \
    --title "dependency upgrade repair ${attempt} $(date -u +%Y-%m-%d)" \
    --auto \
    "$prompt" 2>&1 | tee "${RUN_DIR}/validate-${attempt}-repair.log"

  assert_head_is_top
  mapfile -t chain < <(stack_branches)
  [ "${#chain[@]}" -gt 0 ] \
    || die "the stack is no longer contiguous after repair run ${attempt}"
done

[ "$passed" -eq 1 ] || die "validation still failing after ${MAX_ATTEMPTS} attempts"

log "leaving the top of the stack checked out:"
git branch --list --format='  %(refname:short)' "$BASE_BRANCH" 'deps/*'

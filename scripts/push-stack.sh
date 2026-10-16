#!/usr/bin/env bash
#
# push-stack.sh -- push the agent's dependency branches and open one PR per layer.
#
# Usage:
#   GH_TOKEN=... scripts/push-stack.sh <base-branch>
#
# This assumes the happy path: HEAD is checked out at the top of a stack of
# `deps/*` branches, each sitting on the one below it, and the bottom one sitting
# on <base-branch>. Anything else is an error rather than something to recover
# from.
#
# It is also not idempotent: if the branches or the pull requests already exist,
# it fails. There is no force-push and no "update the existing PR" path -- a
# re-run either finds that HEAD is the base branch (nothing to do) or it fails
# loudly.
#
# SECURITY POSTURE
#   This script runs from the working tree, which the agent had write access to,
#   and it holds an app installation token. That is a deliberate choice, not an
#   oversight: the token is scoped to this repository and cannot push to `main`
#   (keep `main` protected), so the worst case is junk branches and junk PRs,
#   which is what the human review on those PRs is for.
#
#   There is deliberately no hardening here. The agent shares the runner and the
#   user with this script, so anything file- or environment-based -- pinning a
#   hash of this file, scrubbing .git/config, clearing $GITHUB_ENV redirectors --
#   can be defeated from the preceding step. If this ever needs to be a real
#   boundary, the agent and the publish step have to run in separate jobs.
#
set -euo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  echo "usage: $(basename "$0") <base-branch>" >&2
  exit 2
fi

BRANCH_PREFIX="deps/"

die() { printf '::error::%s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*"; }

: "${GH_TOKEN:?GH_TOKEN must be set}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
REPO="$GITHUB_REPOSITORY"

command -v gh >/dev/null 2>&1 || die "gh is not on PATH"
command -v git >/dev/null 2>&1 || die "git is not on PATH"

# Make `git push` use the app token: this installs gh as git's credential helper
# in the global git config, and gh reads GH_TOKEN from the environment.
gh auth setup-git

head_branch="$(git rev-parse --abbrev-ref HEAD)"

# A monthly run has no work to do more often than you would think: every pin is
# already on a version that is at least a week old.
if [ "$head_branch" = "$BASE" ]; then
  log "Nothing to push: HEAD is ${BASE}."
  exit 0
fi

case "$head_branch" in
  "${BRANCH_PREFIX}"*) ;;
  *) die "HEAD is ${head_branch}, which is not a ${BRANCH_PREFIX}* branch" ;;
esac

git rev-parse --verify --quiet "refs/heads/${BASE}" >/dev/null \
  || die "base branch '${BASE}' does not exist locally"

base_tip="$(git rev-parse "refs/heads/${BASE}")"
top_tip="$(git rev-parse "refs/heads/${head_branch}")"

git merge-base --is-ancestor "$base_tip" "$top_tip" \
  || die "${head_branch} is not built on ${BASE}"

# The walk below only ever sees the layers underneath HEAD, so it cannot tell on
# its own that HEAD is the top. Check that directly: nothing else may sit above it.
while IFS= read -r other; do
  [ "$other" = "$head_branch" ] && continue
  git merge-base --is-ancestor "$top_tip" "refs/heads/${other}" \
    && die "HEAD is ${head_branch}, but ${other} is stacked above it; check out the top of the stack"
done < <(git for-each-ref --format='%(refname:short)' 'refs/heads/')

# Work out the stack. Every layer was created from the tip of the layer below it,
# so walking the top branch's history from newest to oldest and picking out the
# commits that have a branch pointing at them yields the layers in order, ending
# when the base branch's tip is reached.
declare -A branch_at_tip=()
while read -r commit name; do
  branch_at_tip["$commit"]="$name"
done < <(git for-each-ref --format='%(objectname) %(refname:short)' 'refs/heads/')

chain_rev=()  # top -> bottom
while read -r commit; do
  [ "$commit" = "$base_tip" ] && break
  name="${branch_at_tip[$commit]:-}"
  [ -n "$name" ] && chain_rev+=("$name")
done < <(git rev-list --topo-order "$top_tip")

[ "${#chain_rev[@]}" -gt 0 ] \
  || die "no ${BRANCH_PREFIX}* branches between ${BASE} and ${head_branch}"
[ "${chain_rev[0]}" = "$head_branch" ] \
  || die "HEAD is ${head_branch}, but the top of the stack is ${chain_rev[0]}"

chain=()  # bottom -> top
for ((i = ${#chain_rev[@]} - 1; i >= 0; i--)); do
  chain+=("${chain_rev[i]}")
done

log "base branch: ${BASE}"
log "stack (bottom -> top): ${chain[*]}"

# ---------------------------------------------------------------------------
# Push each layer and open its pull request
# ---------------------------------------------------------------------------
pr_numbers=()
pr_urls=()
total="${#chain[@]}"

for idx in "${!chain[@]}"; do
  branch="${chain[$idx]}"
  parent="$BASE"
  if [ "$idx" -gt 0 ]; then
    parent="${chain[$((idx - 1))]}"
  fi
  layer="$((idx + 1))"

  log ""
  log "-- layer ${layer}/${total}: ${branch}  (base: ${parent})"

  git push --quiet origin "refs/heads/${branch}:refs/heads/${branch}" \
    || die "could not push ${branch}: it already exists on the remote with different history"

  # The PR title comes from the layer's earliest commit -- the one that introduced
  # the pyproject/lock change -- so it describes the layer rather than the last fix
  # that touched it.
  title="$(git log --reverse --format='%s' \
    "refs/heads/${parent}..refs/heads/${branch}" | sed -n 1p)"
  title="${title:-update dependency group ${branch##*/}}"
  # .github/workflows/check-commits.yml validates PR titles against a
  # conventional-commit pattern, so synthesise a conforming one if needed.
  if ! printf '%s' "$title" | grep -Eq '^[a-z]+(\([^)]+\))?!?:[[:space:]]+.+$'; then
    title="chore(deps): ${title}"
  fi
  log "   title: ${title}"

  body_file="$(mktemp)"
  {
    printf 'Automated dependency upgrade — layer %s of %s.\n\n' "$layer" "$total"
    printf 'Targets `%s`.\n\n' "$parent"
    printf '### Commits\n\n'
    git log --reverse --format='* %s' "refs/heads/${parent}..refs/heads/${branch}"
    printf '\n'
    git log --reverse --format='%b' "refs/heads/${parent}..refs/heads/${branch}" \
      | sed '/^$/d'
    printf '\n---\n\n'
    printf 'Opened by the `agentic dependency upgrade` workflow. Review this layer only.\n'
  } > "$body_file"

  url="$(gh pr create --repo "$REPO" --base "$parent" --head "$branch" \
    --title "$title" --body-file "$body_file")" \
    || die "could not open a pull request for ${branch}"
  number="$(gh pr view --repo "$REPO" "$url" --json number --jq '.number')"
  log "   opened PR #${number}: ${url}"

  pr_numbers+=("$number")
  pr_urls+=("$url")
done

# ---------------------------------------------------------------------------
# Link the pull requests into a formal stack
# ---------------------------------------------------------------------------
# The PR bases already form a stack; this is what makes GitHub render it as one.
if [ "${#pr_numbers[@]}" -lt 2 ]; then
  log ""
  log "only ${#pr_numbers[@]} layer, so there is no stack to form"
else
  stack_args=()
  for number in "${pr_numbers[@]}"; do
    stack_args+=(-f "pull_requests[]=${number}")
  done
  out="$(gh api --method POST "repos/${REPO}/stacks" "${stack_args[@]}" 2>&1)" \
    || die "failed to link the pull requests into a stack: ${out}"
  log ""
  log "created a stack of ${#pr_numbers[@]} layers"
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    printf '## Dependency upgrade stack\n\n'
    printf 'Base branch: `%s`\n\n' "$BASE"
    printf '| layer | branch | base | PR |\n'
    printf '| --- | --- | --- | --- |\n'
    for idx in "${!chain[@]}"; do
      parent="$BASE"
      if [ "$idx" -gt 0 ]; then
        parent="${chain[$((idx - 1))]}"
      fi
      printf '| %s | `%s` | `%s` | %s |\n' \
        "$((idx + 1))" "${chain[$idx]}" "$parent" "${pr_urls[$idx]}"
    done
    printf '\n'
  } >> "$GITHUB_STEP_SUMMARY"
fi

log ""
log "done: ${#pr_urls[@]} pull request(s)"
for url in "${pr_urls[@]}"; do
  log "  ${url}"
done

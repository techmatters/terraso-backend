#!/usr/bin/env bash
#
# push-stack.sh -- push the agent's dependency branches and open one PR per layer.
#
# Usage:
#   GH_TOKEN=... scripts/push-stack.sh <base-branch>
#
# <base-branch> is what the bottom PR targets. Layer order is derived from commit
# ancestry rather than from anything the agent reported, so the stack is correct
# even if the agent's own bookkeeping is wrong; a chain that does not line up is a
# hard error rather than a misleading set of PRs.
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
warn() { printf '::warning::%s\n' "$*" >&2; }
log() { printf '%s\n' "$*"; }

: "${GH_TOKEN:?GH_TOKEN must be set}"
command -v gh >/dev/null 2>&1 || die "gh is not on PATH"
command -v git >/dev/null 2>&1 || die "git is not on PATH"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
REPO="${GITHUB_REPOSITORY}"

# Make `git push` use the app token. This configures gh as git's credential
# helper in the global git config; gh reads GH_TOKEN from the environment.
gh auth setup-git

log "repo:        ${REPO}"
log "base branch: ${BASE}"

git rev-parse --verify --quiet "refs/heads/${BASE}" >/dev/null \
  || die "base branch '${BASE}' does not exist locally"

# ---------------------------------------------------------------------------
# 1. Discover the stack: walk down from the top to the base
# ---------------------------------------------------------------------------
# Only local branches are considered. A fresh CI checkout has the base branch
# plus whatever the agent created, so branches pushed by earlier runs cannot be
# mistaken for this run's work.
#
# The chain comes from commit ancestry, not from anything the agent reported:
# start at the top of the stack, repeatedly step to the closest ancestor that is
# also one of our branches, and stop when the base branch is reached. Each step
# is verified with `merge-base --is-ancestor`.
#
# Deliberately not a global sort by commit count: two branches can sit at the
# same depth (a stray sibling rather than a chain), and ordering by depth alone
# either silently drops one of them or yields a chain whose PR bases are a
# fiction. Walking down from the top ignores strays and reports them instead.
#
# NB: the pattern must not be 'refs/heads/*' -- git's ref globbing is
# segment-aware, so a single '*' does not match 'refs/heads/deps/2026-.../x'.
# A bare prefix lists everything and the `case` below does the filtering.
candidates=()
while IFS= read -r branch; do
  [ "$branch" = "$BASE" ] && continue
  case "$branch" in
    "${BRANCH_PREFIX}"*) ;;
    *) continue ;;
  esac
  if git merge-base --is-ancestor "refs/heads/${BASE}" "refs/heads/${branch}"; then
    candidates+=("$branch")
  else
    warn "ignoring ${branch}: it is not a descendant of ${BASE}"
  fi
done < <(git for-each-ref --format='%(refname:short)' 'refs/heads/')

[ "${#candidates[@]}" -gt 0 ] || die "no ${BRANCH_PREFIX}* branches found on top of ${BASE}"

commits_above_base() {
  git rev-list --count "refs/heads/${BASE}..refs/heads/${1}"
}

# Prefer HEAD as the top of the stack (the agent is asked to finish there), and
# fall back to the deepest branch when it is not.
head_ref="$(git rev-parse --abbrev-ref HEAD)"
top=""
for branch in "${candidates[@]}"; do
  if [ "$branch" = "$head_ref" ]; then
    top="$branch"
    break
  fi
done
if [ -z "$top" ]; then
  top="${candidates[0]}"
  for branch in "${candidates[@]}"; do
    if [ "$(commits_above_base "$branch")" -gt "$(commits_above_base "$top")" ]; then
      top="$branch"
    fi
  done
  warn "HEAD is ${head_ref}, which is not a ${BRANCH_PREFIX}* branch; using ${top} as the top of the stack"
fi

chain_rev=()
current="$top"
steps=0
while [ "$current" != "$BASE" ]; do
  steps=$((steps + 1))
  [ "$steps" -le 500 ] || die "gave up walking down from ${top}: no path back to ${BASE}"

  parent="$BASE"
  parent_depth="$(commits_above_base "$BASE")"
  for branch in "${candidates[@]}"; do
    [ "$branch" = "$current" ] && continue
    git merge-base --is-ancestor "refs/heads/${branch}" "refs/heads/${current}" || continue
    depth="$(commits_above_base "$branch")"
    if [ "$depth" -ge "$parent_depth" ]; then
      parent="$branch"
      parent_depth="$depth"
    fi
  done

  chain_rev+=("$current")
  current="$parent"
done

chain=()
for ((i = ${#chain_rev[@]} - 1; i >= 0; i--)); do
  chain+=("${chain_rev[i]}")
done

[ "${#chain[@]}" -gt 0 ] || die "could not order the ${BRANCH_PREFIX}* branches"

# Anything not on the path is not part of this stack and gets no PR. Say so
# rather than dropping it quietly.
for branch in "${candidates[@]}"; do
  on_path=""
  for chained in "${chain[@]}"; do
    if [ "$chained" = "$branch" ]; then on_path=1; break; fi
  done
  [ -n "$on_path" ] || warn "${branch} is not part of the chain from ${top} to ${BASE}; it will get no pull request"
done

# Each layer must actually sit on the one below it, otherwise the bases we set
# on the PRs would be a fiction (and the Stacks API would reject the stack).
prev="$BASE"
for branch in "${chain[@]}"; do
  git merge-base --is-ancestor "refs/heads/${prev}" "refs/heads/${branch}" \
    || die "${branch} is not stacked on ${prev}; refusing to open a misleading stack"
  prev="$branch"
done

log "stack (bottom -> top): ${chain[*]}"

# ---------------------------------------------------------------------------
# 2. Push each layer and open (or refresh) its PR
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
  log "── layer ${layer}/${total}: ${branch}  (base: ${parent})"

  # --force because a re-run of the same workflow reuses the branch names that
  # the agent derives from a timestamp; these branches are bot-owned and guarded
  # by the deps/ prefix filter above.
  git push --quiet --force origin "refs/heads/${branch}:refs/heads/${branch}" \
    || die "failed to push ${branch}"

  # PR title comes from the layer's earliest commit -- the one that introduced
  # the pyproject/lock change -- so it describes the layer rather than the last
  # fix that touched it.
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

  existing="$(gh pr list --repo "$REPO" --head "$branch" --state open \
    --json number --jq '.[0].number // empty')"

  if [ -n "$existing" ]; then
    gh pr edit --repo "$REPO" "$existing" \
      --title "$title" --body-file "$body_file" >/dev/null
    number="$existing"
    url="$(gh pr view --repo "$REPO" "$existing" --json url --jq '.url')"
    log "   updated PR #${number}: ${url}"
  else
    url="$(gh pr create --repo "$REPO" --base "$parent" --head "$branch" \
      --title "$title" --body-file "$body_file")"
    number="$(gh pr view --repo "$REPO" "$url" --json number --jq '.number')"
    log "   opened PR #${number}: ${url}"
  fi

  pr_numbers+=("$number")
  pr_urls+=("$url")
done

# ---------------------------------------------------------------------------
# 3. Link the pull requests into a formal stack
# ---------------------------------------------------------------------------
# The PR bases already form a stack; this is what makes GitHub render it as one.
if [ "${#pr_numbers[@]}" -lt 2 ]; then
  warn "only ${#pr_numbers[@]} PR(s) opened; a stack needs at least two layers"
else
  stack_args=()
  for number in "${pr_numbers[@]}"; do
    stack_args+=(-f "pull_requests[]=${number}")
  done

  if out="$(gh api --method POST "repos/${REPO}/stacks" "${stack_args[@]}" 2>&1)"; then
    log ""
    log "created a stack of ${#pr_numbers[@]} layers"
  else
    # Already stacked (for example a re-run that refreshed existing PRs)?
    already="$(gh api "repos/${REPO}/stacks?pull_request=${pr_numbers[0]}" \
      --jq '.[0].number // empty' 2>/dev/null || true)"
    if [ -n "$already" ]; then
      log "stack #${already} already exists; left as is"
    else
      case "$out" in
        # Entitlement/availability problem, not a problem with the PRs.
        *"Not Found"*|*404*)
          warn "the Stacks API is unavailable here (stacked PRs may not be enabled for ${REPO})."
          warn "The PRs are still based on each other; GitHub will offer to link them into a stack."
          ;;
        *)
          # 422 means the PR chain itself does not form a valid stack -- our bug.
          die "failed to create the stack: ${out}"
          ;;
      esac
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 4. Report
# ---------------------------------------------------------------------------
head_ref="$(git rev-parse --abbrev-ref HEAD)"
top="${chain[$((total - 1))]}"
if [ "$head_ref" = "$top" ]; then
  log "HEAD is at the top of the stack (${top})"
else
  warn "HEAD is ${head_ref}, but the top of the stack is ${top}"
fi

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

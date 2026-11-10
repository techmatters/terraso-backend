#!/usr/bin/env python3
# Copyright © 2026 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.
"""Refresh ~/secrets/terraso-backend/.env from env.sample, keeping your real values.

Use this after env.sample gains new keys / comments and you want to adopt the
updated template without re-entering your secrets.

What it does:
  1. Back up the current .env to .env.<YYYYMMDD-HHMMSS> in the same directory.
  2. Rebuild .env from env.sample (so you get the template's structure,
     comments, and any newly-added keys).
  3. For every `KEY=value` in env.sample — active OR commented — substitute the
     value AND the commented/active status you had in the backup, matched per
     block by (section, key). So your real values are preserved whether you had
     the line active (e.g. the LOCAL endpoint) or commented (e.g. a real bucket
     name filled into the commented STAGING block); the sample's placeholder
     never overwrites a value you set. Keys the template added that your backup
     lacked keep the sample's placeholder. Matching is per block, so the same key
     across DEV/STAGING/PROD/LOCAL never cross-contaminates. (A key that is unique
     in both files still matches even if its section header was renamed.)
  4. Append trailing sections:
       a. a COMMENTED list of keys that are new in env.sample (not in your old
          .env) — review and fill these in (they hold placeholders above).
       b. `KEY=value` lines (commented/active status kept) for values from your
          old .env that have no slot in the current template, so nothing is lost.

Paths (override via env vars if needed):
  TERRASO_SECRETS_DIR   default: ~/secrets/terraso-backend   (holds .env)
  ENV_SAMPLE_PATH       default: <repo>/env.sample

SAFETY: this script prints only key NAMES, counts, and file paths to stdout —
never any values — so its output is safe to share. It reads your secrets dir;
run it yourself.

Usage:
  python3 scripts/refresh_env.py
"""

import os
import re
import shutil
import sys
from datetime import datetime

SECRETS_DIR = os.path.expanduser(
    os.environ.get("TERRASO_SECRETS_DIR", "~/secrets/terraso-backend")
)
ENV_PATH = os.path.join(SECRETS_DIR, ".env")

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
SAMPLE_PATH = os.environ.get("ENV_SAMPLE_PATH", os.path.join(_REPO_ROOT, "env.sample"))

# KEY=value, allowing optional leading whitespace and an `export ` prefix.
# Everything after the first `=` is the value (no inline-comment stripping, to
# match how docker-compose env_file / the app read these).
ASSIGN_RE = re.compile(r"^(\s*)(export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# A commented-out assignment: `#KEY=value` or `# KEY=value`.
COMMENT_ASSIGN_RE = re.compile(r"^\s*#\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# A block/section header: a comment whose text starts with divider chars (box
# drawing, '=' or '-') then a name, e.g. "# ─── STAGING (…) ───" or
# "# ═══ S3 / file storage ═══". The first word names the block; we use it to
# keep a key that repeats across blocks (DEV/STAGING/PROD/LOCAL) distinct.
HEADER = re.compile(r"^#\s*[─═=-]{2,}\s*([A-Za-z]+)")

RULE = "# " + "-" * 70


def is_comment(line):
    return line.lstrip().startswith("#")


def section_name(line):
    m = HEADER.match(line)
    return m.group(1).upper() if m else None


def parse_assignment(line):
    """(key, value, commented) for an active or commented assignment line, else
    (None, None, False). A header or prose comment is not an assignment."""
    if is_comment(line):
        cm = COMMENT_ASSIGN_RE.match(line)
        if cm:
            return cm.group(1), cm.group(2), True
        return None, None, False
    m = ASSIGN_RE.match(line)
    if m:
        return m.group(3), m.group(4), False
    return None, None, False


def iter_assignments(lines):
    """Yield (section, key, value, commented) for each assignment line, tracking
    the nearest preceding header as `section`, so the same key under DEV/STAGING/
    PROD/LOCAL stays distinct. Keys before any header get section ""."""
    section = ""
    for line in lines:
        sec = section_name(line)
        if sec is not None:
            section = sec
            continue
        key, value, commented = parse_assignment(line)
        if key is not None:
            yield section, key, value, commented


def emit(key, value, commented):
    """Render an assignment, commented or not."""
    line = f"{key}={value}"
    return f"# {line}" if commented else line


def rebuild_lines(sample_lines, backup_lines):
    """Pure transform: return (out_lines, stats). No file IO — unit-testable.

    Each key keeps the VALUE *and* the commented/active status it had in your
    backup, matched per block by (section, key). So a real bucket name you filled
    into the (commented) STAGING block stays there commented, your active LOCAL
    endpoint stays active, and nothing commented in the sample overwrites a value
    you already set — exactly how active values have always been preserved. Keys
    only the template has keep the sample's line; keys only you had go at the end.
    """
    # Index backup assignments by (section, key) -> (value, commented).
    backup_vals = {}
    key_count = {}
    for section, key, value, commented in iter_assignments(backup_lines):
        backup_vals[(section, key)] = (value, commented)
        key_count[key] = key_count.get(key, 0) + 1
    # Keys occurring exactly once in the backup — used as a header-rename fallback,
    # but ONLY when the key is also unique in the sample, so matching stays
    # unambiguous (a key repeated across blocks always needs an exact section hit).
    unique_pair = {k: (s, k) for (s, k) in backup_vals if key_count[k] == 1}

    sample_count = {}
    for _s, k, _v, _c in iter_assignments(sample_lines):
        sample_count[k] = sample_count.get(k, 0) + 1

    # Rebuild from the sample, swapping in the backup's value+status per block.
    out = []
    substituted = []
    used = set()
    section = ""
    for line in sample_lines:
        sec = section_name(line)
        if sec is not None:
            section = sec
            out.append(line)
            continue
        key, _, _ = parse_assignment(line)
        if key is None:
            out.append(line)  # blank or prose comment
            continue
        if (section, key) in backup_vals:
            pair = (section, key)
        elif sample_count.get(key) == 1 and key in unique_pair:
            pair = unique_pair[key]  # same key moved under a renamed header
        else:
            out.append(line)  # template-only key: keep the sample's default
            continue
        value, commented = backup_vals[pair]
        out.append(emit(key, value, commented))
        substituted.append(key)
        used.add(pair)

    # a. Active keys new in the template (no value of yours to preserve).
    seen = set()
    new_keys = []
    for s, k, _v, commented in iter_assignments(sample_lines):
        if not commented and (s, k) not in used and k not in seen:
            new_keys.append(k)
            seen.add(k)
    # b. Your values with no slot in the template, preserved (status kept).
    orphans = [(k, val, com) for (s, k), (val, com) in backup_vals.items()
               if (s, k) not in used]

    if new_keys:
        out += [
            "",
            RULE,
            "# Keys new in env.sample (not in your previous .env) — review & fill in.",
            "# They currently hold the sample's placeholder values above.",
            RULE,
        ]
        out += [f"#   {k}" for k in new_keys]

    if orphans:
        out += [
            "",
            RULE,
            "# Values from your previous .env with no slot in the current template,",
            "# preserved (keeping their commented/active status) so nothing is lost.",
            "# Move or delete as appropriate.",
            RULE,
        ]
        out += [emit(k, val, com) for k, val, com in orphans]

    stats = {
        "substituted": substituted,
        "new_keys": new_keys,
        "orphan_keys": [k for k, _v, _c in orphans],
    }
    return out, stats


def main():
    if not os.path.isfile(SAMPLE_PATH):
        sys.exit(f"ERROR: env.sample not found at {SAMPLE_PATH}")
    if not os.path.isfile(ENV_PATH):
        sys.exit(f"ERROR: no existing .env at {ENV_PATH} (nothing to back up).")

    # 1. Back up the current .env.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(SECRETS_DIR, f".env.{stamp}")
    if os.path.exists(backup_path):
        sys.exit(f"ERROR: backup already exists at {backup_path}; aborting.")
    shutil.copy2(ENV_PATH, backup_path)

    with open(backup_path, encoding="utf-8") as f:
        backup_lines = f.read().splitlines()
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        sample_lines = f.read().splitlines()

    out, stats = rebuild_lines(sample_lines, backup_lines)

    # Write the new .env, preserving the backup's file mode (e.g. 600).
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    shutil.copymode(backup_path, ENV_PATH)

    # Summary — names, counts, and paths only. No values.
    def names(keys):
        return ", ".join(keys) if keys else "(none)"

    print(f"Backed up current .env -> {backup_path}")
    print(f"Rebuilt {ENV_PATH} from {SAMPLE_PATH}")
    print(f"Preserved {len(stats['substituted'])} of your value(s) (per block, keeping commented/active status).")
    print(f"New template keys to review ({len(stats['new_keys'])}): {names(stats['new_keys'])}")
    print(f"Orphan keys preserved at end ({len(stats['orphan_keys'])}): {names(stats['orphan_keys'])}")


if __name__ == "__main__":
    main()

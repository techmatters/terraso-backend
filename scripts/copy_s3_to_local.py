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
"""Seed the local silo (MinIO) by copying objects from a real AWS S3 environment.

You pick the source environment (dev / staging / prod); the destination is always
the local silo. Both are read from the block-structured .env:

  # ─── DEV (real AWS, …) ───      <- a source block (may stay commented)
  # ─── STAGING (real AWS, …) ───
  # ─── PROD (real AWS) ───
  # ─── LOCAL SILO … ───           <- the destination block (active)

For the chosen env it reads that block's bucket names (even while commented) and
maps each <NAME>_S3_BUCKET to the LOCAL block's same-named bucket. Buckets with no
local counterpart (e.g. DB_BACKUP/CDN_STATIC, which the local block doesn't set)
are skipped.

Credentials: the chosen block's AWS_ACCESS_KEY_ID/SECRET are used if present;
otherwise you're prompted (secret hidden). So the source blocks can stay fully
commented with no creds, and devs normally hold no AWS secrets in .env.

The transfer runs `mcli mirror` inside the pgsty/silo image — no host-side mc /
aws / boto3 needed. Creds are passed to the container as env vars (never on the
host command line) and fed to `mcli alias set` inside it; this script prints only
env names, bucket names, and mcli's object listing — never secret values, so
--dry-run output is safe to share. Region is auto-detected per bucket.

Requirements: docker, and a RUNNING local silo (`make run-local-soilid`).

Usage:
  python3 scripts/copy_s3_to_local.py               # prompts for env, then copies
  python3 scripts/copy_s3_to_local.py --from prod   # skip the env prompt
  python3 scripts/copy_s3_to_local.py --dry-run     # preview (transfers nothing)
"""

import argparse
import getpass
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

SECRETS_DIR = os.path.expanduser(
    os.environ.get("TERRASO_SECRETS_DIR", "~/secrets/terraso-backend")
)
ENV_PATH = os.path.join(SECRETS_DIR, ".env")
SILO_IMAGE = os.environ.get("SILO_IMAGE", "pgsty/silo:RELEASE.2026-10-26T00-00-00Z")

ENVS = ("dev", "staging", "prod")

ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# A block/section header: a comment whose text starts with divider chars (box
# drawing, '=' or '-') followed by a name, e.g. "# ─── STAGING (…) ───".
HEADER = re.compile(r"^#\s*[─═=-]{2,}\s*([A-Za-z]+)")


def section_name(line):
    m = HEADER.match(line)
    return m.group(1).upper() if m else None


def extract_block(lines, name):
    """Lines of the block whose header's first word == name (e.g. 'DEV'), from
    just after its header up to the next header. None if not found."""
    target = name.upper()
    start = None
    for i, line in enumerate(lines):
        sec = section_name(line)
        if sec == target and start is None:
            start = i + 1
        elif start is not None and sec is not None:
            return lines[start:i]
    return lines[start:] if start is not None else None


def block_assignments(block_lines):
    """{key: value} for assignments in a block, commented (`# KEY=v`) or not."""
    out = {}
    for line in block_lines:
        s = line.lstrip()
        if s.startswith("#"):
            s = s[1:].lstrip()  # treat a single leading '# ' as uncommented
        m = ASSIGN.match(s)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def mask(value):
    """Show an access-key id enough to compare without printing it in full."""
    return f"{value[:4]}…{value[-4:]}" if len(value) > 8 else "(set)"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # read the region header off the redirect, don't follow it


_REGION_OPENER = urllib.request.build_opener(_NoRedirect)


def bucket_region(bucket, default):
    """Best-effort region lookup. An unauthenticated HEAD to the global S3
    endpoint returns `x-amz-bucket-region` even on a 403/redirect, so we don't
    need creds or the right region to discover it. Falls back to `default`."""
    url = f"https://s3.amazonaws.com/{bucket}"
    try:
        resp = _REGION_OPENER.open(urllib.request.Request(url, method="HEAD"), timeout=10)
        return resp.headers.get("x-amz-bucket-region") or default
    except urllib.error.HTTPError as e:
        return e.headers.get("x-amz-bucket-region") or default
    except Exception:
        return default


def plan_copies(lines, env):
    """Build a copy plan from .env lines for the chosen source env. Returns a dict
    with source/dest config and the source->dest bucket pairs. Raises ValueError
    on any problem. Pure (no IO / no prompting) so it can be unit-tested; the
    source creds may come back empty (main() prompts for them)."""
    src_block = extract_block(lines, env)
    if src_block is None:
        raise ValueError(f"no '{env.upper()}' block in {ENV_PATH} "
                         f"(expected a '# ─── {env.upper()} …' header).")
    dst_block = extract_block(lines, "LOCAL")
    if dst_block is None:
        raise ValueError(f"no 'LOCAL SILO' block in {ENV_PATH}.")

    src = block_assignments(src_block)
    dst = block_assignments(dst_block)

    endpoint = dst.get("AWS_S3_ENDPOINT_URL", "")
    if not endpoint:
        raise ValueError("the LOCAL SILO block has no AWS_S3_ENDPOINT_URL "
                         "(is the local silo configured?).")

    # Bucket map: source bucket -> local dest bucket (deduped by pair).
    pairs = {}
    for key, s_bucket in src.items():
        if not key.endswith("_S3_BUCKET") or not s_bucket:
            continue
        d_bucket = dst.get(key, "")
        if not d_bucket:
            continue  # no local counterpart (e.g. DB_BACKUP/CDN_STATIC) -> skip
        pairs.setdefault(s_bucket, d_bucket)
    if not pairs:
        raise ValueError(f"no copyable buckets for {env}: fill the bucket names in "
                         f"the {env.upper()} block and ensure LOCAL has matching ones.")

    return {
        "src_key": src.get("AWS_ACCESS_KEY_ID", ""),
        "src_secret": src.get("AWS_SECRET_ACCESS_KEY", ""),
        "region": src.get("AWS_S3_REGION_NAME", "us-east-1"),
        "dst_key": dst.get("AWS_ACCESS_KEY_ID", ""),
        "dst_secret": dst.get("AWS_SECRET_ACCESS_KEY", ""),
        "endpoint": endpoint,
        "pairs": pairs,
    }


def prompt_env():
    while True:
        ans = input(f"Copy from which environment? [{'/'.join(ENVS)}]: ").strip().lower()
        if ans in ENVS:
            return ans
        print(f"  please enter one of: {', '.join(ENVS)} (Ctrl-C to cancel)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="from_env", choices=ENVS,
                    help="source environment (skip the interactive prompt)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would copy (mcli mirror --dry-run); transfer nothing")
    ap.add_argument("--debug", action="store_true",
                    help="pass --debug to mcli to print the S3 API calls")
    args = ap.parse_args()

    if not os.path.isfile(ENV_PATH):
        sys.exit(f"ERROR: no .env at {ENV_PATH}")
    with open(ENV_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()

    env = args.from_env or prompt_env()

    try:
        cfg = plan_copies(lines, env)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    src_key, src_secret, region = cfg["src_key"], cfg["src_secret"], cfg["region"]
    dst_key, dst_secret, endpoint = cfg["dst_key"], cfg["dst_secret"], cfg["endpoint"]
    pairs = cfg["pairs"]

    # Prompt for source creds only if the chosen block didn't carry them.
    if not src_key or not src_secret:
        print(f"\nNo stored AWS credentials for '{env}' — enter them (secret is hidden):")
        if not src_key:
            src_key = input("  AWS_ACCESS_KEY_ID: ").strip()
        if not src_secret:
            src_secret = getpass.getpass("  AWS_SECRET_ACCESS_KEY: ").strip()
        if not src_key or not src_secret:
            sys.exit("ERROR: an access key id and secret are both required.")
        print()

    # Creds are handed to the container as env vars (by NAME on the docker command
    # line, so they never appear in the host's argv/ps) and then fed to
    # `mcli alias set` inside the container (the MC_HOST URL form mis-handled these
    # AWS creds; alias-set against the plain regional endpoint works).
    env_base = dict(os.environ)

    banner = "DRY RUN — nothing will be transferred" if args.dry_run else "COPYING"
    print(f"[{banner}]")
    print(f"  source : {env} on real AWS S3 (region auto-detected per bucket; fallback {region})")
    print(f"  src key: {mask(src_key)}  (the AWS identity that must read the source buckets)")
    print(f"  dest   : {endpoint}  (local silo)")
    print(f"  dst key: {mask(dst_key)}  (the local silo root user, e.g. terraso-local)")
    print(f"  image  : {SILO_IMAGE}")
    print("  buckets:")
    for s_bucket, d_bucket in pairs.items():
        print(f"    s3://{s_bucket}  ->  {d_bucket}")
    print()

    rc = 0
    for s_bucket, d_bucket in pairs.items():
        bregion = bucket_region(s_bucket, region)
        env_vars = {
            **env_base,
            "SRC_KEY": src_key, "SRC_SECRET": src_secret,
            "DST_KEY": dst_key, "DST_SECRET": dst_secret,
        }
        debug = "--debug " if args.debug else ""
        dry = "--dry-run " if args.dry_run else ""
        # $VARS are expanded by the container's shell, so the secrets are only ever
        # in the container's env, not this script's output or the host argv.
        script = (
            f'mcli alias set src https://s3.{bregion}.amazonaws.com "$SRC_KEY" "$SRC_SECRET" >/dev/null && '
            f'mcli alias set dst {endpoint} "$DST_KEY" "$DST_SECRET" >/dev/null && '
            f'mcli {debug}mirror {dry}src/{s_bucket} dst/{d_bucket}'
        )
        cmd = ["docker", "run", "--rm",
               "-e", "SRC_KEY", "-e", "SRC_SECRET", "-e", "DST_KEY", "-e", "DST_SECRET",
               SILO_IMAGE, "sh", "-c", script]
        print(f"=== {s_bucket} ({bregion}) -> {d_bucket} ===")
        result = subprocess.run(cmd, env=env_vars)
        if result.returncode != 0:
            rc = result.returncode
            print(f"  (mcli exited {result.returncode})")
    sys.exit(rc)


if __name__ == "__main__":
    main()

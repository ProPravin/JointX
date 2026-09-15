#!/usr/bin/env bash
# Builds a distributable JointX release archive from git's own tracked file
# list -- NEVER by zipping the working directory (which has no concept of
# .gitignore and is exactly how .env, a real data/jointx.db, and a live
# SECRET_KEY ended up inside three separate distributed zip files before
# this script existed).
#
# Usage:
#   tools/make_release.sh [output.zip] [git-ref]
#   tools/make_release.sh                       # -> jointx-release-<sha>.zip from HEAD
#   tools/make_release.sh dist/jointx-v1.0.zip   # explicit output path
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REF="${2:-HEAD}"
SHA="$(git rev-parse --short "$REF")"
OUTPUT="${1:-dist/jointx-release-${SHA}.zip}"

mkdir -p "$(dirname "$OUTPUT")"
rm -f "$OUTPUT"

echo "Building release archive from git ref '$REF' (commit $SHA)..."
git archive --format=zip --output="$OUTPUT" "$REF"

echo "Verifying archive hygiene..."
FORBIDDEN_PATTERN='(^|/)\.env$|\.db$|\.db-wal$|\.db-shm$|\.log$|__pycache__/|(^|/)\.claude/|secret|token|credential'
VIOLATIONS="$(unzip -Z1 "$OUTPUT" | grep -Ei "$FORBIDDEN_PATTERN" || true)"

if [ -n "$VIOLATIONS" ]; then
    echo "REFUSING TO SHIP: the archive contains files matching forbidden patterns:"
    echo "$VIOLATIONS"
    rm -f "$OUTPUT"
    exit 1
fi

FILE_COUNT="$(unzip -Z1 "$OUTPUT" | wc -l)"
echo "OK: $OUTPUT built cleanly ($FILE_COUNT files, no secrets/DB/logs/cache)."

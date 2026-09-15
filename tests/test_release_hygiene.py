"""
Fails the build if a release archive built from git's own tracked files would
contain secrets, a database, logs, or cache directories (spec: P0 containment
-- three real distributed zip files were found to contain a live SECRET_KEY
and a real patient record before this test existed).

This builds the archive the same way tools/make_release.sh does (via
`git archive`, not by zipping the working directory) and inspects exactly
what git would ship -- it does not need the working directory to be clean,
only the git INDEX, since that's what actually goes out the door.
"""
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERN = re.compile(
    r"(^|/)\.env$|\.db$|\.db-wal$|\.db-shm$|\.log$|__pycache__/|(^|/)\.claude/|secret|token|credential",
    re.IGNORECASE,
)

# Names that legitimately contain the substrings above but are not secrets --
# e.g. this very test file, or notification_service.py's variable names.
# Matched by exact repo-relative path so a real secret file can't hide behind
# this allowlist.
ALLOWLIST = {
    "tests/test_release_hygiene.py",
    "backend/services/notification_service.py",  # contains the word "token" in comments/identifiers, not a secret
    ".env.example",  # placeholder-only template, safe and meant to ship
}


def _git_available() -> bool:
    return shutil.which("git") is not None


@pytest.mark.skipif(not _git_available(), reason="git not available in this environment")
def test_release_archive_contains_no_secrets_db_or_logs():
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / "release.zip"
        subprocess.run(
            ["git", "archive", "--format=zip", f"--output={archive_path}", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
        )

        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()

        violations = [n for n in names if FORBIDDEN_PATTERN.search(n) and n not in ALLOWLIST]

        assert not violations, (
            "Release archive (built from git's tracked files) contains forbidden "
            f"file(s): {violations}. If any of these are meant to ship, add the exact "
            "path to ALLOWLIST in this test after confirming it truly contains no "
            "secret/PHI; otherwise fix .gitignore and untrack it with `git rm --cached`."
        )


@pytest.mark.skipif(not _git_available(), reason="git not available in this environment")
def test_dot_env_and_database_are_not_tracked_by_git():
    """
    Belt-and-suspenders check independent of archive-building: .env and any
    *.db file must not be in git's index at all, so even a differently-built
    release mechanism can't accidentally pick them up.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    tracked = result.stdout.splitlines()

    bad = [f for f in tracked if f == ".env" or (f.endswith(".db") and f not in ALLOWLIST)]
    assert not bad, f"These files must never be tracked by git: {bad}"

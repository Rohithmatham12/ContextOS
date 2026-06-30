"""Git churn analysis — ranks files by recent commit frequency.

Files touched more often in recent git history are statistically more likely
to be relevant to a current task. Used as an additive scoring signal in the
context selector, not a replacement for keyword matching.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def build_churn_map(repo_root: Path, days: int = 30) -> dict[str, int]:
    """Return {rel_path: commit_count} for all files changed in the last `days` days.

    Returns empty dict if git is unavailable or repo has no history.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={days} days ago",
                "--name-only",
                "--format=",
                "--diff-filter=ACMR",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    if result.returncode != 0:
        return {}

    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1

    return counts


def churn_score(rel_path: str, churn_map: dict[str, int], weight: float = 0.1) -> float:
    """Score contribution from git churn for a single file.

    Caps at 5 commits to avoid over-weighting extremely active files
    (e.g. auto-generated lock files that change every dependency update).
    """
    count = churn_map.get(rel_path, 0)
    capped = min(count, 5)
    return capped * weight

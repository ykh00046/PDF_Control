"""CLAUDE.md drift guard.

Parses CLAUDE.md "Known Issues & Risks" → "Current Issues" subsection and
compares each issue title (slugified) against docs/_resolved.yml. Exits 1
and prints a diff if any currently-listed issue is already in the resolved
registry.

Usage:
    python scripts/check_claude_md_drift.py

Exit codes:
    0 — clean (no drift)
    1 — drift detected (doc lists items already resolved in code)
    2 — parse error (CLAUDE.md section missing or format broken)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Set

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
RESOLVED_YAML = ROOT / "docs" / "_resolved.yml"


def slugify(title: str) -> str:
    """Lowercase, alnum-only with '-' separators, trimmed."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def load_resolved_slugs() -> Set[str]:
    if not RESOLVED_YAML.exists():
        return set()
    data = yaml.safe_load(RESOLVED_YAML.read_text(encoding="utf-8")) or {}
    entries = data.get("resolved", [])
    return {entry["slug"] for entry in entries if "slug" in entry}


def parse_current_issues(claude_md_text: str) -> List[str]:
    """Extract issue titles from ## Known Issues & Risks → ### Current Issues.

    Issue format (numbered):
        1. **Title Here**: description...
    Returns list of raw titles (without bold markers).
    """
    known_match = re.search(
        r"^##\s+Known Issues.*?(?=^##\s|\Z)",
        claude_md_text,
        re.MULTILINE | re.DOTALL,
    )
    if not known_match:
        raise ValueError("CLAUDE.md missing '## Known Issues' section")

    section = known_match.group(0)
    current_match = re.search(
        r"###\s+Current Issues(.*?)(?=^###\s|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if not current_match:
        raise ValueError("CLAUDE.md missing '### Current Issues' subsection")

    body = current_match.group(1)
    return re.findall(r"^\s*\d+\.\s+\*\*([^*]+)\*\*", body, re.MULTILINE)


def detect_drift(claude_md_text: str, resolved_slugs: Set[str]) -> List[str]:
    titles = parse_current_issues(claude_md_text)
    drift = []
    for title in titles:
        if slugify(title) in resolved_slugs:
            drift.append(title)
    return drift


def main() -> int:
    if not CLAUDE_MD.exists():
        print(f"ERROR: {CLAUDE_MD} not found", file=sys.stderr)
        return 2

    try:
        resolved = load_resolved_slugs()
        drift = detect_drift(CLAUDE_MD.read_text(encoding="utf-8"), resolved)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if not drift:
        print(f"OK: CLAUDE.md is consistent with {len(resolved)} resolved entries")
        return 0

    print("DRIFT DETECTED — CLAUDE.md lists issues already marked resolved:")
    for title in drift:
        print(f"  - {title!r} (slug: {slugify(title)})")
    print()
    print(f"Fix: remove these from CLAUDE.md or remove their entry from {RESOLVED_YAML.relative_to(ROOT)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

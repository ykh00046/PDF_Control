"""Unit tests for scripts/check_claude_md_drift.py."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_claude_md_drift import (  # noqa: E402
    detect_drift,
    parse_current_issues,
    slugify,
)


def test_slugify_basic():
    assert slugify("Config default pollution") == "config-default-pollution"


def test_slugify_punctuation_and_case():
    assert slugify("Preview-Save Logic Divergence!") == "preview-save-logic-divergence"
    assert slugify("RemoveSection Memory Guard") == "removesection-memory-guard"


def test_slugify_collapses_repeats():
    assert slugify("Foo   ---   Bar") == "foo-bar"


def test_parse_current_issues_extracts_bold_titles():
    md = """# CLAUDE.md

## Known Issues & Risks

### Current Issues

1. **Long Text in Narrow Areas**: Text may fail to fit
   - Impact: Text may disappear

2. **Another Issue**: Something else
   - Impact: Stuff

### Risks

- some risk

## Other Section
"""
    assert parse_current_issues(md) == ["Long Text in Narrow Areas", "Another Issue"]


def test_parse_current_issues_raises_when_section_missing():
    with pytest.raises(ValueError, match="Known Issues"):
        parse_current_issues("# CLAUDE.md\n\nNo such section here.\n")


def test_detect_drift_flags_resolved_items():
    md = """## Known Issues & Risks

### Current Issues

1. **Already Fixed Thing**: described
2. **Still Broken**: described
"""
    drift = detect_drift(md, {"already-fixed-thing"})
    assert drift == ["Already Fixed Thing"]


def test_detect_drift_clean():
    md = """## Known Issues & Risks

### Current Issues

1. **Long Text in Narrow Areas**: described
"""
    drift = detect_drift(md, {"config-default-pollution"})
    assert drift == []


def test_real_claude_md_is_consistent():
    """The actual project file must not drift."""
    import yaml
    resolved = yaml.safe_load((ROOT / "docs" / "_resolved.yml").read_text(encoding="utf-8"))
    slugs = {e["slug"] for e in resolved["resolved"]}
    drift = detect_drift((ROOT / "CLAUDE.md").read_text(encoding="utf-8"), slugs)
    assert drift == [], f"Drift in real CLAUDE.md: {drift}"

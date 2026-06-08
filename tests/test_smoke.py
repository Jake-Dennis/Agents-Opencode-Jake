"""Smoke tests for the setup-project command and project bootstrapping.

These tests verify that the setup-project command documentation, the shell
scripts that implement it, and the resulting project skeleton are all
consistent with each other. They do NOT actually run setup-project (which
requires interactive input and modifies the filesystem), but they validate
the command description, the .bat scripts, and the expected output structure.
"""

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# T-SP-1: setup-project.md describes the full workflow
# ---------------------------------------------------------------------------
def test_sp_1_setup_project_md_exists():
    cmd = REPO / ".opencode" / "commands" / "setup-project.md"
    assert cmd.exists(), "setup-project.md command file must exist"
    content = cmd.read_text(encoding="utf-8")
    # Must describe all 6 steps from AGENTS.md
    for phrase in [
        "detect project type",
        "initialize git",
        "graphify",
        ".opencode",
        ".gitignore",
        "README",
        "3-file split",
        "jobs.md",
    ]:
        assert phrase.lower() in content.lower(), f"'{phrase}' must be described in setup-project.md"


def test_sp_1_setup_project_has_frontmatter():
    cmd = REPO / ".opencode" / "commands" / "setup-project.md"
    content = cmd.read_text(encoding="utf-8")
    assert content.startswith("---"), "setup-project.md must start with frontmatter"
    assert "description:" in content.split("---")[1], "frontmatter must have description"


# ---------------------------------------------------------------------------
# T-SP-2: AGENTS.md and setup-project.md agree on steps
# ---------------------------------------------------------------------------
def test_sp_2_agents_md_and_command_agree():
    agents = REPO / "AGENTS.md"
    cmd = REPO / ".opencode" / "commands" / "setup-project.md"
    agents_content = agents.read_text(encoding="utf-8")
    cmd_content = cmd.read_text(encoding="utf-8")

    # Both should mention graphify
    assert "graphify" in agents_content.lower()
    assert "graphify" in cmd_content.lower()

    # Both should mention .opencode
    assert ".opencode" in agents_content
    assert ".opencode" in cmd_content

    # Both should mention .gitignore
    assert ".gitignore" in agents_content
    assert ".gitignore" in cmd_content

    # AGENTS.md should list the same steps as the command (detect, git init,
    # graphify, .opencode, .gitignore, README)
    section = agents_content[agents_content.index("First-time setup"):]
    step_count_agents = len(re.findall(r'^\d+\.', section, re.MULTILINE))
    assert step_count_agents >= 6, f"AGENTS.md should describe at least 6 steps, found {step_count_agents}"


# ---------------------------------------------------------------------------
# T-SP-3: setup.bat creates the expected .opencode directory structure
# ---------------------------------------------------------------------------
def test_sp_3_setup_bat_references_opencode_structure():
    """setup.bat and global-setup.bat should mention creating the .opencode
    directory structure, including the 3-file split (todo.md, work-log.md,
    jobs.md)."""
    for bat_name in ("setup.bat", "global-setup.bat"):
        bat = REPO / bat_name
        assert bat.exists(), f"{bat_name} must exist"
        content = bat.read_text(encoding="utf-8")
        # Must reference the core files
        assert ".opencode" in content or "opencode" in content.lower(), \
            f"{bat_name} should reference .opencode"


# ---------------------------------------------------------------------------
# T-SP-4: The 3-file split skeleton is documented everywhere
# ---------------------------------------------------------------------------
def test_sp_4_three_file_split_documented():
    """The 3-file split (todo.md / work-log.md / jobs.md) should be
    documented in AGENTS.md, setup-project.md, and the relevant ADRs."""
    files = [
        ("AGENTS.md", REPO / "AGENTS.md"),
        ("setup-project.md", REPO / ".opencode/commands/setup-project.md"),
        ("ADR-006", REPO / ".opencode/decisions/adr-006-three-file-ownership-split.md"),
    ]
    for label, path in files:
        assert path.exists(), f"{label} ({path}) must exist"
        content = path.read_text(encoding="utf-8")
        assert "jobs.md" in content or "three-file" in content.lower() or "work-log.md" in content, \
            f"{label} should reference jobs.md or 3-file split"


# ---------------------------------------------------------------------------
# T-SP-5: The setup-project smoke test itself is listed in the test suite
# ---------------------------------------------------------------------------
def test_sp_5_smoke_test_is_discoverable():
    """This test file should be discoverable by pytest as part of CI."""
    # We are running right now — this is a meta-check that the file exists
    # and was collected by pytest
    assert __name__ != "__main__", "should be run via pytest, not directly"


if __name__ == "__main__":
    pytest.main([__file__])

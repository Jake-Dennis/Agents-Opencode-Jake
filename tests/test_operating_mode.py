"""Tests for plan-002 operating mode (any-project portability).

These tests verify the conductor can detect its environment and operate in
either dispatch mode (when a subagent tool is available) or single-agent
mode (when it isn't). The same agent prompts work in both modes; what
changes is how the conductor interprets its role.

If any of these tests fail, the operating-mode detection or workflow is
regressed, and the agent set will not work in projects without a `task`
tool. See `.opencode/plans/plan-002-any-project-portability.md` for the
specification and commit history for the implementation.

Stdlib only. Clear failure messages naming the offending file and
the expected vs. actual text.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Locator constants
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / ".opencode" / "agents"
CONDUCTOR_MD = AGENTS_DIR / "conductor.md"

# 12 subagent files (excludes conductor)
SUBAGENT_FILES = [
    "builder.md", "architect.md", "reviewer.md", "tester.md",
    "docs.md", "debugger.md", "refactor.md", "git.md",
    "explorer.md", "security.md", "perf.md", "planner.md",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(p: Path) -> str:
    assert p.exists(), f"Required file missing: {p}"
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T_OM_1: conductor.md documents both operating modes
# ---------------------------------------------------------------------------

def test_T_OM_1_conductor_documents_both_operating_modes():
    """conductor.md must document both dispatch mode and single-agent mode.

    The conductor's prompt is loaded into its context on every session
    start. If either mode is missing, the agent cannot self-classify.
    """
    content = _read(CONDUCTOR_MD).lower()
    assert "single-agent mode" in content, (
        "conductor.md missing 'single-agent mode' — the fallback for envs "
        "without a dispatch tool is not documented"
    )
    assert "dispatch mode" in content, (
        "conductor.md missing 'dispatch mode' — the default for envs with "
        "a dispatch tool is not documented"
    )


# ---------------------------------------------------------------------------
# T_OM_2: conductor.md has mode detection as the first workflow step
# ---------------------------------------------------------------------------

def test_T_OM_2_conductor_mode_detection_is_first_workflow_step():
    """The mode detection step must come before any other workflow step.

    The conductor must announce its mode before doing any work, so the
    user knows what to expect. Detection must be the FIRST step under
    "Session Start" or equivalent.
    """
    content = _read(CONDUCTOR_MD)
    # Find the workflow section
    workflow_match = re.search(
        r"## Workflow.*?(?=\n## |\Z)",
        content,
        re.DOTALL,
    )
    assert workflow_match, "Could not locate '## Workflow' section in conductor.md"
    workflow = workflow_match.group(0)

    # Mode detection must be near the top of the workflow
    detect_pos = workflow.find("Detect operating mode")
    assert detect_pos > 0, (
        "conductor.md '## Workflow' section missing 'Detect operating mode' step. "
        "Mode detection must be the first thing the conductor does."
    )
    # The detection step must come before the first numbered step (Step 0, 1, etc.)
    first_step_pos = min(
        (workflow.find(s) for s in ["Step 0", "### 0.", "### 1.", "Step 1"]
         if workflow.find(s) > 0),
        default=len(workflow),
    )
    assert detect_pos < first_step_pos, (
        "'Detect operating mode' must appear before the first workflow step. "
        f"Found at pos {detect_pos}, first step at pos {first_step_pos}."
    )


# ---------------------------------------------------------------------------
# T_OM_3: conductor.md documents the single-agent workflow
# ---------------------------------------------------------------------------

def test_T_OM_3_conductor_documents_single_agent_workflow():
    """Single-agent mode must describe the sequential phase workflow.

    The conductor plays all roles sequentially in single-agent mode:
    Conductor -> Builder -> Tester -> Reviewer -> Documenter. This
    must be documented, otherwise the agent has no playbook.
    """
    content = _read(CONDUCTOR_MD).lower()
    # Phase names (any case)
    for phase in ["conductor phase", "builder phase", "tester phase",
                  "reviewer phase", "documenter phase"]:
        assert phase in content, (
            f"conductor.md missing '{phase}' in single-agent mode workflow"
        )


# ---------------------------------------------------------------------------
# T_OM_4: conductor.md has honest self-review section
# ---------------------------------------------------------------------------

def test_T_OM_4_conductor_has_honest_self_review_section():
    """Self-review must be documented with its limits acknowledged.

    A conductor that claims self-review is as good as independent
    review is dishonest. The section must name the limits (same model,
    bias toward ship) and the mitigations (re-read the diff, run tests).
    """
    content = _read(CONDUCTOR_MD).lower()
    assert "honest self-review" in content or "self review" in content, (
        "conductor.md missing the honest self-review section"
    )
    # Limits acknowledged
    assert "limit" in content or "bias" in content, (
        "conductor.md self-review section missing the limits / bias acknowledgment"
    )
    # Mitigations named
    assert "re-read" in content or "reread" in content or "diff" in content, (
        "conductor.md self-review section missing the re-read-the-diff mitigation"
    )


# ---------------------------------------------------------------------------
# T_OM_5: conductor.md Boundaries are mode-aware
# ---------------------------------------------------------------------------

def test_T_OM_5_conductor_boundaries_are_mode_aware():
    """The Boundaries section must distinguish hard rules from mode-softened rules.

    In dispatch mode, the conductor doesn't implement directly, doesn't
    write tests, doesn't review its own dispatches. In single-agent
    mode, those rules are necessarily violated. The honesty rules still
    apply in both modes.
    """
    content = _read(CONDUCTOR_MD)
    boundaries_match = re.search(
        r"## Boundaries.*?(?=\n## |\Z)",
        content,
        re.DOTALL,
    )
    assert boundaries_match, "Could not locate '## Boundaries' section in conductor.md"
    boundaries = boundaries_match.group(0).lower()
    # Mode awareness is explicit
    assert "single-agent mode" in boundaries, (
        "conductor.md Boundaries section does not acknowledge single-agent mode"
    )
    # Hard rules still apply in both modes
    assert "opencode.json" in boundaries or "agent-roles" in boundaries, (
        "conductor.md Boundaries section missing the always-hard rules "
        "(opencode.json, AGENT-ROLES.md)"
    )


# ---------------------------------------------------------------------------
# T_OM_6: subagent files have the self-mode note
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", SUBAGENT_FILES)
def test_T_OM_6_subagent_has_self_mode_note(filename: str):
    """Each subagent .md file must have a 'self-mode note' for the conductor.

    In single-agent mode, the conductor reads each subagent .md as a
    checklist. The note must tell the conductor to execute the work
    itself rather than try to dispatch a subagent that doesn't exist.
    The note must appear near the top (line 1 or 2), after the
    consume-only framing.
    """
    text = _read(AGENTS_DIR / filename)
    first_lines = text.splitlines()[:5]
    head = "\n".join(first_lines).lower()
    assert "single-agent mode" in head, (
        f"{filename} missing the 'single-agent mode' self-mode note in the first 5 lines.\n"
        f"  First 5 lines: {first_lines!r}"
    )


# ---------------------------------------------------------------------------
# T_OM_7: conductor.md first response language is specified
# ---------------------------------------------------------------------------

def test_T_OM_7_conductor_first_response_states_mode():
    """The conductor's first response must announce its operating mode.

    The user needs to know which mode the agent is in to calibrate
    expectations. The phrase to use must be specified in the prompt.
    """
    content = _read(CONDUCTOR_MD)
    # Both announcement phrasings should be present
    assert "Dispatch tool detected" in content, (
        "conductor.md missing the 'Dispatch tool detected' first-response phrase"
    )
    assert "No dispatch tool detected" in content, (
        "conductor.md missing the 'No dispatch tool detected' first-response phrase"
    )

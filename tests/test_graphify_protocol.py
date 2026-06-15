"""Regression tests for plan-001 graphify protocol.

These tests verify the new architectural split is structurally in place:

- The conductor is the SOLE owner of graphify queries
  (conductor.md line 1 + Step 5 must reflect this)
- Subagents CONSUME the `Graph context:` block from the dispatch
  (12 subagent .md line 1 must use the consume-only framing)
- Subagents NEVER query the graph themselves
  (shared/graphify.md must have no self-query branch)
- AGENTS.md dispatch template uses the "sole mechanism" wording
  with explicit failure-mode language

If any of these tests fail, the graphify protocol has been reverted
and plan-001 needs to be re-applied. See commit eaad3e3 for the
reference implementation and `.opencode/plans/completed/plan-001-
conductor-owns-graphify.md` for the plan.

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
SHARED_DIR = AGENTS_DIR / "shared"
CONDUCTOR_MD = AGENTS_DIR / "conductor.md"
SHARED_GRAPHIFY_MD = SHARED_DIR / "graphify.md"
AGENTS_TOP_MD = REPO / "AGENTS.md"

# The 12 subagent files (excludes conductor, which has its own framing)
SUBAGENT_FILES = [
    "builder.md", "architect.md", "reviewer.md", "tester.md",
    "docs.md", "debugger.md", "refactor.md", "git.md",
    "explorer.md", "security.md", "perf.md", "planner.md",
]

# The new consume-only line 1 prefix used by all 12 subagents
NEW_LINE1_PREFIX = (
    "> Your dispatch from the conductor includes a `Graph context:` block."
)

# The old MANDATORY line 1 prefix that must be gone from all subagents
OLD_LINE1_PREFIX = (
    "> **MANDATORY:** Before starting any task, you MUST have knowledge graph context"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(p: Path) -> str:
    """Read a UTF-8 text file. Centralized so I/O errors are uniform."""
    assert p.exists(), f"Required file missing: {p}"
    return p.read_text(encoding="utf-8")


def _first_line(p: Path) -> str:
    """Return the first non-empty line of a markdown file (skips BOM if any)."""
    text = _read(p).lstrip("\ufeff")
    for line in text.splitlines():
        if line.strip():
            return line
    return ""


def _step5_section() -> str:
    """Extract the body of `### 5. DISPATCH ...` from conductor.md.

    The section runs from the `### 5. DISPATCH` heading to the next
    `### N.` heading (or end of file). Returned as a string for
    substring assertions.
    """
    content = _read(CONDUCTOR_MD)
    match = re.search(
        r"### 5\. DISPATCH.*?(?=\n### \d+\.|\Z)",
        content,
        re.DOTALL,
    )
    assert match, (
        "Could not locate `### 5. DISPATCH` section in conductor.md. "
        "The Step 5 heading must exist and be followed by a numbered step."
    )
    return match.group(0)


# ---------------------------------------------------------------------------
# T_GP_1: All 12 subagent .md files start with the new consume-only line 1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", SUBAGENT_FILES)
def test_T_GP_1_subagent_line1_uses_consume_only_framing(filename: str):
    """Each subagent's line 1 must be the new consume-only framing.

    Old: '> **MANDATORY:** Before starting any task, you MUST...'
    New: '> Your dispatch from the conductor includes a `Graph context:` block.'
    """
    line1 = _first_line(AGENTS_DIR / filename)
    assert line1.startswith(NEW_LINE1_PREFIX), (
        f"{filename} line 1 is not the new consume-only framing.\n"
        f"  Expected prefix: {NEW_LINE1_PREFIX!r}\n"
        f"  Got:             {line1!r}"
    )


# ---------------------------------------------------------------------------
# T_GP_2: No subagent retains the old MANDATORY line 1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", SUBAGENT_FILES)
def test_T_GP_2_no_subagent_has_old_mandatory_line1(filename: str):
    """The old MANDATORY line 1 must be fully removed from each subagent.

    This is a complementary check to T_GP_1: even if the new line 1
    is in place, a leftover MANDATORY line anywhere on line 1 would
    mean the rewrite was partial.
    """
    line1 = _first_line(AGENTS_DIR / filename)
    assert not line1.startswith(OLD_LINE1_PREFIX), (
        f"{filename} still starts with the OLD MANDATORY line 1:\n  {line1!r}"
    )


# ---------------------------------------------------------------------------
# T_GP_3: conductor.md line 1 is the new "owner" framing
# ---------------------------------------------------------------------------

def test_T_GP_3_conductor_line1_uses_owner_framing():
    """conductor.md line 1 frames the conductor as the SOLE query owner.

    The line must contain 'You own the knowledge graph' and reference
    both required pre-dispatch tools (graphify_graph_stats and
    graphify_query_graph). This is what the conductor sees on every
    session start, so the framing must be unambiguous.
    """
    line1 = _first_line(CONDUCTOR_MD)
    assert "You own the knowledge graph" in line1, (
        f"conductor.md line 1 missing 'You own the knowledge graph': {line1!r}"
    )
    assert "Before every dispatch" in line1, (
        "conductor.md line 1 missing the 'Before every dispatch' trigger"
    )
    assert "graphify_graph_stats" in line1, (
        "conductor.md line 1 missing graphify_graph_stats reference"
    )
    assert "graphify_query_graph" in line1, (
        "conductor.md line 1 missing graphify_query_graph reference"
    )


# ---------------------------------------------------------------------------
# T_GP_4: conductor.md Step 5 contains the pre-dispatch query protocol
# ---------------------------------------------------------------------------

def test_T_GP_4_conductor_step5_contains_query_protocol():
    """Step 5 (DISPATCH) must include the pre-dispatch graph query protocol.

    The protocol is the architectural lever of plan-001: the conductor
    runs graphify_graph_stats + graphify_query_graph BEFORE writing
    the dispatch, formats the results into a Graph context: block,
    and inlines it at the top.
    """
    step5 = _step5_section()
    # Required tools
    assert "graphify_graph_stats" in step5, (
        "Step 5 (DISPATCH) missing 'graphify_graph_stats' — conductor won't run it pre-dispatch"
    )
    assert "graphify_query_graph" in step5, (
        "Step 5 (DISPATCH) missing 'graphify_query_graph' — conductor won't run it pre-dispatch"
    )
    # Required structural actions
    assert re.search(r"\bFormat\b", step5), (
        "Step 5 missing the 'Format' action — results won't be turned into a block"
    )
    assert re.search(r"[Ii]nline", step5), (
        "Step 5 missing the 'Inline' action — block won't be inlined in dispatch"
    )
    # Required failure-mode language
    assert "failed dispatch" in step5.lower() or "broken dispatch" in step5.lower(), (
        "Step 5 missing failure-mode language — subagents won't know the contract"
    )


# ---------------------------------------------------------------------------
# T_GP_5: REMOVED
# ---------------------------------------------------------------------------
# This test previously checked shared/graphify.md for the absence of the
# old "query the graph yourself" decision-tree branch. That file was
# removed when graphify was uninstalled (the graphify MCP, Python
# package, plugin, and the .opencode/ shared file were all dropped).
# The graphify protocol content is now inlined into the 13 agent .md
# files; the other 5 graphify tests (T_GP_1 through T_GP_4 + T_GP_6)
# still cover the conductor and subagent inlined framing.


# ---------------------------------------------------------------------------
# T_GP_6: AGENTS.md dispatch template uses "sole mechanism" + failure-mode
# ---------------------------------------------------------------------------

def test_T_GP_6_agents_md_uses_sole_mechanism_framing():
    """AGENTS.md Dispatch Template must use 'sole mechanism' (not 'primary').

    'Primary' leaves an escape hatch (subagents could still query
    themselves). 'Sole' closes the door: the conductor is the only
    legitimate query point. Failure-mode language is required so
    the conductor knows a missing-block report is its own fault.
    """
    content = _read(AGENTS_TOP_MD)
    assert "sole mechanism" in content, (
        "AGENTS.md missing 'sole mechanism' — dispatch template has regressed "
        "to the old soft 'primary' framing"
    )
    # Failure-mode language — the conductor must understand that a
    # subagent reporting missing context is the conductor's fault.
    assert "missing Graph context" in content, (
        "AGENTS.md missing the 'missing Graph context' failure-mode reference"
    )
    # The Dispatch Template header must reflect the new framing
    assert re.search(
        r"### Dispatch Template \(MANDATORY[^)]*sole mechanism[^)]*\)",
        content,
    ), (
        "AGENTS.md '### Dispatch Template' heading missing the 'sole mechanism' "
        "qualifier in its title"
    )

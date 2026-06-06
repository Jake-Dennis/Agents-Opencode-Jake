"""Plan-013 verification tests (T-JB-1..T-JB-6).

Verifies the live progress tracking wiring:
  - jobs.md exists with format header + worked example
  - 11 write-capable agents (5 readonly + 6 impl) have the Live progress tracking section
  - 5 read-only agents have path-scoped `edit` permission
  - 5 read-only agents' prompts have the "ONLY" clarification
  - 6 impl agents' prompts do NOT have "ONLY" (they have full edit)
  - conductor (file-ref prompt) does NOT have the section
  - git agent does NOT have the section (git stays on bash)
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "opencode.json"
JOBS_MD = REPO / ".opencode" / "jobs.md"
CONDUCTOR_MD = REPO / ".opencode" / "agents" / "conductor.md"

# 5 read-only agents: had `edit: "deny"`, now get path-scoped object
READ_ONLY = ["planner", "architect", "reviewer", "explorer", "security"]
# 6 implementation agents: already have `edit: "allow"`, just get prompt addition
IMPL = ["builder", "tester", "docs", "debugger", "refactor", "perf"]
# 11 write-capable agents (5 readonly + 6 impl) that get the prompt section
WRITE_CAPABLE = READ_ONLY + IMPL

# Path-scoped `edit` object for the 5 read-only agents
EXPECTED_EDIT = {".opencode/jobs.md": "allow", "*": "deny"}

# 5 valid status values (from plan-013 design Section 3)
STATUS_VALUES = {"pending", "in_progress", "complete", "failed", "blocked"}


def _load_cfg():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _load_conductor_body():
    """Read .opencode/agents/conductor.md (resolved from {file:...} ref)."""
    return CONDUCTOR_MD.read_text(encoding="utf-8")


# ---------- T-JB-1: jobs.md exists with format + example ----------
def test_t_jb_1_jobs_md_format():
    """T-JB-1: jobs.md has format header, 3 numbered rules, and a worked example entry."""
    assert JOBS_MD.is_file(), f"missing: {JOBS_MD}"
    body = JOBS_MD.read_text(encoding="utf-8")
    # Format header
    assert "## Format (read this before writing)" in body, "missing format header"
    # 3 numbered rules (Start, As you work, Finish)
    for n, kw in enumerate(["Start", "As you work", "Finish"], 1):
        rule_pattern = f"{n}. **{kw}**"
        assert rule_pattern in body, f"missing rule {n}: {rule_pattern!r}"
    # Worked example entry: ## [plan-XXX] @agent - task
    entry_re = re.compile(r"^## \[[^\]]+\] @\w+ - .+$", re.MULTILINE)
    matches = entry_re.findall(body)
    assert len(matches) >= 1, "no worked example entry found (expected >=1)"
    # Status values appear in the format spec
    found_statuses = {s for s in STATUS_VALUES if re.search(rf"\b{s}\b", body)}
    assert found_statuses == STATUS_VALUES, (
        f"missing status values: {STATUS_VALUES - found_statuses}"
    )
    # 3 checkbox states: [ ], [~], [x]
    assert "[ ]" in body, "missing [ ] checkbox state"
    assert "[~]" in body, "missing [~] in-progress checkbox state"
    assert "[x]" in body, "missing [x] complete checkbox state"


# ---------- T-JB-2: 11 write-capable agents have the section ----------
@pytest.mark.parametrize("agent_name", WRITE_CAPABLE)
def test_t_jb_2_write_capable_have_section(agent_name):
    """T-JB-2: all 11 write-capable agents have the 'Live progress tracking' section."""
    cfg = _load_cfg()
    prompt = cfg["agent"][agent_name]["prompt"]
    assert isinstance(prompt, str), f"{agent_name}.prompt is not a string"
    assert "Live progress tracking" in prompt, (
        f"{agent_name}.prompt missing 'Live progress tracking' section"
    )
    # All 11 must reference jobs.md
    assert "`.opencode/jobs.md`" in prompt, (
        f"{agent_name}.prompt missing `.opencode/jobs.md` reference"
    )


# ---------- T-JB-3: 5 read-only agents have path-scoped edit permission ----------
@pytest.mark.parametrize("agent_name", READ_ONLY)
def test_t_jb_3_readonly_path_scoped_edit(agent_name):
    """T-JB-3: the 5 read-only agents have `edit: { '.opencode/jobs.md': 'allow', '*': 'deny' }`."""
    cfg = _load_cfg()
    perm = cfg["agent"][agent_name]["permission"]
    assert "edit" in perm, f"{agent_name}.permission missing `edit` block"
    assert perm["edit"] == EXPECTED_EDIT, (
        f"{agent_name}.permission.edit = {perm['edit']!r}, expected {EXPECTED_EDIT!r}"
    )


# ---------- T-JB-4: 5 read-only agents' prompts have the "ONLY" clarification ----------
@pytest.mark.parametrize("agent_name", READ_ONLY)
def test_t_jb_4_readonly_prompt_has_only(agent_name):
    """T-JB-4: the 5 read-only agents' prompts explicitly say 'jobs.md ONLY'."""
    cfg = _load_cfg()
    prompt = cfg["agent"][agent_name]["prompt"]
    assert "ONLY" in prompt, (
        f"{agent_name}.prompt missing 'ONLY' clarification (should be read-only)"
    )
    # And the context: edit access to .opencode/jobs.md ONLY
    assert re.search(r"edit access to `\.opencode/jobs\.md` ONLY", prompt), (
        f"{agent_name}.prompt missing the 'edit access to .opencode/jobs.md ONLY' phrasing"
    )


# ---------- T-JB-5: 6 impl agents' prompts do NOT have "ONLY" ----------
@pytest.mark.parametrize("agent_name", IMPL)
def test_t_jb_5_impl_prompt_no_only(agent_name):
    """T-JB-5: the 6 impl agents have full edit access; their prompts must not say 'ONLY'."""
    cfg = _load_cfg()
    prompt = cfg["agent"][agent_name]["prompt"]
    # The "ONLY" phrase is reserved for read-only agents.
    # A bare "ONLY" elsewhere in the prompt would be a bug.
    assert "edit access to `\\.opencode/jobs\\.md` ONLY" not in prompt, (
        f"{agent_name}.prompt should NOT have the 'ONLY' clarification (it has full edit)"
    )
    # The section header must still be present
    assert "Live progress tracking" in prompt


# ---------- T-JB-6: conductor and git agents do NOT have the section ----------
def test_t_jb_6_conductor_and_git_excluded():
    """T-JB-6: conductor and git agents must NOT have the Live progress tracking section.

    - Conductor: writes to todo.md and work-log.md, not jobs.md (per plan-013 design Section 1).
    - Git: stays on bash-only permissions; no need for jobs.md edits.
    """
    cfg = _load_cfg()

    # Conductor: prompt is a {file:...} ref, so read the resolved file body
    conductor_ref = cfg["agent"]["conductor"]["prompt"]
    assert isinstance(conductor_ref, str) and conductor_ref.startswith("{file:"), (
        f"conductor.prompt should be a {{file:...}} ref, got {conductor_ref!r}"
    )
    conductor_body = _load_conductor_body()
    assert "Live progress tracking" not in conductor_body, (
        "conductor.md must NOT have the 'Live progress tracking' section "
        "(conductor writes to todo.md and work-log.md, not jobs.md)"
    )

    # Git agent: inline prompt, must not have the section
    git_prompt = cfg["agent"]["git"]["prompt"]
    assert isinstance(git_prompt, str), "git.prompt should be an inline string"
    assert "Live progress tracking" not in git_prompt, (
        "git.prompt must NOT have the 'Live progress tracking' section "
        "(git stays on bash-only permissions)"
    )

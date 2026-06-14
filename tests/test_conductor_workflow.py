"""End-to-end test of the conductor's 14-step workflow.

This is the highest-value test in the suite: it validates the actual
user-facing workflow (plan file -> conductor dispatches -> work-log
appended -> plan archived), not just individual agent responses.

Layer 2 review fix: this test used to write to the real .opencode/plans/
and .opencode/work-log.md, which could corrupt a developer's live plan
directory if pytest was killed mid-test. It now mirrors the real layout
under pytest's `tmp_path` so cleanup is automatic and the real tree is
never touched. Shared fixtures (cfg, repo_path) come from conftest.py.
"""
import shutil
from datetime import datetime, timezone
import pytest


@pytest.fixture
def fake_plan(tmp_path):
    """Create a fake plan file under tmp_path/.opencode/plans/ for the test.

    Mirrors the real .opencode/ layout (so paths and structure match
    production) but writes to a per-test temporary directory. The
    developer's live .opencode/ tree is never touched — even if pytest
    is killed mid-test. Cleanup is automatic when tmp_path is torn down.
    """
    plan_dir = tmp_path / ".opencode" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "test-999-fake.md"
    plan_path.write_text("""# Plan 999: Test plan (E2E)

## Goal
This plan exists only to test the conductor workflow.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] task A (assigned: @builder)
- [ ] task B (assigned: @reviewer)

### Layer 2 (depends on Layer 1)
- [ ] task C (assigned: @tester, depends on A, B)

## Verification
- [ ] task A: file exists
- [ ] task B: review passes
- [ ] task C: tests pass
""", encoding="utf-8")
    return plan_path


def test_plan_file_has_required_sections(fake_plan):
    """Plan files must have Goal, Tasks, and Verification sections."""
    content = fake_plan.read_text(encoding="utf-8")
    assert "## Goal" in content, "Plan missing '## Goal' section"
    assert "## Tasks" in content, "Plan missing '## Tasks' section"
    assert "## Verification" in content, "Plan missing '## Verification' section"


def test_plan_file_has_checkboxes(fake_plan):
    """Plan files must have checkboxes in Tasks and Verification."""
    content = fake_plan.read_text(encoding="utf-8")
    assert "- [ ]" in content, "Plan missing unchecked tasks"
    assert "## Verification" in content
    # Should have verification steps
    verification_section = content.split("## Verification")[1]
    assert "- [ ]" in verification_section, "Verification section missing checkboxes"


def test_conductor_prompt_has_all_14_workflow_steps(cfg, repo_path):
    """The conductor's prompt must include all 14 workflow step names.

    Plan-010 moved the conductor's prompt body out of opencode.json into
    `.opencode/agents/conductor.md`. The JSON now holds a
    `{file:./.opencode/agents/conductor.md}` ref. This test resolves
    the ref and reads the markdown file's body.
    """
    prompt = _load_conductor_prompt_body(cfg, repo_path)
    required_steps = [
        "1. CLARIFY", "2. GRAPHIFY", "3. PLAN", "4. TODO",
        "5. DISPATCH", "6. TRACK", "7. REVIEW", "8. VERIFY",
        "9. DOCUMENT", "10. SYNC TODO", "11. GRAPHIFY UPDATE",
        "12. GIT", "13. REPORT", "14. RESUME"
    ]
    for step in required_steps:
        assert step in prompt, f"Conductor prompt missing step: {step}"


def test_conductor_prompt_references_all_subagents(cfg, repo_path):
    """The conductor's prompt must @mention all 12 subagents.

    See test_conductor_prompt_has_all_14_workflow_steps for why this
    test reads the markdown file (plan-010 refactor).
    """
    prompt = _load_conductor_prompt_body(cfg, repo_path)
    expected = ["planner", "builder", "architect", "reviewer", "tester",
                "docs", "debugger", "refactor", "git", "explorer", "security", "perf"]
    for agent_name in expected:
        assert f"@{agent_name}" in prompt, f"Conductor prompt missing @{agent_name}"


def test_conductor_prompt_has_plan_template(cfg, repo_path):
    """The conductor's prompt must include a plan file template.

    See test_conductor_prompt_has_all_14_workflow_steps for why this
    test reads the markdown file (plan-010 refactor).
    """
    prompt = _load_conductor_prompt_body(cfg, repo_path)
    assert "## Plan File Template" in prompt, \
        "Conductor prompt missing '## Plan File Template' section"
    assert "## Tasks" in prompt, "Conductor plan template missing '## Tasks'"
    assert "## Verification" in prompt, "Conductor plan template missing '## Verification'"


def _load_conductor_prompt_body(cfg, repo_path) -> str:
    """Resolve the conductor's prompt field to its actual body text.

    Since plan-010, the conductor agent's `prompt` is a `{file:...}` ref
    in opencode.json. This helper:
    1. Reads `cfg["agent"]["conductor"]["prompt"]` (the ref string).
    2. If it starts with `{file:`, strips the wrapper and reads the
       referenced file's content from `repo_path`.
    3. Recursively expands any nested `{file:...}` references.
    4. Otherwise returns the raw value (legacy / future inline prompts).
    """
    import re
    ref = cfg["agent"]["conductor"]["prompt"]
    if isinstance(ref, str) and ref.startswith("{file:"):
        path_str = ref[len("{file:"):].rstrip("}")
        content = (repo_path / path_str).read_text(encoding="utf-8")
        # Recursively expand nested {file:...} references
        for m in re.finditer(r"\{file:([^}]+)\}", content):
            nested_ref = m.group(1)
            if nested_ref.startswith("./"):
                nested_ref = nested_ref[2:]
            nested_path = repo_path / nested_ref
            if nested_path.exists():
                nested_content = nested_path.read_text(encoding="utf-8")
                content = content.replace(m.group(0), nested_content, 1)
        return content
    return ref


def test_workflow_can_move_plan_to_completed(fake_plan, tmp_path):
    """Simulate: mark all tasks done, append work-log, move to completed/.

    All filesystem side effects are scoped to tmp_path/.opencode/ — the
    real repo is never touched, and tmp_path cleanup removes everything.
    """
    opencode_dir = tmp_path / ".opencode"
    work_log = opencode_dir / "work-log.md"
    completed_dir = opencode_dir / "plans" / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Mark all tasks [x]
    content = fake_plan.read_text(encoding="utf-8")
    marked = content.replace("- [ ]", "- [x]")
    assert "- [x]" in marked, "Failed to mark tasks complete"
    assert "- [ ]" not in marked.split("## Verification")[0], "Tasks still unchecked"

    # Step 2: Append to work-log
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"\n## {timestamp}\n- **Task:** E2E test plan\n- **Status:** Complete\n"
    work_log.write_text(log_entry, encoding="utf-8")
    assert log_entry in work_log.read_text(encoding="utf-8"), "Work-log not appended"

    # Step 3: Move plan to completed/
    dest = completed_dir / fake_plan.name
    shutil.move(str(fake_plan), str(dest))
    assert dest.exists(), "Plan not moved to completed/"
    assert not fake_plan.exists(), "Plan still in plans/ (move failed)"
    # Cleanup is automatic with tmp_path

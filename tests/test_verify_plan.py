"""Test scripts/verify-plan.py.

These tests validate that the verify-plan.py script correctly:
1. Extracts verification commands from a plan file
2. Runs each command
3. Returns exit 0 if all pass, 1 if any fail
4. Handles common patterns (file existence, command run, schema validation)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "verify-plan.py"


def write_temp_plan(content, tmpdir):
    """Write content to a temp plan file inside the given directory."""
    plan = tmpdir / "plan-temp.md"
    plan.write_text(content, encoding="utf-8")
    return plan


def run_verify(plan_path):
    """Run verify-plan.py on a plan file. Returns CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(plan_path)],
        capture_output=True, text=True, timeout=60,
        cwd=REPO,
    )


@pytest.fixture
def repo_tmp(tmp_path):
    """tmp_path that's INSIDE the repo so find_repo_root works.

    We create a hidden temp dir under the repo, then clean up after.
    """
    import shutil
    repo_tmp = REPO / ".opencode" / ".tmp-test"
    repo_tmp.mkdir(parents=True, exist_ok=True)
    try:
        yield repo_tmp
    finally:
        shutil.rmtree(repo_tmp, ignore_errors=True)


def test_script_exists():
    """verify-plan.py must exist and be runnable."""
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert SCRIPT.read_text(encoding="utf-8").startswith('"""'), "missing module docstring"


def test_all_pass(repo_tmp):
    """A plan with all-passing verifications should return exit 0."""
    plan = write_temp_plan("""# Plan: all-pass

## Verification
- [x] #1 - LICENSE exists: `LICENSE`
- [x] #2 - test pass: `python -c "assert 1 + 1 == 2"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 0, f"expected exit 0, got {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
    assert "ALL CHECKS PASSED" in r.stdout


def test_one_fails(repo_tmp):
    """A plan with one failing check should return exit 1."""
    plan = write_temp_plan("""# Plan: one-fail

## Verification
- [x] #1 - test passes: `python -c "assert 1 + 1 == 2"`
- [x] #2 - test fails: `python -c "assert 1 + 1 == 3"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, f"expected exit 1, got {r.returncode}"
    assert "1 CHECK(S) FAILED" in r.stdout


def test_no_verification_section(repo_tmp):
    """A plan without ## Verification section should error out."""
    plan = write_temp_plan("# Plan: empty\n\n## Tasks\n- [ ] nothing\n", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 2, f"expected exit 2 (no tasks), got {r.returncode}"


def test_bold_task_ids(repo_tmp):
    """Should handle **#N** bold formatting in task IDs."""
    plan = write_temp_plan("""# Plan: bold

## Verification
- [x] **#1** - description: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 0, f"bold format not handled: {r.stdout}"


def test_real_plan_001():
    """The completed Plan 001 should pass all 15 verifications."""
    plan = REPO / ".opencode" / "plans" / "completed" / "plan-001-improve-project.md"
    if not plan.exists():
        pytest.skip("Plan 001 not yet archived")
    r = run_verify(plan)
    assert r.returncode == 0, (
        f"Plan 001 should pass all verifications, but failed:\n"
        f"exit={r.returncode}\nstdout={r.stdout[-2000:]}\nstderr={r.stderr[-500:]}"
    )


def test_checkbox_states(repo_tmp):
    """Should accept both [x] (done) and [ ] (pending) checkboxes."""
    plan = write_temp_plan("""# Plan: mixed

## Verification
- [x] #1 - done: `python -c "assert True"`
- [ ] #2 - pending: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 0, f"mixed checkboxes not handled: {r.stdout}"


def test_file_existence_check(repo_tmp):
    """Should correctly check file existence (treats bare path as file check)."""
    plan = write_temp_plan("""# Plan: file

## Verification
- [x] #1 - LICENSE exists: `LICENSE`
- [x] #2 - README exists: `README.md`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 0, f"file check failed: {r.stdout}\nstderr: {r.stderr}"


def test_missing_file_check(repo_tmp):
    """Should fail when checking a non-existent file."""
    plan = write_temp_plan("""# Plan: missing

## Verification
- [x] #1 - missing file: `DOES_NOT_EXIST.md`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, f"missing file check should fail, got {r.returncode}"

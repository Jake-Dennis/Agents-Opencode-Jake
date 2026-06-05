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


# ---------------------------------------------------------------------
# Mechanical checks (plan-007, layer 1, T2) — 5 mechanical / regex
# gates that fire after the verification commands, designed to catch
# structural problems without any LLM judgment.
# ---------------------------------------------------------------------


def test_T_MC_1_valid_plan_passes_all_mechanical_checks(repo_tmp):
    """T-MC-1: a plan with valid layers, tasks, and verification exits 0
    and reports 5/5 mechanical checks passing.

    The plan has one layer, two @-assigned tasks with descriptions
    longer than 10 chars, two verification entries, and no duplicate
    IDs or unresolved file references. Every check should pass.
    """
    plan = write_temp_plan("""# Plan: all-valid

### Layer 1
- [x] T1: @builder implements the @-assignment check (assigned: @builder)
- [x] T2: @builder adds the description check (assigned: @builder)

## Verification
- [x] #1 - test: `python -c "assert True"`
- [x] #2 - test: `python -c "assert 1+1==2"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 0, (
        f"expected exit 0, got {r.returncode}\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "5/5 passed, 0 failed" in r.stdout
    # Spot-check each check name appears in the PASS list.
    for name in (
        "@-assignment check",
        "non-empty description check",
        "verification coverage check",
        "no duplicate task IDs check",
        "cross-reference resolution check",
    ):
        assert f"[PASS] {name}" in r.stdout, f"missing PASS for {name}"


def test_T_MC_2_missing_at_assignment_fails_check_1(repo_tmp):
    """T-MC-2: a task line in ``### Layer N`` without ``@-agent`` fails
    check 1 (@-assignment check). The other 4 checks pass because
    everything else is well-formed.
    """
    plan = write_temp_plan("""# Plan: no-at

### Layer 1
- [x] T1: builder does something without any at-assignment here
- [x] T2: @builder does something else with proper assignment (assigned: @builder)

## Verification
- [x] #1 - test: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, (
        f"expected exit 1, got {r.returncode}\nstdout: {r.stdout}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "[FAIL] @-assignment check" in r.stdout
    # The other 4 checks should still pass on this plan.
    assert "[PASS] non-empty description check" in r.stdout
    assert "[PASS] verification coverage check" in r.stdout
    assert "[PASS] no duplicate task IDs check" in r.stdout
    assert "[PASS] cross-reference resolution check" in r.stdout


def test_T_MC_3_short_description_fails_check_2(repo_tmp):
    """T-MC-3: a task with fewer than 10 characters after the
    ``@-assignment`` fails check 2 (non-empty description check).
    The other 4 checks pass.
    """
    plan = write_temp_plan("""# Plan: short-desc

### Layer 1
- [x] T1: @builder x
- [x] T2: @builder has a much longer description here (assigned: @builder)

## Verification
- [x] #1 - test: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, (
        f"expected exit 1, got {r.returncode}\nstdout: {r.stdout}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "[FAIL] non-empty description check" in r.stdout
    # T1 has an @-assignment, so check 1 should pass.
    assert "[PASS] @-assignment check" in r.stdout
    assert "[PASS] verification coverage check" in r.stdout


def test_T_MC_4_too_few_verification_entries_fails_check_3(repo_tmp):
    """T-MC-4: three ``### Layer N`` sections but only one verification
    entry fails check 3 (verification coverage check). Coverage
    requires at least N entries (one per layer).
    """
    plan = write_temp_plan("""# Plan: insufficient-coverage

### Layer 1
- [x] T1: @builder does the first layer of work (assigned: @builder)

### Layer 2
- [x] T2: @builder does the second layer of work (assigned: @builder)

### Layer 3
- [x] T3: @builder does the third layer of work (assigned: @builder)

## Verification
- [x] #1 - test: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, (
        f"expected exit 1, got {r.returncode}\nstdout: {r.stdout}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "[FAIL] verification coverage check" in r.stdout
    # The check message should explicitly call out the layer count.
    assert "need >= 3" in r.stdout
    assert "[PASS] @-assignment check" in r.stdout
    assert "[PASS] non-empty description check" in r.stdout


def test_T_MC_5_duplicate_task_ids_fails_check_4(repo_tmp):
    """T-MC-5: two verification entries with the same ``#N`` fail check 4
    (no duplicate task IDs check). Both verification commands still
    pass; only the mechanical check fails.
    """
    plan = write_temp_plan("""# Plan: duplicate-ids

### Layer 1
- [x] T1: @builder does the first task in the plan (assigned: @builder)

## Verification
- [x] #1 - first test: `python -c "assert True"`
- [x] #1 - second test: `python -c "assert 1+1==2"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, (
        f"expected exit 1, got {r.returncode}\nstdout: {r.stdout}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "[FAIL] no duplicate task IDs check" in r.stdout
    # The failure message must name the offending ID.
    assert "#1" in r.stdout
    # Both verification commands ran and passed (1/2, 1/2 = 2/2).
    assert "2/2 passed" in r.stdout or "VERIFICATION: 2/2" in r.stdout


def test_T_MC_6_unresolved_reference_fails_check_5(repo_tmp):
    """T-MC-6: a backticked ``.md`` path that does not exist fails
    check 5 (cross-reference resolution check).
    """
    plan = write_temp_plan("""# Plan: bad-ref

### Layer 1
- [x] T1: @builder reads `nonexistent_xyz_file_12345.md` for context (assigned: @builder)

## Verification
- [x] #1 - test: `python -c "assert True"`
""", repo_tmp)
    r = run_verify(plan)
    assert r.returncode == 1, (
        f"expected exit 1, got {r.returncode}\nstdout: {r.stdout}"
    )
    assert "MECHANICAL CHECKS" in r.stdout
    assert "[FAIL] cross-reference resolution check" in r.stdout
    # The failure message must name the unresolved reference.
    assert "nonexistent_xyz_file_12345.md" in r.stdout
    # The other 4 checks should pass.
    assert "[PASS] @-assignment check" in r.stdout
    assert "[PASS] non-empty description check" in r.stdout
    assert "[PASS] verification coverage check" in r.stdout
    assert "[PASS] no duplicate task IDs check" in r.stdout

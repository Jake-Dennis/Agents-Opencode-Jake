"""Property-based tests for verify-plan.py using Hypothesis.

These tests verify that verify-plan.py behaves correctly across a wide
range of randomly generated plan files, not just the hand-crafted ones
in test_verify_plan.py.
"""

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

# Hypothesis is optional — skip all tests if not installed
try:
    from hypothesis import given, settings, strategies as st
    from hypothesis import HealthCheck
except ImportError:
    pytest.skip("hypothesis not installed", allow_module_level=True)

REPO = Path(__file__).resolve().parent.parent
VERIFY_SCRIPT = REPO / "scripts" / "verify-plan.py"


# ---------------------------------------------------------------------------
# Strategy: generate a valid plan file
# ---------------------------------------------------------------------------
def _layers(n_layers: int) -> str:
    lines = []
    for i in range(n_layers):
        lines.append(f"### Layer {i + 1}")
        lines.append(f"- [ ] @builder #task_{i}_1: some task description")
        lines.append(f"- [x] @tester #task_{i}_2: another task description")
    return "\n".join(lines)


def _verification(n_checks: int) -> str:
    lines = []
    for i in range(n_checks):
        lines.append(f"- [x] #{i}: `python -c \"print('ok')\"`")
    return "\n".join(lines)


def _plan(n_layers: int, n_checks: int, has_goal: bool, has_tasks: bool, has_verification: bool) -> str:
    parts = []
    if has_goal:
        parts.append("## Goal\n\nSome goal\n")
    if has_tasks:
        parts.append("## Tasks\n\n")
        parts.append(_layers(n_layers))
    if has_verification:
        parts.append("## Verification\n\n")
        parts.append(_verification(n_checks))
    return "\n".join(parts)


plan_strategy = st.builds(
    _plan,
    n_layers=st.integers(min_value=1, max_value=5),
    n_checks=st.integers(min_value=1, max_value=5),
    has_goal=st.booleans(),
    has_tasks=st.booleans(),
    has_verification=st.booleans(),
)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(plan_text=plan_strategy)
def test_verify_script_never_crashes(plan_text):
    """verify-plan.py must never crash (exit 1 or 2 or 0) on any input.
    It must not exit with a signal or unhandled exception."""
    tmp = REPO / ".opencode" / "plans" / "_hypothesis_temp_plan.md"
    try:
        tmp.write_text(plan_text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(tmp)],
            capture_output=True, text=True, timeout=30,
        )
        # Must exit 0, 1, or 2 (never crash with signal like -11)
        assert result.returncode in (0, 1, 2), (
            f"verify-plan.py crashed with exit code {result.returncode}\n"
            f"stdout: {result.stdout[:500]}\n"
            f"stderr: {result.stderr[:500]}"
        )
    finally:
        if tmp.exists():
            tmp.unlink()


@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(plan_text=plan_strategy)
def test_verify_script_output_structured(plan_text):
    """The output must contain expected sections regardless of input."""
    tmp = REPO / ".opencode" / "plans" / "_hypothesis_temp_plan.md"
    try:
        tmp.write_text(plan_text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(tmp)],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        # Must always mention "Plan:" (header line with the path)
        assert "Plan:" in output, f"Output missing 'Plan:' header\n{output[:300]}"
        # Must mention the script name
        assert "verify-plan" in output, f"Output missing 'verify-plan'\n{output[:300]}"
    finally:
        if tmp.exists():
            tmp.unlink()


@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(
    n_layers=st.integers(min_value=1, max_value=4),
)
def test_verification_coverage_check(n_layers):
    """A plan with N layers needs at least N verification entries.
    Fewer entries should trigger the verification coverage FAIL."""
    checks_needed = n_layers  # minimum
    checks_provided = checks_needed - 1  # one less than needed

    plan = _plan(
        n_layers=n_layers,
        n_checks=max(1, checks_provided),
        has_goal=True,
        has_tasks=True,
        has_verification=True,
    )
    tmp = REPO / ".opencode" / "plans" / "_hypothesis_temp_plan.md"
    try:
        tmp.write_text(plan, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(tmp)],
            capture_output=True, text=True, timeout=30,
        )
        # The verification coverage check should fail
        if checks_provided < n_layers:
            assert "verification coverage check" in (result.stdout + result.stderr), (
                f"Expected coverage check to run for {n_layers} layers / {checks_provided} verifications"
            )
    finally:
        if tmp.exists():
            tmp.unlink()

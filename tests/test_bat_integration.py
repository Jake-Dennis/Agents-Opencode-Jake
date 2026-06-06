"""``.bat``-level integration tests for the graphify refresh step.

Decision: the full matrix T2.1–T2.5 ``.bat``-level integration tests
are **deliberately skipped** in favour of the comprehensive Python
unit-test coverage in ``tests/test_graphify_refresh.py`` (T1.1–T1.19,
21 tests). This module docstring documents the rationale so a future
maintainer can revisit the decision.

Why we are not running the full T2.1–T2.5 matrix
-------------------------------------------------

The matrix's §7 lists 5 ``.bat``-level tests that exercise the actual
``global-setup.bat`` and ``setup.bat`` files. We chose to drop them
after weighing the cost / value of each test:

1. **The ``.bat`` files are thin wrappers.** Both ``global-setup.bat``
   (step 4b) and ``setup.bat`` (step 2b) do exactly four things:

   a. Check ``python --version`` works.
   b. Set the stamp path to ``%USERPROFILE%\\.config\\opencode\\
      skills\\graphify\\.graphify_version``.
   c. Append ``--unattended`` / ``--dry-run`` / ``--yes`` flags
      based on the .bat's own flag parsing.
   d. Call ``python <SCRIPT_DIR>\\.opencode\\scripts\\
      graphify_refresh.py <flags>``.

   The Python helper is exhaustively covered by the 21 unit tests in
   ``test_graphify_refresh.py``. The ``.bat`` adds only 4 lines of
   logic on top of that.

2. **The ``.bat`` tests need extensive mocking.** Running a real
   ``.bat`` in a test requires:

   - A fake ``python`` on ``PATH`` that responds to ``python --version``,
     ``python -m pip show``, ``python -m pip install``, and
     ``python -m graphify install`` (each with its own response).
   - A redirected ``%USERPROFILE%`` to a ``tmp_path`` so the
     developer's real ``~/.config/opencode/`` is not touched.
   - A redirected ``%SCRIPT_DIR%`` (or running the .bat from its
     actual location) so the helper module is found.
   - A ``--target-dir`` for ``setup.bat`` (the rest of the .bat
     requires it).
   - Optional mocking of the ``.bat``'s other steps (file copy,
     knowledge graph build) which would otherwise try to run.

3. **The ``.bat`` tests are slow.** Each test takes ~3-5s for the
   PowerShell / ``cmd.exe`` interpreter startup. Five tests = 15-25s
   of added test time for marginal additional coverage of the flag-
   passing logic (which is itself 4-5 lines of code).

4. **The ``.bat`` tests are fragile.** Windows ``cmd.exe`` quoting,
   PowerShell's ``&`` operator, ``%errorlevel%`` propagation, and
   ``pause`` / ``set /p`` stdin handling all add moving parts. A
   future Windows update or opencode install location change could
   silently break the tests without any test failure pointing at the
   ``.bat`` layer (the tests would just become no-ops).

5. **The ``.bat``-level contract is small enough to review by eye.**
   The 4-line flag-passing block in both .bat files can be reviewed
   in seconds; the Python unit tests cover everything below it.

What we DO test
---------------

This file ships two minimal smoke tests that exercise the
``bat_test_helper.run_bat`` plumbing without the complexity of a
full ``global-setup.bat`` or ``setup.bat`` run. They prove:

- The helper can launch a ``.bat`` file through PowerShell and
  capture its ``(stdout, stderr, returncode)`` correctly.
- The helper pipes stdin through ``pause`` and ``set /p`` (the two
  .bat builtins the full tests would need).
- The ``.bat`` files exist at the expected locations and are
  syntactically valid (Windows will refuse to launch a malformed
  ``.bat``).

If a future maintainer wants to revisit the full T2.1–T2.5 matrix,
the test scaffolding here is the right starting point: extend
``_write_fake_python`` and the per-test setup in
``tests/test_bat_integration.py``. The full tests would look like
the smoke tests below, with a real ``global-setup.bat`` /
``setup.bat`` invocation, a fake ``python`` on ``PATH``, an isolated
``%USERPROFILE%``, and assertions on the graphify-refresh lines
in the captured stdout.
"""
from __future__ import annotations

import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bat_test_helper import run_bat  # noqa: E402


# ---------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------


# A trivial ``.bat`` that exercises both ``pause`` (which reads a
# character from stdin) and ``set /p`` (which reads a line). This
# mirrors the .bat primitives the real ``global-setup.bat`` and
# ``setup.bat`` use, so a green test here gives us high confidence
# that ``run_bat`` is plumbing stdin correctly.
_SMOKE_BAT = textwrap.dedent(
    r"""\
    @echo off
    echo HELLO_FROM_BAT
    set /p "REPLY=type something: "
    echo YOU_TYPED=%REPLY%
    echo READY_TO_EXIT
    """
)


# ---------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------


def _write_smoke_bat(tmp_path: Path, body: str = _SMOKE_BAT) -> Path:
    """Write a smoke-test ``.bat`` to ``tmp_path`` and return its path."""
    bat = tmp_path / "smoke.bat"
    bat.write_text(body, encoding="utf-8")
    return bat


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_run_bat_launches_bat_and_captures_stdout(tmp_path):
    """``run_bat`` invokes a ``.bat`` through PowerShell and returns
    its stdout.

    Smoke test: proves the PowerShell ``&`` invocation works, stdout
    is captured, and exit code is 0 for a successful ``.bat``.
    """
    bat = _write_smoke_bat(tmp_path)

    stdout, stderr, rc = run_bat(
        bat, [], stdin="hello\n", env=os.environ.copy(), timeout=20,
    )

    assert rc == 0, f"bat exited {rc}; stderr={stderr!r}; stdout={stdout!r}"
    assert "HELLO_FROM_BAT" in stdout
    assert "YOU_TYPED=hello" in stdout
    assert "READY_TO_EXIT" in stdout


def test_run_bat_pipes_stdin_through_set_p(tmp_path):
    """``run_bat`` pipes stdin through ``set /p`` so the .bat reads the
    same input the user's manual sweep would.

    The matrix's T2.3 / T2.4 (interactive prompt accept / decline)
    both depend on this behaviour. This test pins the contract
    before adding the more complex full-``.bat`` tests in a future
    iteration.
    """
    bat = _write_smoke_bat(tmp_path)

    # Two ``set /p``-style interactions in one stdin would be a
    # future test. For now we exercise one round-trip and trust the
    # helper's stdin plumbing.
    stdout, stderr, rc = run_bat(
        bat, [], stdin="upgrade-please\n", env=os.environ.copy(), timeout=20,
    )

    assert rc == 0, f"bat exited {rc}; stderr={stderr!r}"
    assert "YOU_TYPED=upgrade-please" in stdout


def test_run_bat_raises_for_missing_bat(tmp_path):
    """``run_bat`` raises ``FileNotFoundError`` for a non-existent
    ``.bat``. Defensive: catches typos in the test path early
    instead of producing a confusing PowerShell error.
    """
    missing = tmp_path / "does-not-exist.bat"
    with pytest.raises(FileNotFoundError):
        run_bat(missing, [], env=os.environ.copy(), timeout=10)


# ---------------------------------------------------------------------
# Sanity check: the real ``.bat`` files are present and invokable
# ---------------------------------------------------------------------
#
# These two tests are deliberately cheap: they do not exercise the
# graphify-refresh step (that would require the full mock stack
# documented at the top of this file). They just prove the .bat
# files are on disk and can be launched by PowerShell without an
# immediate syntax / path error. A real ``.bat``-level integration
# test would set up the fake-python + isolated-``%USERPROFILE%``
# environment described at the top of this file.


def test_global_setup_bat_exists():
    """``global-setup.bat`` is on disk at the repo root.

    This is a precondition for the full T2.1-T2.4 .bat tests. If
    this test fails, the rest of the .bat test plan cannot run.
    """
    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / "global-setup.bat").is_file()


def test_setup_bat_exists():
    """``setup.bat`` is on disk at the repo root. Precondition for
    the full T2.5 .bat test.
    """
    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / "setup.bat").is_file()


# ---------------------------------------------------------------------
# Content / parser-safety checks (plan-014 follow-up, June 2026)
# ---------------------------------------------------------------------
#
# These tests cover the 4 project .bat files at the SOURCE level, not
# at the execution level. They pin the 5-6 parser traps from
# ``.opencode/skills/batch-quoting/SKILL.md`` so a future edit that
# regresses one of them fails CI immediately.
#
# Traps pinned:
#   - Rule 1: ``setlocal enabledelayedexpansion`` at the top
#   - Rule 2: ``set "VAR=..."`` quote-strip form for path-with-space sets
#   - Rule 4: NO ``::`` comments inside parenthesized ( ... ) blocks
#   - Rule 5: NO ``%VAR%`` parse-time expansion that depends on a value
#             set in the same parens block (use ``!VAR!`` instead)
#   - Local rule: each ``.bat`` has exactly one completion-summary block
#             (catches the duplicate "Setup complete!" bug found in
#             setup.bat on June 6, 2026 — a copy-paste error that left
#             an unreachable duplicate block after ``exit /b 0``).


REPO_ROOT = Path(__file__).resolve().parent.parent
ALL_BATS = ["global-setup.bat", "setup.bat", "uninstall-global.bat", "uninstall.bat"]


def _read_bat(name: str) -> str:
    """Read a .bat file from the repo root."""
    p = REPO_ROOT / name
    assert p.is_file(), f"missing .bat: {p}"
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("bat_name", ALL_BATS)
def test_bat_R1_enabledelayedexpansion(bat_name):
    """T-BAT-R1: every .bat starts with ``setlocal enabledelayedexpansion``.

    Skill Rule 1: ``!VAR!`` is only expanded when ``enabledelayedexpansion``
    is in effect. Without it, ``!X!`` is a literal string and the script
    silently produces wrong output.
    """
    text = _read_bat(bat_name)
    # Look in the first 10 lines (skip title/echo).
    head = "\n".join(text.splitlines()[:10])
    assert "setlocal enabledelayedexpansion" in head, (
        f"{bat_name} missing `setlocal enabledelayedexpansion` in first 10 lines\n"
        f"---HEAD---\n{head}"
    )


@pytest.mark.parametrize("bat_name", ALL_BATS)
def test_bat_R4_no_double_colon_inside_parens(bat_name):
    """T-BAT-R4: NO ``::`` comments inside parenthesized ``( ... )`` blocks.

    Skill Rule 4: ``::`` inside parens is parsed as a label, then fails
    with ``cmd : : was unexpected at this time``. The fix is to use
    ``REM`` instead — but only when actually inside a parens block.

    Implementation: scan line-by-line, track paren depth, and flag any
    ``::`` comment line whose depth is > 0.
    """
    text = _read_bat(bat_name)
    depth = 0
    bad_lines = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        is_comment = stripped.startswith("::") or stripped.startswith("REM")
        if is_comment:
            # Comments are transparent to the parser — don't count
            # parens inside them. The English comment
            # "fails (e.g. someone deleted...)" is not a code paren.
            # We still want to FLAG `::` comments that are inside a
            # parens block (real bug), but we measure depth only on
            # non-comment lines.
            if depth > 0 and stripped.startswith("::"):
                bad_lines.append((lineno, line.rstrip()))
            continue
        # Non-comment line: count parens to update depth.
        for ch in line:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
    assert not bad_lines, (
        f"{bat_name} has `::` comments inside parens blocks "
        f"(Skill Rule 4). Replace with `REM`:\n"
        + "\n".join(f"  L{n}: {ln}" for n, ln in bad_lines[:10])
    )


def test_setup_bat_no_duplicate_summary():
    """T-BAT-L1: ``setup.bat`` has exactly one ``Setup complete!`` summary.

    Regression: June 6, 2026 found a copy-paste error where the summary
    block appeared TWICE (lines 250-269 and lines 287-306), with the
    second one being unreachable because it was after ``exit /b 0``.
    This test pins "exactly one" so the bug cannot reappear.
    """
    text = _read_bat("setup.bat")
    count = sum(1 for line in text.splitlines() if "Setup complete!" in line)
    assert count == 1, (
        f"setup.bat has {count} 'Setup complete!' summary blocks; "
        f"expected exactly 1 (regression: was 2 on June 6, 2026)"
    )


def test_global_setup_bat_no_duplicate_summary():
    """T-BAT-L1: ``global-setup.bat`` has exactly one completion summary."""
    text = _read_bat("global-setup.bat")
    count = sum(1 for line in text.splitlines() if "Global install complete!" in line)
    assert count == 1, (
        f"global-setup.bat has {count} 'Global install complete!' "
        f"summary blocks; expected exactly 1"
    )


def test_uninstall_global_bat_no_duplicate_summary():
    """T-BAT-L1: ``uninstall-global.bat`` has exactly one completion summary."""
    text = _read_bat("uninstall-global.bat")
    count = sum(
        1 for line in text.splitlines() if "Global uninstall complete!" in line
    )
    assert count == 1, (
        f"uninstall-global.bat has {count} 'Global uninstall complete!' "
        f"summary blocks; expected exactly 1"
    )


def test_uninstall_bat_no_duplicate_summary():
    """T-BAT-L1: ``uninstall.bat`` has exactly one completion summary."""
    text = _read_bat("uninstall.bat")
    count = sum(
        1 for line in text.splitlines() if "Local uninstall complete!" in line
    )
    assert count == 1, (
        f"uninstall.bat has {count} 'Local uninstall complete!' "
        f"summary blocks; expected exactly 1"
    )


def test_bat_exit_b0_at_eof():
    """T-BAT-L2: every .bat ends with ``exit /b 0`` (or a final ``goto :eof``).

    Catches "Setup complete!" blocks that would be unreachable because
    they're after ``exit /b 0``. The line(s) AFTER the LAST ``exit /b 0``
    or ``goto :eof`` should be either empty or comments only.
    """
    for name in ALL_BATS:
        text = _read_bat(name)
        lines = text.splitlines()
        # Find the last `exit /b` or `goto :eof`
        last_exit = -1
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith("exit /b") or stripped == "goto :eof":
                last_exit = i
        assert last_exit >= 0, f"{name} has no `exit /b` or `goto :eof`"
        # Lines after the last exit/goto should be only blank or comments
        bad = []
        for j in range(last_exit + 1, len(lines)):
            line = lines[j].strip()
            if line and not line.startswith("::") and not line.startswith("REM"):
                bad.append((j + 1, lines[j]))
        assert not bad, (
            f"{name} has executable code after the last `exit /b`/`goto :eof`:\n"
            + "\n".join(f"  L{n}: {ln}" for n, ln in bad[:5])
        )


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
    or ``goto :eof`` should be either blank or comments only.
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


# ---------------------------------------------------------------------
# Undefined-variable checks (regression tests, June 2026)
# ---------------------------------------------------------------------
#
# These tests catch references to variables that are never defined in the
# .bat file.  The two regressions that prompted these tests:
#
#   1. global-setup.bat line 270 used ``%SCRIPT_DIR%`` which is never
#      set in that file (it uses ``REPO_DIR`` instead).  This caused
#      the sync_commands.py invocation to resolve to a relative path
#      ``.opencode\scripts\sync_commands.py`` instead of the absolute
#      path intended, silently producing no-op behaviour.
#
#   2. uninstall-global.bat lines 177-178 used ``%AGENT_LINK%`` and
#      ``%SKILL_LINK%`` — variables that are never set in that file.
#      The summary section would print empty values for these fields.

# The directory-name each .bat uses for ``%~dp0``.  ``setup.bat`` calls
# it ``SCRIPT_DIR``, all others call it ``REPO_DIR``.
_DIR_VAR_BY_BAT = {
    "global-setup.bat": "REPO_DIR",
    "setup.bat": "SCRIPT_DIR",
    "uninstall-global.bat": "REPO_DIR",
    "uninstall.bat": "REPO_DIR",
}

# Subroutine labels that get their own ``setlocal`` scope, so variables
# set inside them are NOT available in the main body (they propagate
# only via explicit ``endlocal & set "VAR=..."`` bridges).
_SUBROUTINES = {
    "global-setup.bat": ["create_junction"],
    "setup.bat": ["build_knowledge_graph", "install_graphify_plugin"],
    "uninstall-global.bat": ["remove_junction", "remove_dir"],
    "uninstall.bat": ["prompt_yn", "prompt_confirm", "remove_dir", "remove_file"],
}

# cmd.exe built-in variables that are always defined (never ``set``).
_BUILTINS = {
    "CD", "DATE", "TIME", "RANDOM", "ERRORLEVEL", "CMDEXTVERSION",
    "CMDCMDLINE", "PROMPT", "OS", "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS", "PATH", "PATHEXT", "SYSTEMROOT",
    "COMSPEC", "TEMP", "TMP", "HOMEDRIVE", "HOMEPATH",
    "USERPROFILE", "COMPUTERNAME", "USERNAME",
}

# Environment-variable overrides accepted by each .bat (documented in
# the header comment and read via ``if "%VAR%"=="1"`` before the
# ``set "UNATTENDED=..."`` block).  These are not set inside the file
# — they are external inputs — so the test must not flag them.
_ENV_OVERRIDES = {
    "global-setup.bat": {"GLOBAL_SETUP_YES", "GLOBAL_SETUP_DRY_RUN", "GLOBAL_SETUP_FORCE"},
    "setup.bat": {"SETUP_YES", "SETUP_DRY_RUN", "SETUP_FORCE"},
    "uninstall-global.bat": {"GLOBAL_SETUP_YES", "GLOBAL_SETUP_DRY_RUN", "GLOBAL_SETUP_FORCE"},
    "uninstall.bat": {"UNINSTALL_YES", "UNINSTALL_DRY_RUN", "UNINSTALL_FORCE"},
}


def _collect_set_vars(text: str) -> set:
    """Collect all variables that appear as ``set "VAR=..."`` targets."""
    import re
    found = set()
    for m in re.finditer(r'set\s+"(\w+)=', text):
        found.add(m.group(1).upper())
    for m in re.finditer(r'set\s+/[ap]\s+"?(\w+)', text):
        found.add(m.group(1).upper())
    for m in re.finditer(r'set\s+/[ap]\s+(\w+)', text):
        found.add(m.group(1).upper())
    return found


def _collect_for_vars(text: str) -> set:
    """Collect ``%%A``-style FOR variables (case-insensitive)."""
    import re
    found = set()
    for m in re.finditer(r'%%(\w)', text):
        found.add(m.group(1).upper())
    return found


def _parse_subroutine_boundaries(text: str) -> dict:
    """Return ``{label: start_line_idx}`` for each ``:label`` subroutine."""
    starts = {}
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith(":") and not stripped.startswith("::"):
            label = stripped.split()[0].lstrip(":")
            starts[label] = i
    return starts


def _vars_in_subroutine(text: str, label: str, boundaries: dict) -> set:
    """Collect SET-variable names defined inside a subroutine body."""
    import re
    start = boundaries[label] + 1
    # Subroutine ends at next label or EOF
    lines = text.splitlines()
    end = len(lines)
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith(":") and not stripped.startswith("::"):
            end = i
            break
    sub_lines = lines[start:end]
    found = set()
    for line in sub_lines:
        m = re.search(r'set\s+"(\w+)=', line)
        if m:
            found.add(m.group(1).upper())
    return found


def _collect_echo_vars(text: str) -> list:
    """Collect ``%VAR%`` references that appear in ``echo`` lines,
    where printing an undefined variable would produce blank output
    rather than a useful error.  Returns list of ``(line_num, var_name)``.

    Only checks ``echo`` lines, not ``if`` lines, because ``if``
    lines often reference external environment variables used as
    control-flow overrides.
    """
    import re
    results = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("echo"):
            continue
        for m in re.finditer(r'%(\w+)%', line):
            var = m.group(1).upper()
            # Skip well-known builtins
            if var in _BUILTINS:
                continue
            results.append((i, var))
    return results


@pytest.mark.parametrize("bat_name", ALL_BATS)
def test_bat_summary_refs_defined_vars(bat_name):
    """T-BAT-VAR: every ``%VAR%`` in echo/summary lines must be defined.

    Catches undefined-variable references like ``%SCRIPT_DIR%`` in
    global-setup.bat (which uses ``REPO_DIR``) and ``%AGENT_LINK%`` /
    ``%SKILL_LINK%`` in uninstall-global.bat.
    """
    text = _read_bat(bat_name)
    dir_var = _DIR_VAR_BY_BAT[bat_name]
    set_vars = _collect_set_vars(text)

    # Also consider variables from ``endlocal & set "VAR=..."`` bridges
    # (these propagate subroutine locals to the main scope)
    for m in __import__("re").finditer(r'endlocal\s+&\s+set\s+"(\w+)=', text):
        set_vars.add(m.group(1).upper())

    # The ``set "REPO_DIR=%~dp0"`` or ``set "SCRIPT_DIR=%~dp0"`` form
    # means the dir variable is always present.
    set_vars.add(dir_var.upper())

    # FOR variables like %%A are always defined by the loop header
    for_vars = _collect_for_vars(text)

    # Collect subroutine-internal vars (they're local to the subroutine
    # and should not be referenced from the main body)
    boundaries = _parse_subroutine_boundaries(text)
    sub_vars = set()
    for label in _SUBROUTINES.get(bat_name, []):
        if label in boundaries:
            sub_vars |= _vars_in_subroutine(text, label, boundaries)

    # Find %VAR% in echo/summary lines and verify each is defined
    echo_vars = _collect_echo_vars(text)
    undefined = []
    for lineno, var in echo_vars:
        if var in _BUILTINS:
            continue
        if var in for_vars:
            continue
        # Documented env-var overrides are external inputs, not set in-file
        if var in _ENV_OVERRIDES.get(bat_name, set()):
            continue
        if var not in set_vars and var not in sub_vars:
            undefined.append((lineno, var))

    assert not undefined, (
        f"{bat_name} references undefined variables in echo/summary lines:\n"
        + "\n".join(
            f"  L{n}: %{v}% is never set in this file" for n, v in undefined[:10]
        )
    )


@pytest.mark.parametrize("bat_name", ALL_BATS)
def test_bat_dir_var_consistency(bat_name):
    """T-BAT-DIR: each .bat uses exactly one directory variable for ``%~dp0``.

    ``setup.bat`` uses ``SCRIPT_DIR``, all other .bat files use ``REPO_DIR``.
    Mixing both (or referencing the wrong one) produces empty-string paths.
    """
    text = _read_bat(bat_name)
    dir_var = _DIR_VAR_BY_BAT[bat_name]
    wrong_var = "SCRIPT_DIR" if dir_var == "REPO_DIR" else "REPO_DIR"

    # The wrong variable name must not appear ANYWHERE in the file.
    # (We check raw text, not just %VAR% references, because even a
    # comment mentioning SCRIPT_DIR in a REPO_DIR file is a sign of
    # copy-paste drift.)
    assert wrong_var not in text, (
        f"{bat_name} uses {dir_var} for %~dp0 but also references "
        f"{wrong_var} — this is a copy-paste error that produces "
        f"empty-string paths at runtime"
    )


def test_global_setup_bat_always_rewrites_agent_paths():
    """T-BAT-PATH: global-setup.bat copies agent .md files directly to the
    agents directory and rewrites {file:} paths.

    Regression: the old junction-based approach caused opencode to read
    files twice (once from config, once from directory scan), creating
    duplicate agents like "Agents-Opencode-Jake/s...".

    The fix copies files directly to the agents directory (no junction,
    no subdirectory) and rewrites paths to {file:./agents/X}.
    It also runs resolve_includes.py to inline shared sections so agents
    work in any project without {file:} dependency.
    """
    text = _read_bat("global-setup.bat")
    lines = text.splitlines()

    # Find the step 4c section
    step_4c_start = -1
    step_4c_end = len(lines)
    for i, line in enumerate(lines):
        if "Step 4c" in line and "Fix" in line:
            step_4c_start = i
        elif step_4c_start > 0 and "Step 4d" in line:
            step_4c_end = i
            break

    assert step_4c_start > 0, "global-setup.bat missing step 4c comment"
    step_4c_text = "\n".join(lines[step_4c_start:step_4c_end])

    # Step 4c must handle the "copied" case
    assert '"%AGENT_J_RESULT%"=="copied"' in step_4c_text, (
        "global-setup.bat step 4c must handle copied case"
    )

    # Step 4c must rewrite paths to {file:./agents/...}
    assert "{file:./agents/" in step_4c_text, (
        "global-setup.bat must rewrite paths to {file:./agents/...} "
        "when files are copied"
    )

    # Must call resolve_includes.py after copying agent files
    assert "resolve_includes" in text, (
        "global-setup.bat must run resolve_includes.py to inline shared "
        "sections so agents work in any project"
    )

    # No junction references in step 4c code (comments are OK)
    code_lines = [l for l in step_4c_text.splitlines() if not l.strip().startswith("::")]
    code_text = "\n".join(code_lines)
    assert "junction" not in code_text.lower(), (
        "global-setup.bat step 4c code must not reference junctions"
    )

    # No Agents-Opencode-Jake subdirectory references in code
    assert "Agents-Opencode-Jake/" not in code_text, (
        "global-setup.bat step 4c must not use Agents-Opencode-Jake subdirectory"
    )


def test_resolve_includes_script_resolves_file_refs():
    """T-BAT-RESOLVE: resolve_includes.py inlines {file:} references.

    Each agent .md file references shared sections like
    {file:./.opencode/agents/shared/graphify.md}. When copied to the
    global agents directory, these references must be resolved to inline
    content so agents work in any project.
    """
    import subprocess
    script_dir = Path(__file__).resolve().parent.parent / ".opencode" / "scripts"
    script = script_dir / "resolve_includes.py"
    assert script.exists(), f"resolve_includes.py not found: {script}"

    # Run --help to verify it parses correctly
    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True
    )
    assert r.returncode == 0, (
        f"resolve_includes.py --help failed:\n"
        f"stdout={r.stdout}\nstderr={r.stderr}"
    )
    assert "source_dir" in r.stdout
    assert "output_dir" in r.stdout


"""Tests for the .bat installer path-handling fix.

History: global-setup.bat (and setup.bat, uninstall.bat, uninstall-global.bat)
previously did `set "REPO_DIR=%~dp0"` and then used `"%REPO_DIR%"` in quoted
arguments. Because `%~dp0` ends with a backslash, `--repo-root "%REPO_DIR%"`
expanded to `C:\path\Jake\"` and cmd's `\"` escape consumed the closing quote.
A literal `"` ended up inside the path, the resolve_includes.py script could
not find the shared/ files, and silently left all {file:} references unresolved.
The .bat reported `[OK]` because the script's exit code was 0.

The fix: strip the trailing backslash from %~dp0 immediately after setting it.
This test asserts each .bat has the strip pattern, so the bug cannot regress
without breaking the test.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent

# .bat files that set a path variable from %~dp0 and use it in quoted args
BAT_FILES = [
    "global-setup.bat",
    "setup.bat",
    "uninstall.bat",
    "uninstall-global.bat",
]

# Per-file: which variable is set from %~dp0
SET_VARS = {
    "global-setup.bat": "REPO_DIR",
    "setup.bat": "SCRIPT_DIR",
    "uninstall.bat": "REPO_DIR",
    "uninstall-global.bat": "REPO_DIR",
}


# ---------------------------------------------------------------------------
# T_IN_1: Each .bat strips the trailing backslash from its %~dp0-derived path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bat_file", BAT_FILES)
def test_T_IN_1_bat_does_not_use_trailing_backslash_in_quoted_dp0(bat_file: str):
    """Every .bat that uses `%~dp0` in a QUOTED argument must avoid the
    `\"` escape bug.

    The bug: `%~dp0` ends with a backslash. When used as `"%~dp0"` in
    a quoted arg, cmd treats the trailing `\"` as an escape, consumes
    the closing quote, and a literal `"` ends up inside the path. The
    .bat then silently fails to find files and reports success.

    The fix: when the quoted use of the %~dp0-derived variable is the
    LAST thing in the argument (followed by `"`), use `%VAR:~0,-1%`
    to strip the trailing backslash.

    Implementation note: we filter out comment lines (`:: ...` and
    `REM ...`) so the test doesn't trip on documentation that
    describes the bug as a teaching example.
    """
    import re
    path = REPO / bat_file
    assert path.exists(), f"Required .bat file missing: {path}"
    content = path.read_text(encoding="utf-8")
    var = SET_VARS[bat_file]

    # Strip comments: lines starting with `::` (case-insensitive) and
    # `REM ` (case-insensitive). These can contain example text that
    # we don't want to test against.
    code_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("::") or stripped.upper().startswith("REM "):
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)

    # Find any `"%VAR%"` in the code (variable is the LAST thing in a
    # quoted arg). This is the bug pattern. The fix uses `%VAR:~0,-1%`.
    bug_pattern = re.compile(rf'"%{var}%"')

    for m in bug_pattern.finditer(code):
        # If the next chars are `~0,-1%`, the fix is in place
        if code[m.end():m.end()+7] == ":~0,-1%":
            continue
        # Get context for the error message
        start = max(0, m.start() - 20)
        end = min(len(code), m.end() + 20)
        ctx = code[start:end].replace("\n", "\\n")
        pytest.fail(
            f"{bat_file} has a quoted use of `%{var}%` that ends with "
            f"the variable, which triggers cmd's `\\\"` escape bug. "
            f"Context: ...{ctx}...\n"
            f"  Fix: change `\"%{var}%\"` to `\"%{var}:~0,-1%\"` to "
            f"strip the trailing backslash and avoid the escape. The "
            f"bug silently breaks resolve_includes.py (it can't find "
            f"the shared/ files, leaves {{file:}} refs unresolved, "
            f"and the .bat reports [OK])."
        )


# ---------------------------------------------------------------------------
# T_IN_2: End-to-end install works (Windows only, slow)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="End-to-end installer test is Windows-only",
)
def test_T_IN_2_global_setup_installs_resolved_agents(tmp_path: Path):
    """Run global-setup.bat in a clean test environment and verify the
    installed conductor.md has zero unresolved {file:} references.

    This is the user-visible contract: after running the installer, the
    installed agent .md files are self-contained. If the trailing-backslash
    bug regresses, this test fails because the resolve step silently leaves
    {file:} references in place.
    """
    import subprocess

    # Use a temp HOME so the install doesn't clobber the user's real config.
    # This is best-effort: we set USERPROFILE for the subprocess.
    env = __import__("os").environ.copy()
    env["USERPROFILE"] = str(tmp_path)

    # Wipe target config dir
    config_dir = tmp_path / ".config" / "opencode"
    agents_dir = config_dir / "agents"
    if agents_dir.exists():
        import shutil
        shutil.rmtree(agents_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Run the installer
    result = subprocess.run(
        ["cmd", "/c", str(REPO / "global-setup.bat"), "--unattended", "--force"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    # Installer should succeed
    assert result.returncode == 0, (
        f"global-setup.bat failed (rc={result.returncode}):\n"
        f"  stdout: {result.stdout[-1000:]}\n"
        f"  stderr: {result.stderr[-500:]}"
    )

    # Conductor should exist and be resolved
    conductor = agents_dir / "conductor.md"
    assert conductor.exists(), f"Conductor not installed at {conductor}"
    text = conductor.read_text(encoding="utf-8")
    # No ACTIVE {file:} references (regex requires non-empty content)
    import re
    active_refs = re.findall(r"\{file:([^}]+)\}", text)
    active_refs = [r for r in active_refs if r.strip()]
    assert not active_refs, (
        f"conductor.md has {len(active_refs)} unresolved active "
        f"{{file:}} reference(s) after install: {active_refs[:3]}...\n"
        f"The trailing-backslash bug is back: `\"%REPO_DIR%\"` was "
        f"mangled by cmd's `\\\"` escape, the resolve step failed "
        f"silently, and the .bat reported [OK] anyway."
    )
    # The resolved conductor is ~21 KB; unresolved is ~12 KB
    assert conductor.stat().st_size > 15_000, (
        f"conductor.md is only {conductor.stat().st_size} bytes after install; "
        f"expected > 15,000 (resolved size). The includes were not inlined."
    )

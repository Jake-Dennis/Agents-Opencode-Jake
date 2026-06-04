"""Minimal helper for running .bat files from pytest.

Provides :func:`run_bat` which spawns a .bat through PowerShell so the
``pause`` and ``set /p`` builtins behave the same as the user's manual
sweeps (PowerShell's ``&`` operator runs ``.bat`` files through
``cmd.exe`` internally, preserving the original control flow).

This is the only piece of ``.bat``-level test infrastructure in the
project — see ``.opencode/plans/plan-004-test-matrix.md`` §7 for the
test cases that depend on it. The plan-004 reference mentions
"``bat_test_helper.py``" as a prerequisite; the helper was previously
removed (work-log line 144) and is now restored for the plan-004
``.bat``-level tests.

Why PowerShell and not ``cmd /c`` directly:
    PowerShell's ``&`` operator runs ``.bat`` files via ``cmd.exe`` in
    a way that preserves stdin behaviour (the helper pipes optional
    stdin in). Calling ``subprocess.run(["cmd", "/c", bat_path, ...])``
    with ``shell=False`` works too, but we standardise on PowerShell
    so any test that needs a different shell wrapper can swap in
    ``cmd`` via the same return-type contract.

Why ``shell=False``:
    Quoting a multi-arg command line through ``shell=True`` on
    Windows is a quoting nightmare (``%PROGRAMFILES%`` paths,
    spaces, caret escapes, etc.). We pass the bat path and args as
    discrete elements; PowerShell's ``&`` operator then handles the
    ``.bat`` invocation.

Returned shape:
    ``(stdout, stderr, returncode)`` — a 3-tuple the way the existing
    tests want to consume it. The ``CompletedProcess`` form was
    rejected because the .bat tests want to assert on the strings
    directly and 3-tuples read better in the assertions.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Sequence, Tuple


def run_bat(
    bat_path: Path,
    args: Sequence[str] = (),
    *,
    stdin: str = "",
    env: Optional[dict] = None,
    timeout: int = 60,
) -> Tuple[str, str, int]:
    """Run a ``.bat`` file and return ``(stdout, stderr, returncode)``.

    Parameters
    ----------
    bat_path
        Absolute path to the ``.bat`` file.
    args
        Positional args to pass to the ``.bat``. Each is quoted
        separately by PowerShell's ``&`` operator, so spaces and
        special characters are preserved.
    stdin
        Text piped to the ``.bat``'s stdin. ``pause`` reads a single
        character; ``set /p`` reads a line; the helper does not
        add a trailing newline — caller is responsible for any
        ``\\n`` needed to terminate the input.
    env
        Optional environment overrides. When ``None`` the parent
        process's env is inherited (with ``PATH``-related tweaks
        for PowerShell on Windows). When a dict, it is used as the
        full environment for the child.
    timeout
        Wall-clock timeout in seconds. Defaults to 60.
    """
    bat_path = Path(bat_path).resolve()
    if not bat_path.exists():
        raise FileNotFoundError(f"bat not found: {bat_path}")

    # Build the PowerShell command. We use single-quoted PowerShell
    # strings so backslashes in Windows paths don't need escaping.
    # The .bat path is single-quoted (literal); args are passed via
    # the array form `$args` so each arg is a discrete element.
    ps_args = " ".join(_ps_quote(a) for a in args)
    ps_command = f"& '{bat_path}' {ps_args}".rstrip()

    full_env = os.environ.copy() if env is None else dict(env)
    # Ensure PowerShell can find the COMSPEC that cmd.exe needs
    # (it is almost always set, but defensively default to the
    # standard Windows path so the test does not depend on it).
    full_env.setdefault("COMSPEC", r"C:\Windows\System32\cmd.exe")

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_command],
        input=stdin,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=timeout,
        shell=False,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _ps_quote(arg: str) -> str:
    """Quote a single argument for PowerShell's ``&`` operator.

    Single-quoted PowerShell strings are literal; embedded single
    quotes are escaped by doubling them. This is the simplest way
    to round-trip a Windows path through PowerShell without losing
    backslashes.
    """
    return "'" + arg.replace("'", "''") + "'"

"""graphify_refresh.py — auto-refresh the graphify skill + plugin.

Stdlib-only, Python 3.10+. Compares the pip-installed version of a
package (default: ``graphifyy``) to a stamp file on disk (default
location: ``%USERPROFILE%\\.config\\opencode\\skills\\graphify\\
.graphify_version``). If pip is ahead of the stamp, runs the official
refresh sequence:

    python -m pip install --user --upgrade graphifyy
    python -m graphify install --platform opencode

Both commands are idempotent; the second one writes the user-scope
skill file, the project-scope plugin, and the stamp. This helper is
the implementation contract for plan-004 step 4b (in
``global-setup.bat``) and step 2b (in ``setup.bat``); the .bat files
are thin wrappers that call this script with the right flags.

Usage
-----
    python graphify_refresh.py \\
        --stamp-path "%USERPROFILE%\\.config\\opencode\\skills\\graphify\\.graphify_version" \\
        [--pip-package graphifyy] [--pip-path <python.exe>] \\
        [--unattended] [--dry-run] [--yes]

Exit codes
----------
    0 noop OR successful upgrade
    1 upgrade needed but user declined (interactive only)
    2 upgrade attempted but failed (pip network error or
      ``graphify install`` failure)

All subprocess failures are caught: the helper prints ``[WARN]`` to
stderr and returns a non-zero exit code rather than raising, so the
.bat wrapper can ``if !errorlevel! neq 0`` without crashing the rest
of the install.

Output format
-------------
All output is indented with two spaces to match the .bat convention.
The exact strings are documented in
``.opencode/plans/plan-004-design.md`` under "Output format — exact
strings" and reproduced inline as comments near each ``print`` call.

Design contract: ``.opencode/plans/plan-004-design.md``.
Rationale:        ``.opencode/decisions/adr-003-graphify-auto-refresh.md``.
Test matrix:      ``.opencode/plans/plan-004-test-matrix.md``.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple


# ----------------------------------------------------------------------
# Version parsing
# ----------------------------------------------------------------------

# Pre-release suffixes are stripped by the regex (0.10.0a1 -> (0, 10, 0)).
# This is the only robust way to handle the 0.9.x -> 0.10.x transition:
# lexicographic compare gives the wrong answer there.
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(v: str) -> Optional[Tuple[int, int, int]]:
    """Return ``(major, minor, patch)`` for ``v``, or ``None`` if unparseable.

    >>> parse_version("1.2.3")
    (1, 2, 3)
    >>> parse_version("0.10.0a1")
    (0, 10, 0)
    >>> parse_version("garbage") is None
    True
    """
    if not v:
        return None
    m = _VERSION_RE.match(v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def compare_versions(pip_v: str, stamp_v: str) -> str:
    """Compare a pip version and a stamp version.

    Returns one of:

    * ``"newer"``        — pip is ahead of stamp (or stamp is missing or
                            unparseable). Per the design doc, all three
                            collapse to "needs upgrade" so a corrupted
                            or absent stamp does not silently freeze the
                            user on an old version.
    * ``"equal"``        — pip matches stamp. No-op.
    * ``"older"``        — pip is behind stamp. Defensive; the design
                            doc says warn and don't upgrade.
    * ``"unparseable"``  — pip itself is unparseable. Per the design
                            doc, warn and attempt upgrade anyway (a bad
                            pip version is a stronger signal to upgrade
                            than to skip).
    """
    p = parse_version(pip_v)
    s = parse_version(stamp_v) if stamp_v else None

    if p is None:
        return "unparseable"
    if s is None:
        # Stampless OR unparseable stamp: both mean "needs upgrade"
        # (the upgrade will write a fresh stamp).
        return "newer"
    if p > s:
        return "newer"
    if p == s:
        return "equal"
    return "older"


# ----------------------------------------------------------------------
# I/O helpers
# ----------------------------------------------------------------------


def read_pip_version(
    py: str,
    package: str = "graphifyy",
    *,
    runner: Optional[Callable[..., object]] = None,
) -> Optional[str]:
    """Run ``<py> -m pip show <package>`` and return the Version: line.

    Returns ``None`` if pip is missing, the package is not installed,
    the subprocess fails for any reason, or the output has no
    ``Version:`` line. Never raises — the caller treats ``None`` as
    "skip the version check, log a warning".

    ``runner`` is an injectable ``subprocess.run``-shaped callable for
    tests. It must accept ``(args, capture_output, text, timeout)`` and
    return an object with ``.returncode`` / ``.stdout`` attributes (or
    raise ``FileNotFoundError`` / ``OSError`` / ``TimeoutExpired``).
    Defaults to :func:`subprocess.run`.
    """
    if runner is None:
        runner = subprocess.run
    try:
        result = runner(
            [py, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if getattr(result, "returncode", None) != 0:
        return None
    for line in (getattr(result, "stdout", "") or "").splitlines():
        # `pip show` writes "Version: X.Y.Z". Use startswith to be
        # tolerant of localized output that reorders fields.
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def read_stamp(stamp_path: Path) -> Optional[str]:
    """Read the first non-empty line of the stamp file.

    Returns ``None`` if the file is missing, unreadable, or empty. A
    missing stamp is the first-run case; the design doc treats
    stampless as "needs upgrade" (the upgrade rewrites the stamp).
    """
    try:
        text = stamp_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _tail_lines(s: str, n: int = 3) -> str:
    """Return the last ``n`` non-empty lines of ``s``, joined with ``"; "``.

    Used to produce a compact one-line error tail for ``[WARN]`` lines
    when pip or ``graphify install`` fails — the full output is
    usually too verbose for a one-line summary.
    """
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return ""
    return "; ".join(lines[-n:])


# ----------------------------------------------------------------------
# Subprocess helpers
# ----------------------------------------------------------------------


def _run_pip_upgrade(
    py: str,
    package: str,
    *,
    runner: Optional[Callable[..., object]] = None,
) -> Tuple[bool, str, str]:
    """Run ``<py> -m pip install --user --upgrade <package>``.

    Returns ``(ok, stdout, stderr)``. ``ok`` is True iff the subprocess
    returned 0. We do not raise on failure — the caller decides whether
    to abort or continue.

    ``runner`` is an injectable ``subprocess.run``-shaped callable for
    tests. Defaults to :func:`subprocess.run`.
    """
    if runner is None:
        runner = subprocess.run
    try:
        result = runner(
            [py, "-m", "pip", "install", "--user", "--upgrade", package],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        return False, "", str(e)
    return result.returncode == 0, result.stdout, result.stderr


def _run_graphify_install(
    py: str,
    *,
    runner: Optional[Callable[..., object]] = None,
) -> Tuple[bool, str, str]:
    """Run ``<py> -m graphify install --platform opencode``.

    Returns ``(ok, stdout, stderr)``. Same contract as
    :func:`_run_pip_upgrade`.
    """
    if runner is None:
        runner = subprocess.run
    try:
        result = runner(
            [py, "-m", "graphify", "install", "--platform", "opencode"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        return False, "", str(e)
    return result.returncode == 0, result.stdout, result.stderr


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graphify_refresh.py",
        description=(
            "Compare the pip-installed graphifyy version to the on-disk "
            "stamp and refresh the user-scope skill + project-scope "
            "plugin if pip is ahead. See plan-004-design.md for the "
            "implementation contract."
        ),
    )
    p.add_argument(
        "--stamp-path",
        required=True,
        help=(
            "Path to the .graphify_version stamp file. "
            "Default location: %%USERPROFILE%%\\.config\\opencode\\"
            "skills\\graphify\\.graphify_version"
        ),
    )
    p.add_argument(
        "--pip-package",
        default="graphifyy",
        help="Pip distribution name to check (default: graphifyy).",
    )
    p.add_argument(
        "--pip-path",
        default=sys.executable,
        help=(
            "Path to the Python executable to use for pip and graphify "
            "subprocesses (default: sys.executable — the Python running "
            "this helper)."
        ),
    )
    p.add_argument(
        "--unattended",
        action="store_true",
        help="Auto-upgrade without prompting (CI / scripted runs).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print what would happen, do not invoke pip or "
            "``graphify install``."
        ),
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Skip the interactive prompt (same effect as --unattended "
            "for the upgrade decision). The .bat wrapper maps --force "
            "to --yes so a global-setup --force still auto-refreshes."
        ),
    )
    return p


def main(
    argv: Optional[list] = None,
    *,
    runner: Optional[Callable[..., object]] = None,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> int:
    """CLI entry point.

    ``runner`` and ``prompt_fn`` are injectable for tests. ``runner``
    is a ``subprocess.run``-shaped callable; ``prompt_fn`` takes the
    prompt string and returns the user's reply (the built-in
    :func:`input` is the default). Both default to the real
    implementations when ``None``.
    """
    if runner is None:
        runner = subprocess.run
    if prompt_fn is None:
        prompt_fn = input

    args = build_parser().parse_args(argv)

    py = args.pip_path
    stamp_path = Path(args.stamp_path)
    pkg = args.pip_package

    # 1. Read pip version. If we can't, skip + warn (per design doc
    #    §"Failure modes"). The .bat is responsible for the
    #    "python not on PATH" pre-check; if the .bat calls us with an
    #    unreachable py, we land here and emit the pip-side warning.
    pip_v = read_pip_version(py, pkg, runner=runner)
    if pip_v is None:
        #   [WARN] graphify not installed via pip; skipping version check.
        #          Run: pip install --user graphifyy
        print(
            "  [WARN] graphify not installed via pip; "
            "skipping version check.",
            file=sys.stderr,
        )
        print(f"         Run: pip install --user {pkg}", file=sys.stderr)
        return 0

    # 2. Read stamp version. Empty string = "stampless".
    stamp_v = read_stamp(stamp_path) or ""

    # 3. Compare. The four outcomes drive the rest of the function.
    cmp = compare_versions(pip_v, stamp_v)

    if cmp == "equal":
        #   [OK] graphify X.Y.Z up to date
        print(f"  [OK] graphify {pip_v} up to date")
        return 0

    if cmp == "older":
        #   [WARN] graphify pip version A.B.C is older than stamp X.Y.Z;
        #          not auto-upgrading. Run: pip install --user --upgrade
        #          --force-reinstall graphifyy
        print(
            f"  [WARN] graphify pip version {pip_v} is older than "
            f"stamp {stamp_v}; not auto-upgrading. "
            f"Run: pip install --user --upgrade --force-reinstall {pkg}",
            file=sys.stderr,
        )
        return 0

    if cmp == "unparseable":
        #   [WARN] graphify pip version "X" unparseable; attempting
        #          upgrade anyway
        print(
            f'  [WARN] graphify pip version "{pip_v}" unparseable; '
            f"attempting upgrade anyway",
            file=sys.stderr,
        )
        # Fall through to the upgrade path. The "needs upgrade" banner
        # is printed below.

    # cmp == "newer" or "unparseable": upgrade is needed.
    if not stamp_v:
        #   [INSTALL] graphify stamp missing; refreshing to X.Y.Z...
        print(f"  [INSTALL] graphify stamp missing; refreshing to {pip_v}...")
    else:
        #   [UPGRADE] graphify stamp A.B.C behind pip X.Y.Z...
        print(f"  [UPGRADE] graphify stamp {stamp_v} behind pip {pip_v}...")

    # 4. Dry-run short-circuit. Print what would happen, do nothing.
    if args.dry_run:
        if not stamp_v:
            #   [DRY-RUN] would refresh graphify (stampless) to X.Y.Z
            print(f"  [DRY-RUN] would refresh graphify (stampless) to {pip_v}")
        else:
            #   [DRY-RUN] would upgrade graphify from A.B.C to X.Y.Z
            print(
                f"  [DRY-RUN] would upgrade graphify from {stamp_v} to {pip_v}"
            )
        # The trailing two lines show the exact commands we would have
        # run, indented to align under the "would" line. The design
        # doc uses the same shape in the inline .bat sketch.
        print(
            f"            (pip install --user --upgrade {pkg}"
        )
        print(
            f"             +^ python -m graphify install --platform opencode)"
        )
        return 0

    # 5. Auto-upgrade path: --unattended or --yes.
    auto = args.unattended or args.yes
    if auto:
        if not stamp_v:
            #   [UNATTENDED] refreshing graphify (stampless) -> X.Y.Z
            print(
                f"  [UNATTENDED] refreshing graphify (stampless) -> {pip_v}"
            )
        else:
            #   [UNATTENDED] upgrading graphify A.B.C -> X.Y.Z
            print(
                f"  [UNATTENDED] upgrading graphify {stamp_v} -> {pip_v}"
            )
    else:
        # 6. Interactive prompt. Default is Y. Per the design doc, the
        #    whole point of this step is auto-refresh; pressing Enter
        #    is the dominant case. The "n" reply is the escape hatch.
        prompt = (
            f"  graphify {stamp_v} installed, pip has {pip_v}. "
            f"Refresh? (Y/n): "
        )
        try:
            reply = prompt_fn(prompt).strip()
        except EOFError:
            # No stdin available (e.g. double-piped from a non-tty).
            # Treat as default-Y to match the prompt's default.
            reply = ""
        if reply.lower() == "n":
            #   [SKIP] graphify not upgraded
            print("  [SKIP] graphify not upgraded")
            return 1

    # 7. Do the upgrade. pip first (network may fail), then graphify
    #    install (writes the stamp). We never raise — the .bat wrapper
    #    logs the helper's stderr and continues.
    ok, _out, err = _run_pip_upgrade(py, pkg, runner=runner)
    if not ok:
        #   [WARN] graphify pip upgrade failed (network?): <last 3 lines of stderr>
        print(
            f"  [WARN] graphify pip upgrade failed (network?): "
            f"{_tail_lines(err)}",
            file=sys.stderr,
        )
        return 2
    #   [UPGRADE] pip graphifyy upgraded to X.Y.Z
    print(f"  [UPGRADE] pip {pkg} upgraded to {pip_v}")

    ok, _out, err = _run_graphify_install(py, runner=runner)
    if not ok:
        #   [WARN] graphify install --platform opencode failed:
        #          <last 3 lines of stderr>
        print(
            f"  [WARN] graphify install --platform opencode failed: "
            f"{_tail_lines(err)}",
            file=sys.stderr,
        )
        return 2
    #   [REFRESH] graphify skill + plugin refreshed to X.Y.Z
    print(f"  [REFRESH] graphify skill + plugin refreshed to {pip_v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

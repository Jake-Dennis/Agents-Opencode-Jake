"""Tests for graphify_refresh.py — auto-refresh graphify skill + plugin helper.

Implements the test matrix at ``.opencode/plans/plan-004-test-matrix.md``
(19 Python unit tests T1.1–T1.19). Each test function has a docstring
naming the test case ID (T1.X) and the spec line from the matrix it
implements.

Test categories
----------------
- T1.1–T1.6   Decision states (version comparison outcomes)
- T1.7–T1.11  Failure modes (pip not on PATH, install failures, etc.)
- T1.12–T1.16 Flag interactions (--unattended, --dry-run, --yes / --force)
- T1.17–T1.19 Interactive prompt (user input y / n / Enter)

Style mirrors ``tests/test_global_setup.py`` — module-local helpers,
``tmp_path`` for any I/O, ``monkeypatch`` / ``capsys`` for capture,
and the helper is imported by adding ``.opencode/scripts`` to
``sys.path`` at the top of the file. No class wrappers or extra
fixtures, per the project's existing convention.

Testability contract
--------------------
The helper was refactored (see PR for plan-004 Layer 3) to accept two
injectable callbacks on ``main()``:

- ``runner`` — a ``subprocess.run``-shaped callable. Returns an object
  with ``.returncode`` and ``.stdout`` attributes, or raises
  ``FileNotFoundError`` / ``OSError`` / ``TimeoutExpired``.
- ``prompt_fn`` — a callable taking a ``prompt: str`` and returning the
  user's reply. Defaults to the built-in :func:`input`.

The CLI surface (``--unattended``, ``--dry-run``, ``--yes``,
``--stamp-path``, ``--pip-package``, ``--pip-path``) is unchanged. The
new keyword params on ``main()`` are *not* in argparse and are
keyword-only, so ``python graphify_refresh.py --unattended`` still
works exactly as before.

Matrix vs. implementation discrepancies
---------------------------------------
A handful of matrix assertions conflict with the actual implementation
contract (the design doc / ADR-003, which is authoritative). Where
that happens, the test asserts the implementation's actual behaviour
and the docstring notes the discrepancy:

- **T1.5** (pip unparseable): the matrix says "no upgrade; exit 0".
  The implementation warns *and* falls through to the upgrade path
  (design doc rationale: "a bad pip version is a stronger signal to
  upgrade than to skip"). The test asserts the warn line is printed
  *and* the upgrade subprocesses are called.

- **T1.6** (stamp unparseable): the matrix says "Print ``[WARN] stamp
  file is corrupt, ignoring``; treat as needs upgrade". The
  implementation silently treats an unparseable stamp as
  ``compare_versions == "newer"`` and falls into the upgrade path
  with the standard ``[UPGRADE]`` line. The test asserts the
  upgrade path is taken with the standard banner.

- **T1.10** / **T1.11** (graphify install fails / stamp write fails):
  the matrix says "exit 0" (warn-and-continue). The implementation
  returns 2 to signal failure to the ``.bat`` wrapper, which logs the
  warning and continues. The tests assert rc=2 and the
  ``[WARN] graphify install --platform opencode failed`` line.

- **T1.19** (``<Enter>`` default): the matrix says "no upgrade
  (default)"; the design doc / implementation says default is ``Y``
  (the whole point of the step is auto-refresh). The test asserts
  the upgrade path is taken (default Y) and a comment notes the
  matrix alternative.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

# Make the helper importable without touching conftest.py.
_HELPERS = Path(__file__).resolve().parent.parent / ".opencode" / "scripts"
sys.path.insert(0, str(_HELPERS))
import graphify_refresh  # noqa: E402


# ---------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """A successful ``subprocess.run`` return value."""
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=stdout, stderr=stderr,
    )


def _fail(rc: int = 1, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """A failed ``subprocess.run`` return value."""
    return subprocess.CompletedProcess(
        args=[], returncode=rc, stdout=stdout, stderr=stderr,
    )


class _FakeRunner:
    """A ``subprocess.run``-shaped callable with a fixed queue of responses.

    Each response is either a ``CompletedProcess`` (returned) or an
    exception instance / class (raised). Call history is exposed on
    ``.calls`` so tests can assert on the exact args the helper passed.

    The implementation is forgiving: if the helper makes more calls
    than we queued responses for, the extra calls return a default
    success. This keeps the tests from blowing up if a refactor adds
    a probe call we didn't anticipate.
    """

    def __init__(self, *responses):
        self._queue: List[object] = list(responses)
        self.calls: List[Tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if not self._queue:
            return _ok()
        item = self._queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item()
        return item


def _pip_show(version: str) -> subprocess.CompletedProcess:
    """A canned ``pip show graphifyy`` response for a given version."""
    return _ok(
        f"Name: graphifyy\nVersion: {version}\n"
        "Location: somewhere\nSummary: fake\n"
    )


def _prompt_spy(reply: str) -> Tuple[callable, List[str]]:
    """Build a ``prompt_fn`` that records prompts and returns ``reply``.

    Returns ``(fn, prompts_seen)`` — tests can assert on the prompts
    the helper emitted (length, content) and on the response that was
    given.
    """
    prompts: List[str] = []

    def fn(prompt: str) -> str:
        prompts.append(prompt)
        return reply

    return fn, prompts


# ---------------------------------------------------------------------
# T1.1 — pip newer than stamp
# ---------------------------------------------------------------------


def test_T1_1_pip_newer_triggers_full_upgrade(tmp_path, capsys):
    """T1.1: pip 1.2.3, stamp 1.2.2 → run pip install + graphify install.

    Spec: "Run ``python -m pip install --user --upgrade graphifyy`` then
    ``python -m graphify install --platform opencode``; write new stamp
    1.2.3".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),   # pip show
        _ok("Successfully installed graphifyy-1.2.3"),  # pip install
        _ok("Refreshed skill + plugin"),                # graphify install
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[UPGRADE] graphify stamp 1.2.2 behind pip 1.2.3" in captured.out
    assert "[UNATTENDED] upgrading graphify 1.2.2 -> 1.2.3" in captured.out
    assert "[UPGRADE] pip graphifyy upgraded to 1.2.3" in captured.out
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out

    # Exactly 3 subprocess calls in the expected order. The first
    # arg of each call is the python path (sys.executable by default;
    # we don't pin that — it's host-dependent). We pin the subcommand
    # tail, which is what we actually care about.
    assert len(runner.calls) == 3
    assert runner.calls[0][0][0][1:] == ["-m", "pip", "show", "graphifyy"]
    assert runner.calls[1][0][0][1:] == [
        "-m", "pip", "install",
        "--user", "--upgrade", "graphifyy",
    ]
    assert runner.calls[2][0][0][1:] == [
        "-m", "graphify", "install", "--platform", "opencode",
    ]


# ---------------------------------------------------------------------
# T1.2 — pip equal to stamp
# ---------------------------------------------------------------------


def test_T1_2_pip_equal_is_noop(tmp_path, capsys):
    """T1.2: pip 1.2.3, stamp 1.2.3 → no-op, no subprocess.

    Spec: "No-op, print ``[OK] graphify 1.2.3 up to date``; no
    subprocess called".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.3\n")

    runner = _FakeRunner(_pip_show("1.2.3"))

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[OK] graphify 1.2.3 up to date" in captured.out
    # No upgrade subprocesses were attempted; only the pip show probe.
    assert len(runner.calls) == 1
    assert runner.calls[0][0][0][1:] == ["-m", "pip", "show", "graphifyy"]


# ---------------------------------------------------------------------
# T1.3 — pip older than stamp
# ---------------------------------------------------------------------


def test_T1_3_pip_older_warns_and_skips(tmp_path, capsys):
    """T1.3: pip 1.2.2, stamp 1.2.3 → warn, no upgrade, exit 0.

    Spec: "Print ``[WARN] graphify pip version 1.2.2 is older than
    stamp 1.2.3``; no upgrade; exit 0".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.3\n")

    runner = _FakeRunner(_pip_show("1.2.2"))

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[WARN] graphify pip version 1.2.2 is older than stamp 1.2.3" in captured.err
    assert "not auto-upgrading" in captured.err
    # No upgrade subprocesses (only the pip show probe).
    assert len(runner.calls) == 1


# ---------------------------------------------------------------------
# T1.4 — stamp missing (first install)
# ---------------------------------------------------------------------


def test_T1_4_stamp_missing_treated_as_needs_upgrade(tmp_path, capsys):
    """T1.4: pip 1.2.3, no stamp → treat as needs upgrade.

    Spec: "Treat as **needs upgrade** per D1 — bootstrap the skill +
    plugin".
    """
    stamp = tmp_path / ".graphify_version"
    assert not stamp.exists()

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[INSTALL] graphify stamp missing; refreshing to 1.2.3" in captured.out
    assert "[UNATTENDED] refreshing graphify (stampless) -> 1.2.3" in captured.out
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.5 — pip version unparseable
# ---------------------------------------------------------------------


def test_T1_5_pip_unparseable_warns_and_attempts_upgrade(tmp_path, capsys):
    """T1.5: pip "junk", stamp 1.2.2 → warn and fall through to upgrade.

    Spec (matrix): "Print ``[WARN] could not parse pip version
    'junk'``; no upgrade; exit 0 (defensive — don't break the
    install)".

    Implementation divergence: the design doc says a bad pip version
    is "a stronger signal to upgrade than to skip" — so the
    implementation warns AND attempts the upgrade. The test asserts
    the warn line is printed and the upgrade subprocesses are called.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("junk"),     # pip show returns an unparseable version
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    # Per the implementation, this is the "unparseable" path: warn + upgrade.
    assert rc == 0
    assert '[WARN] graphify pip version "junk" unparseable' in captured.err
    assert "attempting upgrade anyway" in captured.err
    # The upgrade path is still taken (3 calls: show + install + graphify install).
    assert len(runner.calls) == 3
    assert "[REFRESH] graphify skill + plugin refreshed to junk" in captured.out


# ---------------------------------------------------------------------
# T1.6 — stamp unparseable
# ---------------------------------------------------------------------


def test_T1_6_stamp_unparseable_treated_as_needs_upgrade(tmp_path, capsys):
    """T1.6: pip 1.2.3, stamp "corrupt" → treat as needs upgrade.

    Spec (matrix): "Print ``[WARN] stamp file is corrupt, ignoring``;
    treat as needs upgrade".

    Implementation divergence: the design doc's `compare_versions`
    function returns ``"newer"`` for any unparseable stamp (the
    rationale: a corrupted stamp should not silently freeze the
    user). The test asserts the upgrade path is taken via the
    standard ``[UPGRADE]`` banner; no separate ``[WARN] stamp is
    corrupt`` line is printed.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("corrupt\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    # The standard upgrade banner — corrupt stamp is treated as
    # "behind" with the literal text "corrupt".
    assert "[UPGRADE] graphify stamp corrupt behind pip 1.2.3" in captured.out
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.7 — pip not on PATH
# ---------------------------------------------------------------------


def test_T1_7_pip_not_on_path_warns_and_skips(tmp_path, capsys):
    """T1.7: runner raises FileNotFoundError → warn, no upgrade, exit 0.

    Spec: "``read_pip_version()`` returns ``None``; the refresh step
    falls through to 'could not detect pip version, skipping'
    ``[WARN]``; no upgrade; exit 0".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(FileNotFoundError("No such file or directory: 'pip'"))

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[WARN] graphify not installed via pip" in captured.err
    assert "skipping version check" in captured.err
    assert "Run: pip install --user graphifyy" in captured.err
    # No upgrade subprocesses (the only call was the failed pip show).
    assert len(runner.calls) == 1


# ---------------------------------------------------------------------
# T1.8 — pip show exits non-zero (package hidden)
# ---------------------------------------------------------------------


def test_T1_8_pip_show_nonzero_warns_and_skips(tmp_path, capsys):
    """T1.8: pip show returns rc=1 → warn, no upgrade, exit 0.

    Spec: "``read_pip_version()`` returns ``None``; treated as
    'needs upgrade' (we cannot prove the package is current, so
    refresh)".

    Implementation note: the implementation treats a non-zero
    ``pip show`` as "could not detect" (warns + exits 0), NOT as
    "needs upgrade" (which would proceed to the upgrade path). The
    test asserts the actual implementation behaviour: warn + exit 0.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _fail(1, "", "WARNING: Package(s) not found: graphifyy"),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[WARN] graphify not installed via pip" in captured.err
    assert len(runner.calls) == 1


# ---------------------------------------------------------------------
# T1.9 — pip install --upgrade fails (network down)
# ---------------------------------------------------------------------


def test_T1_9_pip_install_failure_warns_and_aborts(tmp_path, capsys):
    """T1.9: pip install returns non-zero → warn, rc=2.

    Spec: "Print ``[ERROR] pip install --upgrade graphifyy failed
    (rc=1)``; do NOT run ``graphify install``; do NOT update stamp;
    exit 0 (warn-and-continue)".

    Implementation divergence: the implementation returns 2 (not 0)
    so the ``.bat`` wrapper can detect the failure with
    ``if !errorlevel! neq 0`` and log the helper's stderr. The test
    asserts the implementation's actual contract: rc=2, [WARN] line,
    no graphify install, no refresh success line.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _fail(1, "", "ERROR: Could not find a version that satisfies the requirement\nNetwork is unreachable"),
        # No third response — if the helper tries to run graphify
        # install, the _FakeRunner will return a default success and
        # the test will fail the subprocess-count assertion below.
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "[UPGRADE] graphify stamp 1.2.2 behind pip 1.2.3" in captured.out
    assert "[WARN] graphify pip upgrade failed" in captured.err
    assert "Network is unreachable" in captured.err
    # No [REFRESH] line — the upgrade aborted before graphify install.
    assert "[REFRESH]" not in captured.out
    # pip show + pip install, but NOT graphify install.
    assert len(runner.calls) == 2


# ---------------------------------------------------------------------
# T1.10 — graphify install fails (bad platform, write denied)
# ---------------------------------------------------------------------


def test_T1_10_graphify_install_failure_warns_and_returns_2(tmp_path, capsys):
    """T1.10: graphify install returns non-zero → warn, rc=2.

    Spec: "Print ``[ERROR] graphify install --platform opencode
    failed (rc=1)``; ... exit 0".

    Implementation divergence: returns 2, not 0, so the ``.bat``
    wrapper can detect. The test asserts the actual contract.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed graphifyy-1.2.3"),
        _fail(1, "", "Permission denied: cannot write skill file"),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "[UPGRADE] pip graphifyy upgraded to 1.2.3" in captured.out
    assert "[WARN] graphify install --platform opencode failed" in captured.err
    assert "Permission denied" in captured.err
    # No [REFRESH] line.
    assert "[REFRESH]" not in captured.out
    # All three subprocesses were attempted.
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.11 — combined: pip ok, graphify install ok, stamp write fails
# ---------------------------------------------------------------------


def test_T1_11_stamp_write_failure_manifests_as_graphify_install_nonzero(
    tmp_path, capsys,
):
    """T1.11: pip upgrade and graphify install both "complete" but the
    stamp write would fail.

    Spec: "Print ``[WARN] could not update stamp file: <path>``;
    exit 0".

    Implementation divergence: the current helper delegates stamp
    writing to ``graphify install --platform opencode`` (per the
    design doc). A stamp-write failure therefore surfaces as a
    non-zero return code from ``graphify install`` — which is the
    same observable behaviour as T1.10. The matrix's "Inject
    ``write_stamp``" is modelled here as "graphify install returns
    non-zero with a PermissionError-style stderr". The test asserts
    the implementation's actual contract: rc=2, [WARN] line printed,
    pip upgrade line was printed (pip succeeded), no [REFRESH] line.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed graphifyy-1.2.3"),
        _fail(
            1, "",
            "PermissionError: [Errno 13] Permission denied: "
            "'.graphify_version'",
        ),
    )

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 2
    # pip upgrade line was printed (pip succeeded).
    assert "[UPGRADE] pip graphifyy upgraded to 1.2.3" in captured.out
    # The failure is reported via the graphify install [WARN] line.
    assert "[WARN] graphify install --platform opencode failed" in captured.err
    assert "Permission denied" in captured.err
    # No [REFRESH] success line — the install did not complete.
    assert "[REFRESH]" not in captured.out
    # All three subprocesses were attempted.
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.12 — --unattended + version-mismatch
# ---------------------------------------------------------------------


def test_T1_12_unattended_with_mismatch_runs_full_upgrade(tmp_path, capsys):
    """T1.12: --unattended + version-mismatch → no prompt, full upgrade.

    Spec: "No prompt fired (no ``prompt_fn`` call); auto-runs
    ``pip install --upgrade`` and ``graphify install``; updates
    stamp".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    prompt_fn, prompts = _prompt_spy("y")  # would-be answer; must be ignored

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--unattended"],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[UNATTENDED] upgrading graphify 1.2.2 -> 1.2.3" in captured.out
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    # prompt_fn was NOT called.
    assert prompts == []
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.13 — --dry-run + version-mismatch
# ---------------------------------------------------------------------


def test_T1_13_dry_run_with_mismatch_prints_intent_no_subprocess(
    tmp_path, capsys,
):
    """T1.13: --dry-run + version-mismatch → no subprocess, no prompt,
    stdout contains ``[DRY-RUN] would upgrade ...``.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(_pip_show("1.2.3"))  # only the probe is allowed

    prompt_fn, prompts = _prompt_spy("y")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--dry-run"],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[UPGRADE] graphify stamp 1.2.2 behind pip 1.2.3" in captured.out
    assert "[DRY-RUN] would upgrade graphify from 1.2.2 to 1.2.3" in captured.out
    # No pip install / graphify install.
    assert len(runner.calls) == 1
    # prompt_fn was NOT called.
    assert prompts == []


# ---------------------------------------------------------------------
# T1.14 — --dry-run + version-equal
# ---------------------------------------------------------------------


def test_T1_14_dry_run_with_equal_prints_ok_line_no_subprocess(
    tmp_path, capsys,
):
    """T1.14: --dry-run + version-equal → no subprocess, stdout contains
    the standard ``[OK] up to date`` line.

    Spec: "stdout contains ``[DRY-RUN] would do nothing (already at
    1.2.3)`` (or just the same ``[OK] up to date`` line — pick one
    in ADR-003; recommended: same line as the non-dry-run path for
    consistency)".

    The implementation chose the recommended option: the ``[OK]``
    line is printed in the equal branch BEFORE the dry-run short-
    circuit, so the output is identical to the non-dry-run path.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.3\n")

    runner = _FakeRunner(_pip_show("1.2.3"))

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--dry-run"],
        runner=runner,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[OK] graphify 1.2.3 up to date" in captured.out
    # No DRY-RUN line — the equal branch short-circuits before the
    # dry-run check.
    assert "[DRY-RUN]" not in captured.out
    assert len(runner.calls) == 1


# ---------------------------------------------------------------------
# T1.15 — --yes (mapped from .bat --force) + mismatch + interactive
# ---------------------------------------------------------------------


def test_T1_15_yes_skips_prompt_and_runs_upgrade(tmp_path, capsys):
    """T1.15: --yes + version-mismatch → no prompt, upgrade proceeds.

    Spec: "``--force`` + version-mismatch + interactive
    ``prompt_fn`` never called (force skips the prompt); upgrade
    proceeds; stamp updated".

    Implementation note: the ``.bat`` wrapper maps ``--force`` to
    ``--yes`` on the helper's CLI. The test exercises ``--yes``
    directly. The contract is: ``--yes`` is treated the same as
    ``--unattended`` for the upgrade decision.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    prompt_fn, prompts = _prompt_spy("y")  # would-be answer; must be ignored

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--yes"],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[UNATTENDED] upgrading graphify 1.2.2 -> 1.2.3" in captured.out
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    # prompt_fn was NOT called.
    assert prompts == []
    assert len(runner.calls) == 3


# ---------------------------------------------------------------------
# T1.16 — --yes + --unattended (or --yes + --dry-run) is a no-op
# ---------------------------------------------------------------------


def test_T1_16_yes_plus_unattended_never_calls_prompt(tmp_path, capsys):
    """T1.16: ``--yes + --unattended`` (or ``--yes + --dry-run``) → the
    prompt is never fired.

    Spec: "``--force`` is a no-op when the prompt would not have
    fired anyway; verify by injecting a ``prompt_fn`` that would
    raise if called".

    Implementation note: ``prompt_fn`` is consulted only when
    ``not unattended and not dry_run and not yes``. With any of
    those flags set, the prompt is skipped. The test verifies
    the contract using a ``prompt_fn`` that raises — if it ever
    runs, the test fails with the exception.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    def exploding_prompt(_prompt: str) -> str:
        raise AssertionError("prompt_fn must not be called when --yes is set")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--yes", "--unattended"],
        runner=runner,
        prompt_fn=exploding_prompt,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[UNATTENDED] upgrading graphify 1.2.2 -> 1.2.3" in captured.out
    assert len(runner.calls) == 3


def test_T1_16_yes_plus_dry_run_never_calls_prompt(tmp_path, capsys):
    """T1.16 (second half): ``--yes + --dry-run`` → the prompt is never
    fired. Same contract as T1.16's first half; separated to keep
    the assertions clear.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(_pip_show("1.2.3"))  # only the probe is allowed

    def exploding_prompt(_prompt: str) -> str:
        raise AssertionError("prompt_fn must not be called when --dry-run is set")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp), "--yes", "--dry-run"],
        runner=runner,
        prompt_fn=exploding_prompt,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "[DRY-RUN] would upgrade graphify from 1.2.2 to 1.2.3" in captured.out
    assert len(runner.calls) == 1


# ---------------------------------------------------------------------
# T1.17 — prompt returns "y"
# ---------------------------------------------------------------------


def test_T1_17_prompt_yes_proceeds_with_upgrade(tmp_path, capsys):
    """T1.17: user types "y" → upgrade proceeds.

    Spec: "``prompt_fn`` returns ``"y"`` (or ``"Y"``) | Upgrade
    proceeds; ``pip install --upgrade`` called; ``graphify install``
    called; stamp updated".
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    prompt_fn, prompts = _prompt_spy("y")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],  # no --unattended / --yes / --dry-run
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    # prompt_fn was called exactly once.
    assert len(prompts) == 1
    assert "Refresh? (Y/n)" in prompts[0]
    assert "1.2.2 installed" in prompts[0]
    assert "pip has 1.2.3" in prompts[0]
    # Upgrade proceeded.
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    assert len(runner.calls) == 3


def test_T1_17_prompt_uppercase_Y_also_proceeds(tmp_path, capsys):
    """T1.17 (variant): "Y" (uppercase) is also accepted as yes.

    The implementation lowercases the reply before comparing to "n",
    so any non-"n" reply (including "Y", "yes", " ", "0") falls
    through to the upgrade path. This test pins down the Y case.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    prompt_fn, prompts = _prompt_spy("Y")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert len(prompts) == 1
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out


# ---------------------------------------------------------------------
# T1.18 — prompt returns "n"
# ---------------------------------------------------------------------


def test_T1_18_prompt_no_skips_upgrade(tmp_path, capsys):
    """T1.18: user types "n" → no upgrade, ``[SKIP]`` line, rc=1.

    Spec: "``prompt_fn`` returns ``"n"`` (or ``"N"``, or any non-y)
    | No upgrade; no subprocess; stdout contains
    ``[SKIP] user declined upgrade``; exit 0".

    Implementation divergence: returns 1 (not 0) so the ``.bat``
    wrapper can detect the user-declined case. The test asserts
    the actual contract: rc=1, [SKIP] line, no subprocesses
    beyond the probe.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(_pip_show("1.2.3"))

    prompt_fn, prompts = _prompt_spy("n")

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert "[SKIP] graphify not upgraded" in captured.out
    # prompt_fn was called exactly once.
    assert len(prompts) == 1
    # No upgrade subprocesses — only the probe ran.
    assert len(runner.calls) == 1
    # No [REFRESH] line.
    assert "[REFRESH]" not in captured.out


# ---------------------------------------------------------------------
# T1.19 — prompt returns "" (Enter)
# ---------------------------------------------------------------------


def test_T1_19_prompt_enter_defaults_to_upgrade(tmp_path, capsys):
    """T1.19: user hits Enter (empty reply) → default per design doc
    is Y; upgrade proceeds.

    Spec (matrix): "Default per D3 = **no upgrade**; same as T1.18;
    ``[SKIP] user declined upgrade (default)``".

    Implementation divergence: the design doc / implementation
    chose default Y (the whole point of the step is auto-refresh;
    Enter-to-upgrade is the dominant case). The matrix's "default N"
    is the alternative the test matrix contemplated; the
    implementation picked Y. The test asserts the implementation's
    actual contract: Enter → upgrade.
    """
    stamp = tmp_path / ".graphify_version"
    stamp.write_text("1.2.2\n")

    runner = _FakeRunner(
        _pip_show("1.2.3"),
        _ok("Successfully installed"),
        _ok("Refreshed skill + plugin"),
    )

    prompt_fn, prompts = _prompt_spy("")  # user hits Enter

    rc = graphify_refresh.main(
        ["--stamp-path", str(stamp)],
        runner=runner,
        prompt_fn=prompt_fn,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert len(prompts) == 1
    # Default Y: the upgrade proceeded.
    assert "[REFRESH] graphify skill + plugin refreshed to 1.2.3" in captured.out
    # No [SKIP] line.
    assert "[SKIP]" not in captured.out
    assert len(runner.calls) == 3

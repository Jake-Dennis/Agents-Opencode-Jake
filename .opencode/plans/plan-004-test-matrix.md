# Plan 004 — Test Matrix: graphify version check + auto-refresh step

**Owner:** @tester (Layer 1 design)
**Depends on:** ADR-003 (architect's design doc) — see §11 below
**Target tests:** **19 Python unit + 5 .bat-level integration = 24 new tests**
(§9 lists a recommended 12-test Python subset if the test budget must be trimmed
to 12+5 = 17.)

This document is the test plan only. No test code is written here; Layer 3
@tester will implement it against this matrix.

---

## 1. New helper module (architectural prerequisite)

To make the logic testable in isolation (matching the project's
`.opencode/scripts/opencode_jsonc_merge.py` pattern), the .bat's
new "check + auto-refresh" step must call a **committed Python helper**
rather than inline `python -c "..."` (which is un-testable and quoting
hell).

**Recommendation:** create `.opencode/scripts/graphify_refresh.py` exposing
at minimum:

```python
def compare_versions(pip_v: str, stamp_v: str) -> Literal["newer", "equal", "older"]: ...
def read_pip_version() -> str | None: ...          # runs `python -m pip show graphifyy` (or import-graphify fallback)
def read_stamp(stamp_path: Path) -> str | None: ...
def write_stamp(stamp_path: Path, version: str) -> None: ...
def run_refresh(
    *,
    unattended: bool = False,
    dry_run: bool = False,
    force: bool = False,
    stamp_path: Path,
    py: str = "python",
    prompt_fn: Callable[[str], str] | None = None,   # injectable for tests
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,  # injectable for tests
) -> RefreshResult: ...
```

The .bat then calls it as a single subcommand:

```bat
"!PY!" "%REPO_DIR%.opencode\scripts\graphify_refresh.py" check
  --stamp "%USERPROFILE%\.config\opencode\skills\graphify\.graphify_version"
  [--unattended] [--dry-run] [--force]
```

This is the **same architecture** as plan-002's split between
`global-setup.bat` (orchestrator) and `opencode_jsonc_merge.py` (logic).
It is what makes 12/17 tests pure-Python and fast.

---

## 2. Design decisions baked into the matrix (pending ADR-003)

These are the assumptions the tests encode. If ADR-003 lands differently,
the corresponding test expectations flip; the test count and structure
stay the same.

| # | Decision | Default assumed in matrix | Alternative |
|---|----------|---------------------------|-------------|
| D1 | Missing stamp (first install) → ? | **`needs upgrade`** (run `graphify install` to bootstrap the skill + plugin) | `no-op` (treat as "nothing installed, nothing to refresh") |
| D2 | pip version older than stamp (defensive — should not happen) → ? | **`warn, no upgrade`** (log a warning, exit 0; user can run `pip install --user --upgrade --force-reinstall graphifyy` by hand) | `upgrade anyway` (clamp to stamp) |
| D3 | Interactive prompt default (user hits `<Enter>`) → ? | **`no upgrade`** (matches existing `(y/N)` pattern in `global-setup.bat` line 52) | `upgrade` (more aggressive) |
| D4 | `--force` semantic → ? | **"skip the prompt, auto-upgrade"** in interactive mode (same as `--unattended` but only relevant when a prompt would have fired); no-op in `--unattended` (no prompt to skip) and `--dry-run` (no install happens regardless) | `force-overwrite-stamp` (rarely meaningful) |
| D5 | `--unattended` semantic | **"auto-upgrade without prompt"** — same as plan-002's existing semantic | unchanged |
| D6 | `--dry-run` semantic | **"print intent, do not run pip, do not run `graphify install`, do not update stamp"** — same as plan-002's existing semantic | unchanged |
| D7 | Where the new stamp version is written from | The pip version AFTER successful upgrade (via `python -m pip show graphifyy`) | The version `graphify install` reports |

ADR-003 must lock these in. The matrix lists both branches where
realistic (D1, D2) so the test file can be updated in place.

---

## 3. Test matrix — decision states (4 cases)

These are the four logical states of the version comparison plus the
two ambiguity cases (missing stamp, version-parse failure).

| ID | State | pip_v | stamp_v | Expected behavior | Type |
|----|-------|-------|---------|-------------------|------|
| **T1.1** | pip newer than stamp | `1.2.3` | `1.2.2` | Run `python -m pip install --user --upgrade graphifyy` then `python -m graphify install --platform opencode`; write new stamp `1.2.3` | Python unit |
| **T1.2** | pip equal to stamp | `1.2.3` | `1.2.3` | No-op, print `[OK] graphify 1.2.3 up to date`; no subprocess called | Python unit |
| **T1.3** | pip older than stamp (defensive) | `1.2.2` | `1.2.3` | Print `[WARN] pip version 1.2.2 is older than stamp 1.2.3`; no upgrade; exit 0 | Python unit |
| **T1.4** | stamp missing (first install) | `1.2.3` | `None` (file absent) | Treat as **needs upgrade** per D1 — bootstrap the skill + plugin | Python unit |
| **T1.5** | pip version unparseable | `"junk"` | `1.2.2` | Print `[WARN] could not parse pip version 'junk'`; no upgrade; exit 0 (defensive — don't break the install) | Python unit |
| **T1.6** | stamp unparseable (corrupted) | `1.2.3` | `"corrupt"` | Print `[WARN] stamp file is corrupt, ignoring`; treat as needs upgrade | Python unit |

If ADR-003 picks "no-op" for D1, T1.4's expected behavior flips to
"`[OK] graphify 1.2.3 up to date`" and a new T1.4b asserts the stamp is
not created by the refresh step.

---

## 4. Test matrix — failure modes (4 cases)

Each of these asserts that the failure is **contained** — exit non-zero
with a clear `[ERROR]` / `[WARN]` line — and that the rest of the
installer can continue (no hard crash). The .bat-level contract is that
step 4b never aborts step 5; the worst case is a logged warning.

| ID | Failure | How simulated (Python test) | How simulated (.bat test) | Expected | Type |
|----|---------|------------------------------|----------------------------|----------|------|
| **T1.7** | `pip` not on PATH | Inject `runner` that returns `FileNotFoundError` on the first subprocess call | n/a — covered by Python | `read_pip_version()` returns `None`; the refresh step falls through to "could not detect pip version, skipping" `[WARN]`; no upgrade; exit 0 | Python unit |
| **T1.8** | `pip show graphifyy` exits non-zero (package hidden) | Inject `runner` returning `CompletedProcess(returncode=1, stdout="", stderr="WARNING: Package(s) not found")` | n/a | `read_pip_version()` returns `None`; treated as "needs upgrade" (we cannot prove the package is current, so refresh) | Python unit |
| **T1.9** | `pip install --upgrade graphifyy` fails (network down) | Inject `runner` returning non-zero on the upgrade call | n/a | Print `[ERROR] pip install --upgrade graphifyy failed (rc=1)`; do NOT run `graphify install`; do NOT update stamp; exit 0 (warn-and-continue) | Python unit |
| **T1.10** | `graphify install --platform opencode` fails (bad platform, write denied) | Inject `runner` returning non-zero on the install call | n/a | Print `[ERROR] graphify install --platform opencode failed (rc=1)`; this is the post-pip step, so pip is already upgraded — write the stamp from `pip show graphifyy` (which we just re-ran in T1.1) so the next install does not redundantly upgrade; exit 0 | Python unit |
| **T1.11** | Combined: pip succeeds but stamp write fails (permission denied on `.config/opencode/skills/graphify/`) | Inject `write_stamp` to raise `PermissionError`; everything else stubbed OK | n/a | Print `[WARN] could not update stamp file: <path>`; exit 0; the pip upgrade and `graphify install` both completed successfully (idempotent next run will try again) | Python unit |

A `.bat`-level analog of T1.7 — "pip not on PATH during real install" —
is impractical to set up in a test (you cannot easily strip pip from
PATH inside a `.bat` that the .bat is using to find python). It is
covered by T1.7 at the unit level only.

---

## 5. Test matrix — flag interactions (3 cases)

| ID | Flag combination | Expected | Type |
|----|------------------|----------|------|
| **T1.12** | `--unattended` + version-mismatch | No prompt fired (no `prompt_fn` call); auto-runs `pip install --upgrade` and `graphify install`; updates stamp | Python unit |
| **T1.13** | `--dry-run` + version-mismatch | `prompt_fn` never called; `pip install --upgrade` never called; `graphify install` never called; stamp not written; stdout contains `[DRY-RUN] would upgrade graphify from 1.2.2 to 1.2.3` | Python unit |
| **T1.14** | `--dry-run` + version-equal | `prompt_fn` never called; no subprocess; stdout contains `[DRY-RUN] would do nothing (already at 1.2.3)` (or just the same `[OK] up to date` line — pick one in ADR-003; recommended: same line as the non-dry-run path for consistency) | Python unit |
| **T1.15** | `--force` + version-mismatch + interactive | `prompt_fn` never called (force skips the prompt); upgrade proceeds; stamp updated | Python unit |
| **T1.16** | `--force` + `--unattended` (or `--force` + `--dry-run`) | `--force` is a no-op when the prompt would not have fired anyway; verify by injecting a `prompt_fn` that would raise if called | Python unit |

> **Why `--force` is NOT irrelevant.** A first reading says "force only
> matters when there's a conflict to force; the refresh step has no
> conflicts." But the existing `.bat` pattern uses `--force` to mean
> "skip confirmation prompts" (see `global-setup.bat` line 16 + the
> `agent.<name>` collision warn-skip in plan-002). The matrix treats
> `--force` the same way: it skips the prompt in interactive mode. This
> keeps the three flags orthogonally meaningful and matches the user's
> existing mental model.

---

## 6. Test matrix — interactive prompt (3 cases)

These tests pass a `prompt_fn=lambda q: <answer>` to the helper. The
helper's contract is: `prompt_fn` is called **only** when all three
of (a) `not unattended`, (b) `not dry_run`, (c) `not force` are true,
AND a version mismatch is detected. The test asserts the answer the
user types maps to the right action.

| ID | User input | Expected | Type |
|----|------------|----------|------|
| **T1.17** | `prompt_fn` returns `"y"` (or `"Y"`) | Upgrade proceeds; `pip install --upgrade` called; `graphify install` called; stamp updated | Python unit |
| **T1.18** | `prompt_fn` returns `"n"` (or `"N"`, or any non-y) | No upgrade; no subprocess; stdout contains `[SKIP] user declined upgrade`; exit 0 | Python unit |
| **T1.19** | `prompt_fn` returns `""` (empty / `<Enter>`) | Default per D3 = **no upgrade**; same as T1.18; `[SKIP] user declined upgrade (default)` | Python unit |

The prompt string itself is asserted in T2.3 (`.bat`-level).

---

## 7. Test matrix — .bat-level integration (5 cases)

These run the actual `.bat` files via PowerShell. They cover the
boundary that the Python unit tests cannot: flag parsing at the .bat
layer, stdout formatting, exit codes, and the `pause` / stdin pipeline.

**Prerequisite:** resurrect `tests/bat_test_helper.py` (was removed in
work-log line 144). The helper is a small function:

```python
def run_bat(bat_path: Path, *, args: list[str], stdin: str = "", env: dict | None = None) -> subprocess.CompletedProcess: ...
```

It invokes `cmd /c "echo <stdin> | <bat> <args>"` from a clean
`tmp_path` working directory and returns `(stdout, stderr, returncode)`.
Each test sets `%USERPROFILE%` to a `tmp_path` clone of the real
`%USERPROFILE%` (just enough to satisfy the `.bat`'s path lookups
without touching the developer's actual home dir).

| ID | Scenario | .bat | Args | stdin | Asserts | Type |
|----|----------|------|------|-------|---------|------|
| **T2.1** | No-op happy path: pip == stamp | `global-setup.bat` | `--unattended` | `""` | stdout contains exactly one `[OK] graphify 1.2.3 up to date` line; exit 0; no `[DRY-RUN]` line; no `pip install` output | .bat integration |
| **T2.2** | Mismatch triggers upgrade | `global-setup.bat` | `--unattended` | `""` | Pre-set stamp to `1.0.0`; ensure `pip show` reports `1.2.3`; stdout contains `[UPGRADE] graphify 1.0.0 -> 1.2.3`; exit 0 (or non-zero if pip cannot reach PyPI in the test env — see T2.2 note) | .bat integration |
| **T2.3** | Interactive prompt fires once, accepts `y` | `global-setup.bat` | (no flags) | `"y\n"` | Pre-set stamp to older version; stdout contains the exact prompt `Upgrade graphify from 1.0.0 to 1.2.3? (y/N):`; followed by `[UPGRADE]` line | .bat integration |
| **T2.4** | Interactive prompt fires once, accepts `n` | `global-setup.bat` | (no flags) | `"n\n"` | Same prompt as T2.3; followed by `[SKIP] user declined upgrade`; pip never called | .bat integration |
| **T2.5** | `--dry-run` short-circuits everything | `setup.bat` | `--dry-run` | `""` | stdout contains `[DRY-RUN] graphify_refresh: would upgrade from 1.0.0 to 1.2.3` (or whatever the architect's chosen format is); no `pip install` output; stamp unchanged | .bat integration |

> **T2.2 caveat:** A real pip install against PyPI in a CI / test
> environment is brittle. The .bat test is allowed to **mock** the
> pip call by setting a fake `pip` on PATH inside the test's `tmp_path`
> that just `echo`s its args. This is a small price for end-to-end
> coverage of the .bat's flag parsing + stdout format. Document this
> mock strategy in the helper's docstring so reviewers know.

The .bat-level tests for `setup.bat` mirror these (5 more cases would
be ideal, but `setup.bat` shares the same helper module, so the
existing 5 cover the boundary for both). If a divergence is found
between the two .bats (e.g., different prompt text, different stamp
path), add a 6th T2.6 mirroring the divergent case for `setup.bat`.

---

## 8. Test file layout

```
tests/
  test_graphify_refresh.py        # NEW: 12 Python unit tests (T1.1 - T1.19 minus 3)
  bat_test_helper.py              # NEW: minimal helper for .bat subprocess runs
  test_bat_refresh.py             # NEW: 5 .bat-level integration tests (T2.1 - T2.5)
```

Python test count: 12 (T1.1 - T1.6, T1.7 - T1.11, T1.12 - T1.16, T1.17 - T1.19) = 19. Trim to 12 by keeping only the highest-value subset; see §9.

> Note: the plan-004 task description said the file would be
> `tests/test_graphify_refresh.py`. The naming is kept exactly as the
> plan specified.

---

## 9. Recommended Python test subset (12 of 19)

The full §3-§6 list is 19 cases. To stay within the 12-20 test budget
the user prompt set, **all 19 are warranted**, but if the test budget
must be trimmed further, drop these 7 in this order (lowest value first):

1. **T1.5** (pip version unparseable) — pure defensive; merge with T1.6
2. **T1.6** (stamp unparseable) — pure defensive; merge with T1.5 into a single `test_handles_unparseable_versions`
3. **T1.11** (stamp write fails) — OS-level; rare in practice
4. **T1.14** (`--dry-run` + version-equal) — covered by T1.13 + the existing T2.5
5. **T1.16** (`--force` + `--unattended`) — degenerate flag combo
6. **T1.19** (`<Enter>` default) — T1.18 covers it
7. **T1.15** (`--force` + interactive + mismatch) — T1.12 covers the same code path

That trims 19 → 12 cleanly. Recommend keeping **all 19** and trimming
elsewhere in the project if budget is tight.

---

## 10. Implementation strategy rationale

**Split:** 12-19 Python unit tests in `tests/test_graphify_refresh.py`
+ 5 .bat-level integration tests in `tests/test_bat_refresh.py`.

**Why this split:**

- **Pure-Python unit tests** cover the entire decision matrix (§3), the
  failure modes (§4), and the flag interactions (§5). All version
  comparisons, stamp I/O, and subprocess orchestration are pure-Python
  and can be tested with `pytest`'s `tmp_path` fixture + injected
  `runner` and `prompt_fn` callbacks — no real `pip` or `graphify`
  invocation required. This is the same pattern plan-002 used for
  `opencode_jsonc_merge.py` (see `tests/test_global_setup.py` — 60
  tests, all pure-Python). Fast feedback, deterministic, no network.

- **.bat-level integration tests** are kept narrow (5 cases) because
  the .bat's only job is to **parse flags + invoke the helper +
  format stdout**. The Python helper is already covered at the unit
  level. The .bat tests only need to prove the flag-parsing, the
  `--unattended` skip, the prompt text, and the `[DRY-RUN]` /
  `[OK]` / `[UPGRADE]` stdout format survive the .bat → Python →
  .bat → stdout round trip. Slow (~3-5s per test), so we keep this
  layer small.

- **No new test class wrappers or fixtures.** Matches the project's
  existing test style — `tests/test_global_setup.py` uses a few
  module-local helper functions (`_project_file`, `_global_file`,
  `_manifest_file`) and otherwise writes straight `test_*(...)`
  functions. Layer 3 @tester should follow the same pattern in
  `tests/test_graphify_refresh.py`.

---

## 11. Open questions for ADR-003

The matrix bakes in assumptions D1-D7 (§2). The architect must lock
these down before Layer 3 writes the tests. Specifically:

1. **D1 — missing stamp behavior.** The matrix assumes "treat as
   needs upgrade" (bootstraps the skill + plugin). If ADR-003 picks
   the alternative, T1.4's assertion flips to `assert not stamp_path.exists()`
   after the call.
2. **D2 — pip older than stamp behavior.** The matrix assumes
   "warn, no upgrade." If ADR-003 picks "upgrade anyway," T1.3's
   assertion flips to the T1.1 path.
3. **D3 — `<Enter>` default.** The matrix assumes "no upgrade."
   The plan-004 verification line 35 already uses the `(y/N)` convention
   in `global-setup.bat` line 52, so this is the most likely decision.
4. **D7 — stamp content source.** The matrix assumes the stamp
   is updated from the **post-upgrade** `pip show graphifyy` output
   (in case `pip install --upgrade` is a no-op for some reason, the
   stamp is still authoritative). The alternative is to take the
   version from `graphify install --platform opencode` (which is
   guaranteed to match the skill file the CLI just wrote).

---

## 12. Cross-references

- Plan: `.opencode/plans/plan-004-auto-refresh-graphify.md`
- Existing test style: `tests/test_global_setup.py` (60 tests,
  `tmp_path` + injected callbacks)
- Existing .bat pattern: `global-setup.bat` (flags at lines 13-21,
  Python resolver at lines 104-119, dep-check at lines 134-156)
- Work-log entry for removed `bat_test_helper.py`: line 144
- `graphify` stale-version check (reference, do not import):
  `graphify/__main__.py:1925`

---

## Summary

24 new tests across two files: 19 pure-Python unit tests (T1.1-T1.19)
covering the version-comparison decision matrix, all 5 failure modes,
the 5 flag interactions, and the 3 interactive-prompt branches; plus
5 .bat-level integration tests (T2.1-T2.5) covering the .bat's flag
parsing, stdout format, and stdin/prompt handling. §9 lists a
recommended 12-test Python subset for a 17-test budget if needed.
The split follows the plan-002 pattern: put the logic in a committed
Python helper, test it in isolation, and keep .bat-level tests narrow
and focused on the .bat boundary. All assumptions that depend on
ADR-003 are flagged in §11 so the test file can be updated in place
once the architect's decision lands.

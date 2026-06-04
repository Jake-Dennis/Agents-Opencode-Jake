# ADR-003: Installers auto-refresh the graphify skill + plugin

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** Jake Dennis (conductor session), @architect
- **Related:** `.opencode/plans/plan-004-auto-refresh-graphify.md`,
  `.opencode/plans/plan-004-design.md` (implementation contract)

## Context and Problem Statement

The official `/graphify` slash command is installed in two pieces:

1. The **pip package** `graphifyy` (import name `graphify`) — pulled
   from PyPI on first install by the existing step 4a in
   `global-setup.bat` and step 2 in `setup.bat`. Idempotent: re-runs
   are no-ops because the import check passes.
2. The **static copies** of the skill file and the opencode plugin:
   - `~/.config/opencode/skills/graphify/SKILL.md` (user-scope
     skill, copy written by `graphify install --platform opencode`)
   - `.opencode/plugins/graphify.js` (project-scope plugin, same)

The static copies are written by
`python -m graphify install --platform opencode`, which is the
upstream-recommended command and is idempotent. Both pieces are
written by the same command, so they always agree on disk. They are
also stamped: the install writes
`~/.config/opencode/skills/graphify/.graphify_version` containing
the version that the static files came from (currently
`0.8.31\n`).

The pain point: when `graphifyy` ships a new release on PyPI, the
pip package auto-updates the next time the user runs `pip install
--upgrade graphifyy` (or via a third-party tool), but the static
skill file and plugin do **not** — they are just files on disk. The
next time the user invokes `/graphify`, the CLI's built-in
stale-version check (line 1925 of `graphify/__main__.py`) compares
the running pip version to the stamp and prints a warning telling
the user to refresh. The user has to read the warning, remember
the magic incantation
(`pip install --user --upgrade graphifyy && python -m graphify
install --platform opencode`), and run it by hand.

In practice the warning is ignored. The result: the user runs on a
mismatched graphify (newer pip code, older static skill) and gets
confusing behaviour when the skill and the package disagree on what
`/graphify` is supposed to do.

We need a way to keep the three artifacts (pip package, user-scope
skill, project-scope plugin) in sync **without** requiring the user
to act on a warning. The installer scripts (`global-setup.bat`,
`setup.bat`) are the user's existing touchpoint — every opencode
project re-runs them on setup, and global-setup is re-run when the
user wants to refresh the global config. Re-running the installer
is the right hook.

## Decision Outcome

Add a new sub-step to each installer — **step 4b** in
`global-setup.bat` and **step 2b** in `setup.bat` — that:

1. Reads the pip-installed version of `graphifyy` via
   `python -m pip show graphifyy` (parsed for the `Version:` line).
2. Reads the installed stamp at
   `~/.config/opencode/skills/graphify/.graphify_version`.
3. If the stamp is missing (first run), or unparseable (corrupted
   stamp), or strictly older than the pip version, the step runs
   the official refresh sequence:
   ```
   python -m pip install --user --upgrade graphifyy
   python -m graphify install --platform opencode
   ```
   The second command is idempotent and rewrites both the
   user-scope skill file and the project-scope plugin in one
   call, plus the stamp.
4. If pip equals stamp, the step is a single
   ` [OK] graphify X.Y.Z up to date` line — zero subprocess
   output, zero disk writes.
5. If pip cannot be read (python missing, pip not installed,
   `pip show` failing), the step warns and continues. The
   remainder of the install still completes.

The step honours the existing `--unattended` (auto-upgrade, no
prompt), `--dry-run` (print what would happen, do not execute),
and `--force` (auto-upgrade, no prompt -- mapped to `--yes`)
flags. The `--force → --yes` mapping is intentional and matches
the existing semantics of `--force` elsewhere in the installer
("skip confirmation prompts / overwrite on conflict"). This is
verified by test T1.15.

The interactive prompt when pip > stamp and no flags are set is
`graphify A.B.C installed, pip has X.Y.Z. Refresh? (Y/n): ` with
**default Y** (Enter accepts). Rationale: the whole point is
auto-refresh; pressing Enter is the dominant case. The
`[SKIP] graphify not upgraded` escape hatch is the `n` reply.

The full implementation contract — exact parsing code, comparison
logic, output strings, failure-mode handling — is in
`.opencode/plans/plan-004-design.md`. This ADR is the rationale
and the alternatives record; the design doc is the builder's
contract.

## Why the comparison is `pip >= stamp` (not `pip == stamp`)

If a user has a beta or pre-release stamp (e.g. they ran
`pip install --pre graphifyy` once) and a stable pip release
subsequently shipped, the stamp will be a pre-release version like
`0.10.0a1` and the pip version will be `0.10.0`. Treating them
as "equal" would leave the user on a stale pre-release forever;
treating them as `pip > stamp` correctly triggers the refresh.

The Python one-liner in the design doc strips the pre-release
suffix with `re.match(r'(\d+)\.(\d+)\.(\d+)', v)` so the
comparison is on `(major, minor, patch)` tuples of integers, not
on lexicographic strings. This is the only robust way to handle
the `0.9.x → 0.10.x` transition (string compare gives the wrong
answer there: `"0.9.0" gtr "0.10.0"` is true, which is wrong).

## Consequences

### Positive

* **The three graphify artifacts stay in sync** without the user
  having to read a warning. The `pip show` → `graphify install`
  pairing runs on every installer re-run, so a `graphifyy` PyPI
  release is picked up the next time the user runs the installer.
* **Idempotent.** Re-running on a clean install is a one-line
  `[OK]` and zero subprocess output. Re-running on a network
  failure leaves the stamp unchanged so the next run can retry
  (the stamp is only written by `graphify install --platform
  opencode`, not by us).
* **No new dependencies.** Python is already a hard prerequisite
  (step 1 of `setup.bat`, step 4a of `global-setup.bat`). `pip` is
  part of the Python install. `graphify` is already installed
  (the whole point of this step is to refresh it). No
  third-party tooling, no scheduled tasks, no registry entries.
* **Failure-tolerant.** Every failure mode is "warn + continue",
  not "exit". A broken `pip show` does not abort the opencode
  install. The user can re-run the .bat to retry.
* **Honours the user's existing flag contract.** `--unattended`
  and `--dry-run` work the same way here as they do in the
  rest of the installer. `--force` is mapped to `--yes` (auto-
  upgrade, no prompt) for the same reason `--force` exists
  elsewhere in the installer: it means "skip confirmation
  prompts / overwrite on conflict". This is verified by
  test T1.15.
* **Stampless case is handled.** First run, or any case where
  `graphify install --platform opencode` was never executed
  successfully, triggers the refresh. We do not silently skip
  on a missing stamp.

### Negative

* **More code in the .bat files.** The new step is ~70 lines of
  inline .bat per file. The two .bat files now duplicate this
  logic (just like the graphify import check in step 4a is
  duplicated). The duplication is small enough to be cheaper
  than the alternative (extract a `.bat` helper and `call` it
  from both), but a future maintainer could factor it out.
* **No unit tests for the .bat itself.** `tests/` exercises the
  Python merge helper, not the .bat files. The new step will
  only be covered by static review (`@reviewer`). The version-
  compare logic is small enough that this is acceptable, but a
  `tests/bat_test_helper.py` would be a better long-term
  investment. Logged as an open question in the design doc.
* **Brittle to stamp format drift.** The stamp is currently
  `X.Y.Z\n`. If the upstream changes the stamp format (e.g.
  `0.8.31+local.foo` or a JSON dict with metadata), our regex
  would treat the new stamp as unparseable and trigger a refresh
  on every run. That is a safe degradation (refresh is
  idempotent) but is wasted work. We accept this for plan-004
  and note that a future version check can verify the
  upstream's stamp contract.
* **Assumes `graphify install --platform opencode` only touches
  the skill dir and the plugin file.** The official command is
  documented to do exactly that and nothing else; we rely on
  that. If upstream ever changes the command to also write to
  `opencode.jsonc`, this step would race the merge helper. The
  merge helper runs *after* step 4b and would clobber any
  `opencode.jsonc` changes. We accept this dependency on
  upstream's contract; if it ever changes, we revisit.
* **No notification when an upgrade is actually applied.** The
  user sees `[UPGRADE] pip graphifyy upgraded to 0.8.31` and
  `[REFRESH] graphify skill + plugin refreshed to 0.8.31` in
  the .bat output, but a `opencode` session already in progress
  does not pick up the new skill file until it restarts. This
  is acceptable — the user has to restart `opencode` after a
  pip upgrade anyway, since the running session holds the old
  Python module in memory.

### Reversibility

The change is two .bat files. Reverting is a `git revert` (or
deleting the new blocks). The step is additive — removing it
returns the codebase to the "user has to act on the CLI warning"
status quo, with no other behavioural changes.

## Alternatives Considered

1. **Do nothing.** The user manually runs
   `pip install --user --upgrade graphifyy && python -m graphify
   install --platform opencode` after seeing the CLI's stale-
   version warning.
   *Rejected:* the warning is ignored in practice; the user runs
   on mismatched artifacts; the issue will recur every time
   `graphifyy` ships a release. The whole point of this ADR is
   to eliminate the manual step.

2. **A scheduled task / Windows Task Scheduler hook that runs
   `graphify install` weekly.** This is a permanent system
   change — not what the user opted into — and runs without
   their awareness. It also requires admin to register.
   *Rejected:* out of proportion to a knowledge-graph tool. The
   .bat step is the user's existing touchpoint; reusing it
   costs zero new infrastructure. Logged as "out of scope" in
   plan-004.

3. **Move the version check into the opencode CLI itself, so
   it runs on `/graphify` invocation.** The CLI's built-in
   stale-version check already does this — it warns on every
   invocation. The problem is the warning is silent until the
   user looks. Moving the check into the opencode core is the
   upstream maintainer's call, not ours.
   *Rejected:* we cannot modify the opencode CLI; we can only
   modify the installer.

4. **Add a `/graphify-refresh` slash command that the user
   invokes.** This is a UI improvement on top of the existing
   warning, but it still requires the user to know to invoke
   it.
   *Rejected:* the user already runs the installer on setup;
   re-running the installer is the natural cadence. Adding a
   second command the user has to remember is worse UX than
   the warning they already ignore.

5. **Extract the version-check + upgrade logic into a
   standalone `.bat` helper file (e.g.
   `.opencode\scripts\refresh_graphify.bat`) and `call` it
   from both installers.** This avoids duplicating the ~70
   lines of new .bat code.
   *Rejected for plan-004, accepted as a possible future
   refactor:* the duplication is small and the inline pattern
   matches the existing step 4a / step 2 graphify import
   check, which is also duplicated. The cost of `call`-ing a
   helper is a separate file in the repo, an extra
   error-handling branch (what if the helper is missing?), and
   a second point of failure during install. The builder can
   refactor in a follow-up if the duplication feels heavy.

6. **Extract the logic into a Python helper (`refresh_graphify.py`)
   and unit-test it.** The .bat becomes a thin wrapper that
   shells out to the helper. This is the most testable option
   and matches the existing `.opencode/scripts/opencode_jsonc_merge.py`
   pattern.
   *Rejected for plan-004:* the version-compare logic is ~10
   lines of Python; the pip + graphify-invocation logic is
   already exercised by the upstream package. A wrapper file
   would be mostly orchestration of subprocess calls, which is
   not where the test value is. Logged as an open question in
   the design doc; the @tester can build it if they want to
   write .bat-level integration tests.

7. **Use `uv tool install` instead of `pip install --user`.** This
   is a different package manager and changes the install path.
   *Rejected:* the user's current `pip --user` setup works and
   the plan-004 out-of-scope list already defers this to a
   separate decision.

## Pros and Cons of the Options (re-listed for the record)

### Chosen: new sub-step in each .bat, inline

* Good: reuses the user's existing touchpoint; no new
  infrastructure; failure-tolerant; honours `--unattended` /
  `--dry-run`; idempotent.
* Good: matches the existing inline .bat style (step 4a is
  inline, not a Python helper).
* Bad: ~70 lines of new .bat per file, duplicated.
* Bad: no unit tests for the .bat itself.

### Alternative: Python helper + .bat wrapper

* Good: unit-testable; matches the merge-helper pattern.
* Bad: adds a new file for ~10 lines of actual logic.
* Bad: the subprocess orchestration is not where the bugs
  would be (the upstream `graphify install` is well-tested).
* Bad: another moving part in the install chain.

### Alternative: Scheduled task

* Good: fully hands-off; no user action.
* Bad: permanent system change; admin required; runs without
  awareness.
* Bad: out of proportion to the problem.

### Alternative: Do nothing

* Good: zero new code; zero new risk.
* Bad: the existing warning is ignored; users run on
  mismatched artifacts; the problem recurs.

## References

* `graphify/__main__.py` line 1925 — the upstream's built-in
  stale-version check.
* `~/.config/opencode/skills/graphify/SKILL.md` — the user-scope
  skill file written by `graphify install --platform opencode`.
* `~/.config/opencode/skills/graphify/.graphify_version` — the
  version stamp, single text line, currently `0.8.31\n`.
* `.opencode/plugins/graphify.js` — the project-scope plugin,
  also written by `graphify install --platform opencode`.
* `.opencode/plans/plan-004-auto-refresh-graphify.md` — the
  plan that motivated this ADR.
* `.opencode/plans/plan-004-design.md` — the implementation
  contract the @builder follows.
* `global-setup.bat` lines 134–156 — the existing step 4a
  graphify import check that step 4b slots in next to.
* `setup.bat` lines 43–61 — the existing step 2 dependency
  check that step 2b slots in next to.
* `.opencode/decisions/adr-002-global-setup-merge-strategy.md`
  — the previous ADR; this ADR is in the same family (about
  the installer scripts).
# Plan 004: Auto-refresh graphify skill + plugin in installers

## Goal
Add a "check + auto-refresh" step to `global-setup.bat` and `setup.bat` so re-running the normal installer keeps the `graphify` pip package, the user-scope skill file at `~/.config/opencode/skills/graphify/SKILL.md`, and the project-scope plugin at `.opencode/plugins/graphify.js` up to date — without requiring the user to remember the manual `pip install --upgrade graphifyy && python -m graphify install --platform opencode` sequence.

## Context
- The official `/graphify` slash command was installed via `python -m graphify install --platform opencode` (commit 8539809). The skill file and plugin are static copies from the pip package; new graphify versions do not propagate automatically.
- The CLI's built-in stale-version check (line 1925 of `graphify/__main__.py`) compares the pip version to the stamp at `~/.config/opencode/skills/graphify/.graphify_version` and warns on every invocation, but the user has to act on the warning.
- Both .bat files already have a graphify dep-install step (commit a010f1b, step 4a in `global-setup.bat` and step 2 in `setup.bat`). The new step slots in directly after that.
- `graphify install --platform opencode` is idempotent and refreshes BOTH user-scope skill and project-scope plugin in one call.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] **@architect** — design the version-check + auto-refresh step. Decide: where it slots in, what command to run for the version check, what the interactive prompt looks like, how `--unattended` / `--dry-run` / `--force` interact, and how to handle failures (pip not on PATH, pip command fails, network down during install, version parse failure). Output a 1-page design doc + an ADR. (assigned: @architect)
- [ ] **@tester** — design the test matrix. Cover at minimum: pip newer than stamp, equal, older (defensive), missing stamp (first install), pip not on PATH, pip command fails, network down during upgrade, interactive `y` / `n` / `<Enter>`, `--unattended` no-prompt, `--dry-run` no-write. Output: list of test cases + which .bat each applies to. (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] **@builder** — implement the new step in `global-setup.bat` (after step 4a, renumber to step 4b). Honor all design-doc decisions. (assigned: @builder, depends on @architect + @tester)
- [ ] **@builder** — implement the same step in `setup.bat` (after step 2, renumber to step 3 if step 2 becomes 2b). (assigned: @builder, depends on @architect + @tester)

### Layer 3 (depends on Layer 2)
- [ ] **@tester** — write the actual test cases (Python helper functions for the new step, plus .bat-level integration tests using the existing `bat_test_helper.py` pattern). (assigned: @tester, depends on @builder)
- [ ] **@docs** — update `README.md` and `examples/integrate-into-your-project.md` to document the new "auto-refresh on installer re-run" behavior. One paragraph + a "to force-refresh manually" callout. (assigned: @docs, depends on @builder)

### Layer 4 (depends on Layer 3)
- [ ] **@reviewer** — review the .bat changes for correctness, idempotency, error handling, and consistency with the existing flag-handling pattern. (assigned: @reviewer, depends on @builder + @tester)
- [ ] **@git** — commit the implementation + tests + docs in a single conventional commit. Move this plan to `.opencode/plans/completed/`. (assigned: @git, depends on @reviewer + @docs)

## Verification

Static + dynamic checks (run from the repo root, exit 0 = pass):

- [x] **#1** `.opencode/scripts/graphify_refresh.py` — file exists
- [x] **#2** `python -c "import ast; ast.parse(open('.opencode/scripts/graphify_refresh.py', encoding='utf-8').read())"` — helper parses
- [x] **#3** `python -c "import ast; ast.parse(open('tests/test_graphify_refresh.py', encoding='utf-8').read())"` — new test file parses
- [x] **#4** `python -c "from pathlib import Path; t = Path('.opencode/scripts/graphify_refresh.py').read_text(encoding='utf-8'); assert 'parse_version' in t; assert 'compare_versions' in t; assert 'read_pip_version' in t; assert 'read_stamp' in t; assert '_run_pip_upgrade' in t; assert '_run_graphify_install' in t; assert 'runner' in t; assert 'prompt_fn' in t; print('OK')"` — helper has the testable seams called for by the matrix
- [x] **#5** `python -c "from pathlib import Path; t = Path('global-setup.bat').read_text(encoding='utf-8'); assert '[4b/5] Checking graphify version' in t; assert 'graphify_refresh.py' in t; print('OK')"` — step 4b lives in global-setup.bat and calls the helper
- [x] **#6** `python -c "from pathlib import Path; t = Path('setup.bat').read_text(encoding='utf-8'); assert '[2b/7] Checking graphify version' in t; assert 'graphify_refresh.py' in t; print('OK')"` — step 2b lives in setup.bat and calls the helper
- [x] **#7** `python -c "from pathlib import Path; t = Path('global-setup.bat').read_text(encoding='utf-8'); assert '[1/5]' in t and '[2/5]' in t and '[3/5]' in t and '[4a/5]' in t and '[4b/5]' in t and '[5/5]' in t; print('OK')"` — step numbering preserved ([1/5]..[5/5], with 4a+4b)
- [x] **#8** `python -c "from pathlib import Path; t = Path('setup.bat').read_text(encoding='utf-8'); assert '[1/7]' in t and '[2/7]' in t and '[2b/7]' in t and '[3/7]' in t; print('OK')"` — step numbering preserved in setup.bat
- [x] **#9** `python -m pytest tests/test_graphify_refresh.py -v` — all 19+ new tests pass
- [x] **#10** `python -m pytest tests/test_global_setup.py -q` — existing 60 tests still pass
- [x] **#11** `python -c "import json, subprocess; r = subprocess.run(['python','-m','pytest','tests/test_graphify_refresh.py','tests/test_global_setup.py','-q'], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr; print('OK')"` — new + old pass together
- [x] **#12** `.opencode/decisions/adr-003-graphify-auto-refresh.md` — file exists
- [x] **#13** `python -c "from pathlib import Path; t = Path('README.md').read_text(encoding='utf-8').lower(); assert 'auto-refresh' in t or 'auto refresh' in t; assert 're-running' in t or 'rerun' in t; assert 'graphify' in t; print('OK')"` — README documents the new behavior
- [x] **#14** `python -c "from pathlib import Path; t = Path('examples/integrate-into-your-project.md').read_text(encoding='utf-8').lower(); assert 'auto-refresh' in t or 'auto refresh' in t; assert 're-running' in t or 'rerun' in t; print('OK')"` — example doc documents the new behavior

Live-state checks (run on the user's real machine):

- [ ] **#15** Conductor — `python .opencode\scripts\graphify_refresh.py --help` — argparse shows all 5 flags
- [ ] **#16** Conductor — `python -c "from pathlib import Path; sp = Path.home() / '.config' / 'opencode' / 'skills' / 'graphify' / '.graphify_version'; print('stamp:', sp.read_text().strip() if sp.exists() else 'MISSING')"` — stamp file exists at user-scope (set by prior `graphify install --platform opencode`)
- [ ] **#17** Conductor — `powershell -NoProfile -Command "\" \" | & '.\global-setup.bat' --unattended"` from the repo root: confirm the new step prints `[4b/5] Checking graphify version...` followed by ` [OK] graphify X.Y.Z up to date` (matches the live pip version) and exits 0. This is the idempotency / no-upgrade-needed path.
- [ ] **#18** Conductor — `powershell -NoProfile -Command "\" \" | & '.\global-setup.bat' --unattended --dry-run"` from the repo root: confirm the step prints a `[DRY-RUN] would upgrade graphify from ...` line (or the no-op equivalent when versions match) and does not invoke `pip` or `graphify install`. Capture and inspect stdout.
- [ ] **#19** Conductor — overwrite the stamp with a fake-older version (`python -c "from pathlib import Path; p = Path.home() / '.config' / 'opencode' / 'skills' / 'graphify' / '.graphify_version'; p.write_text('0.0.1')"`), re-run the install via `powershell -NoProfile -Command "\" \" | & '.\global-setup.bat' --unattended"`, confirm the upgrade path fires and the stamp is updated to the real pip version afterwards. This is the "stale stamp → upgrade" path.
- [ ] **#20** Conductor — `python -c "import sys; sys.path.insert(0, '.opencode/scripts'); from opencode_jsonc_merge import load_jsonc; cfg = load_jsonc(r'%USERPROFILE%\.config\opencode\opencode.jsonc'); assert len(cfg.get('agent', {})) == 13; assert 'build' in cfg.get('command', {}); print('OK')"` — pre-existing global state preserved (no regressions on the merge helper).

## Out of scope
- Auto-upgrade via a scheduled task / Windows hook (the .bat-step is the user's existing touchpoint; adding a scheduled task is a permanent system change and out of proportion to a knowledge-graph tool).
- Switching from `pip install --user` to `uv tool install` (the user's current `pip --user` setup works; changing it is a separate decision).
- Adding a "check for updates" command to the opencode slash menu (the version check fires only on installer re-run, which is the deliberate scope).

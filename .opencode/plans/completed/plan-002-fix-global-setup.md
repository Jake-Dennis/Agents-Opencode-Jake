# Plan 002: Fix global-setup.bat to actually install agents + skills

## Goal
Patch `global-setup.bat` + `uninstall-global.bat` so a successful run
produces a working global opencode install. Today the installer appears to
succeed but installs an empty agents directory (because agents live in
`opencode.json`, per ADR-001), and the existing global `opencode.jsonc` is
not actually merged — only a "NOTE" is printed.

## Background (from static review + subagent reports)

| Path | Status today |
|---|---|
| `…\agents\Agents-Opencode-Jake` (global) | Junction → empty `.opencode\agents\` |
| `…\skills\graphify-agent-workflow` (global) | MISSING |
| `…\opencode.jsonc` (global) | Exists, only contains `$schema` |
| `.opencode\agents\` (repo) | Empty by design (ADR-001) |
| `opencode.json` (repo) | Source of truth for 13 agents |

3 failure modes the refactor must fix:
1. Empty-source junction (`mklink` succeeds, but junction points at nothing).
2. Skill junction missing on this machine.
3. No actual JSONC merge — just a `NOTE` for existing `opencode.jsonc`.

## Architecture (from @architect)

- **Split the .bat from the merge logic.** The Python helper is committed at
  `.opencode/scripts/opencode_jsonc_merge.py` (not inlined as `python -c "..."`
  — quoting hell, and un-testable). The .bat invokes it as
  `python .opencode\scripts\opencode_jsonc_merge.py install|remove ...`.
- **Idempotent merge** with per-key policy (architect's full table below).
- **Manifest file** at `%USERPROFILE%\.config\opencode\.opencode-jake-installed.json`
  records what was added, so `uninstall-global.bat` can surgically remove it
  without clobbering the user's other agents.
- **JSONC tolerance**: helper strips `//` and `/* */` comments and trailing
  commas before `json.loads`.
- **Python resolver**: try `python`, then `py -3`. Skip `python3` (MS Store
  stub on this machine).
- **`--unattended` / `--dry-run` / `--force` flags** for both install and
  uninstall, also via env vars `GLOBAL_SETUP_YES=1`, `GLOBAL_SETUP_DRY_RUN=1`,
  `GLOBAL_SETUP_FORCE=1`.

### Per-key merge policy

| Key | Strategy | On collision |
|---|---|---|
| `default_agent`, `model`, `small_model` | overwrite | silently wins (project is authoritative) |
| `skills.paths` | union + dedupe (case-insensitive) | both kept |
| `instructions` | union + dedupe (case-insensitive) | both kept |
| `agent.<name>` | deep-merge, warn + skip | `--force` to overwrite |
| `$schema`, `enabled_providers`, `provider`, `mcp`, `command`, `permission` | never touch | preserved as-is |

## Tasks

### Layer 1 (parallel, no deps) — design + audit ✅ DONE
- [x] **#1** @architect — Designed JSONC merge strategy (see Architecture)
- [x] **#2** @explorer — Audited 10 files needing changes (see Deliverables)

### Layer 2 (depends on L1) — implementation
- [ ] **#3** @builder — Create `.opencode/scripts/opencode_jsonc_merge.py`
  (the Python helper, stdlib only, ~200 lines):
  - `argparse` with `install|remove` mode, `--project`, `--global`,
    `--manifest`, `--force`, `--dry-run` flags
  - `load_jsonc(p)` — strips comments + trailing commas, then `json.loads`
  - `atomic_write(path, data, header)` — write `.tmp` then `os.replace`
  - `dedupe_union(a, b)` — case-insensitive, preserve order
  - `deep_merge(a, b)` — recursive dict merge
  - `cmd_install(args)` — runs the merge per the policy table, writes
    the manifest, prints a summary
  - `cmd_remove(args)` — uses manifest to surgically remove merged keys
  - Exit codes: 0 ok, 2 bad args, 3 parse fail, 4 perm denied, 5 collision
- [ ] **#4** @builder — Rewrite `global-setup.bat` (~190 lines):
  - Parse flags `--unattended`, `--dry-run`, `--force` (and env-var equivalents)
  - Resolve Python: try `python`, then `py -3`, skip `python3`
  - Probe `.opencode\agents\*.md` count; if > 0 do legacy junction; if
    == 0 AND project has `opencode.json` with `agent` key, skip junction
    and run merge; if neither, abort
  - Skill junction with idempotency check (`fsutil reparsepoint query`)
  - Invoke helper: `python .opencode\scripts\opencode_jsonc_merge.py install ...`
  - On Python missing: fall back to a `findstr` patcher that handles only
    the 3 scalar keys, with `[WARN]` message
  - Final summary: junction targets, manifest path, agent count
- [ ] **#5** @builder — Rewrite `uninstall-global.bat` (~180 lines):
  - Same flag handling as installer
  - Read manifest. If present: call helper in `remove` mode. If missing:
    print legacy "edit by hand" guidance, do NOT offer to delete file.
  - Remove junctions only if target matches manifest's recorded target
  - After successful remove: `del` the manifest
- [ ] **#6** @builder — Create `.opencode/decisions/adr-002-global-setup-merge-strategy.md`:
  - Context, decision, consequences, alternatives
  - Link to plan 002 and architect design

### Layer 3 (depends on L2) — verify + test
- [ ] **#7** @tester — Create `tests/test_global_setup.py` (unit tests for
  the merge helper, no real user config touched):
  - `test_load_jsonc_handles_comments_and_trailing_commas`
  - `test_install_merges_scalar_keys` (overwrites default_agent, model,
    small_model)
  - `test_install_unions_skills_paths_idempotent` (run twice, no dupes)
  - `test_install_unions_instructions_and_adds_repo_agents_md`
  - `test_install_deep_merges_agent_block_warns_on_collision`
  - `test_install_with_force_overwrites_agents`
  - `test_remove_surgically_drops_merged_keys_preserves_user_agents`
  - `test_atomic_write_creates_tmp_and_replaces`
  - All tests use `tmp_path` fixture, no real global config
- [ ] **#8** @tester — Fix the mislabeled assertion block in
  `tests/test_integration.py:186-205` (it currently reads `setup.bat` but
  asserts global-setup strings). Either point it at `global-setup.bat` or
  delete it if `test_setup.py` covers it.
- [ ] **#9** @tester — Update `tests/test_setup.py`:
  - Lines 152-153: keep `.config\opencode` + `mklink` assertions (they
    still pass after refactor — `mklink` stays in skill step).
  - Line 160: keep `AGENTS_DIR` assertion.
  - Add new assertion: `python -c "import ast; ast.parse(open('.opencode/scripts/opencode_jsonc_merge.py').read())"`
- [ ] **#10** @docs — Update `README.md` lines 38, 40 and
  `examples/integrate-into-your-project.md` lines 8, 14, 12-16 to reflect
  the new merge-into-`opencode.jsonc` behavior.

### Layer 4 (depends on L3) — review
- [ ] **#11** @reviewer — Review all changes:
  - Correctness of JSONC merge (comments, trailing commas, BOM)
  - Idempotency (run twice → identical output)
  - Error paths (Python missing, perms denied, malformed jsonc, missing
    manifest on uninstall)
  - Backwards compatibility (legacy `.opencode\agents\*.md` path still
    works for projects that haven't migrated to JSON-only)
  - No regressions in `test_setup.py`, `test_agents_v2.py`,
    `test_integration.py`, `test_conductor_workflow.py`,
    `test_agents_runtime.py`, `test_schema.py`
  - All 13 agents survive the round-trip
  - Run `python -m pytest tests/ -v` to confirm

### Layer 5 (depends on L4) — live run
- [ ] **#12** Conductor — Run patched `global-setup.bat --unattended`
  non-interactively, then verify:
  - Skill junction created and points to right target
  - Global `opencode.jsonc` has `agent` (13 names), `skills.paths`,
    `instructions`, `default_agent`, `model`, `small_model`
  - Manifest file written
  - `opencode agent list` exits 0 and shows all 13 agents
- [ ] **#13** Conductor — Re-run `global-setup.bat --unattended` to
  confirm idempotency (no duplicates, no clobbered user agents)
- [ ] **#14** Conductor — Run `uninstall-global.bat --unattended` and
  verify global config no longer has the merged keys but user's other
  customizations are preserved

## Deliverables
- `.opencode/scripts/opencode_jsonc_merge.py` (new)
- `global-setup.bat` (rewritten)
- `uninstall-global.bat` (rewritten)
- `.opencode/decisions/adr-002-global-setup-merge-strategy.md` (new)
- `tests/test_global_setup.py` (new)
- `tests/test_integration.py` (mislabeled block fixed)
- `tests/test_setup.py` (1 new assertion)
- `README.md` (script table updated)
- `examples/integrate-into-your-project.md` (lines 8, 14, 12-16 updated)
- This plan archived to `.opencode/plans/completed/`

## Verification
Static checks (run any time):
- [ ] #1 — `.opencode/decisions/adr-002-global-setup-merge-strategy.md` (file exists)
- [ ] #2 — `python -c "from pathlib import Path; t = Path('global-setup.bat').read_text(encoding='utf-8', errors='ignore') + Path('uninstall-global.bat').read_text(encoding='utf-8', errors='ignore'); assert 'mklink' in t; assert 'opencode.jsonc' in t; print('OK')"`
- [ ] #3 — `.opencode/scripts/opencode_jsonc_merge.py` (file exists)
- [ ] #4 — `python -c "import ast; ast.parse(open('.opencode/scripts/opencode_jsonc_merge.py', encoding='utf-8').read())"`
- [ ] #5 — `python -m pytest tests/test_global_setup.py -v` exits 0 (30 tests, all in-scope)
- [ ] #6 — `python -c "import ast; ast.parse(open('tests/test_global_setup.py', encoding='utf-8').read())"`
- [ ] #7 — `python -c "import ast; ast.parse(open('tests/test_integration.py', encoding='utf-8').read())"` (note: test_setup.py is a pre-existing script-style runner; it reports "All checks passed!" when run directly via `python tests/test_setup.py`)
- [ ] #8 — `python -c "from pathlib import Path; p = Path('README.md'); assert 'merge' in p.read_text().lower() or 'symlink' in p.read_text().lower(); print('OK')"` (sanity, doc updated)
- [ ] #9 — `python -c "from pathlib import Path; p = Path('examples/integrate-into-your-project.md'); assert 'merge' in p.read_text().lower() or 'jsonc' in p.read_text().lower(); print('OK')"`
- [ ] #10 — `python -c "from pathlib import Path; p = Path('tests/test_setup.py'); src = p.read_text(encoding='utf-8', errors='ignore'); assert 'ast.parse' in src; print('OK')"` (helper-parses assertion added per L3)

Live-state checks (final state: uninstalled; verified manually during dev — see work-log 2026-06-04):
- [x] Install state (post-`global-setup.bat`): 13 agents + 2 skills.paths + 1 instruction merged; manifest written; `opencode agent list` shows all 13. See work-log 2026-06-04 Layer 5.
- [x] Idempotent re-install: re-run produced no duplicates. See work-log 2026-06-04 Layer 5.
- [x] Uninstall state (final): empty agent block, empty skills.paths, empty instructions, scalars preserved. Verified by re-running `uninstall-global.bat` end-to-end after the .bat bug fixes.
- [x] End-to-end install + uninstall cycle via .bat: works clean (no manifest left, junctions removed). See work-log 2026-06-04.

Final-state gate (current state should be uninstalled per user option 4):
- [ ] #11 — Final state check: `python -c "import sys, os; sys.path.insert(0, '.opencode/scripts'); from opencode_jsonc_merge import load_jsonc; from pathlib import Path; cfg = load_jsonc(Path(os.environ['USERPROFILE']) / '.config' / 'opencode' / 'opencode.jsonc'); assert cfg.get('agent', {}) == {}; assert cfg.get('skills', {}).get('paths', []) == []; assert cfg.get('instructions', []) == []; assert cfg.get('default_agent') == 'conductor'; print('OK')"`

## Risks
- Pre-commit hook doesn't lint `.bat` syntax; rely on `tests/test_setup.py`
  grep checks + a new `import ast` check on the Python helper.
- `opencode` CLI may not honor `agent` block in global `opencode.jsonc`. The
  runtime test in #12 (counting 13 agents) is the ground truth. If it
  fails, fall back to per-project-only merge (out of scope for this plan).
- Manifest can drift if user edits global jsonc between install/uninstall.
  The remove path uses filter-and-skip semantics to handle this gracefully.

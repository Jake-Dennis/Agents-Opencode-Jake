# Plan 014: Full Project Improvements (22 items)

## Goal

Execute all 22 improvement items identified in the June 8 audit. These span test fixes, documentation, configuration hardening, CI setup, and architecture improvements.

## Tasks

### Layer 1 (parallel, no deps) — ALL COMPLETED

- [x] @docs #1: ADR for path-scoped permission pattern
- [x] @docs #2: ADR for 3-file ownership split
- [x] @docs #3: File upstream bug reports (bun segfault + opencode models crash)
- [x] @builder #4: Migrate git agent bash glob to path-scoped pattern
- [x] @builder #5: Add `disabled_providers` to lock to `opencode` only
- [x] @docs #6: Add `--dry-run` flag description to `/build` command

### Layer 2 (parallel, no deps on each other) — ALL COMPLETED

- [x] @tester @builder #7: Fix 5 pre-existing test failures (all 198/198 passing)
- [x] @tester #8: Add `setup-project` smoke test
- [x] @architect #9: Create `.opencode/jobs.md` archival/rotation rule
- [x] @docs #10: Create Contributing guide `CONTRIBUTING.md`
- [x] @docs #11: Update AGENTS.md with model inheritance docs
- [x] @debugger #12: Fix pre-commit hook hang on Windows

### Layer 3

- [ ] @builder #13: Implement `.opencode/jobs.md` archival rotation (depends on #9, deferred)
- [ ] @builder #14: Add git hook for `.opencode/jobs.md` linting (depends on #9, deferred)
- [x] @tester #15: Verify path-scoped `edit` glob syntax at runtime (T-AS-16)

### Layer 4

- [ ] @builder #16: Add `variant` field to agent configs (deferred)
- [ ] @architect @builder #17: Add per-agent `fallback_model` (deferred)
- [ ] @builder #18: Add GitHub Actions CI workflow (deferred)
- [ ] @tester #19: Add `.bat` execution tests to CI (depends on #18, deferred)

### Layer 5

- [ ] @architect #20: TUI render of `.opencode/jobs.md` (research, deferred)
- [ ] @tester #21: Mutation testing setup (deferred)
- [ ] @tester #22: Property-based tests for verify-plan.py (deferred)

## Verification

- [x] #1: `python -c "import pathlib; assert pathlib.Path('.opencode/decisions/adr-005-path-scoped-permission.md').exists(); print('OK')"`
- [x] #2: `python -c "import pathlib; assert pathlib.Path('.opencode/decisions/adr-006-three-file-ownership-split.md').exists(); print('OK')"`
- [x] #4: `python -c "import json; c=json.load(open('opencode.json')); b=c['agent']['git']['permission']['bash']; assert isinstance(b, dict); assert '*' in b; print('OK:', b)"`
- [x] #5: `python -c "import json; c=json.load(open('opencode.json')); assert 'disabled_providers' in c; assert len(c['disabled_providers']) > 0; print('OK:', len(c['disabled_providers']), 'providers')"`
- [x] #6: `python -c "assert 'dry-run' in open('.opencode/commands/build.md').read(); print('OK')"`
- [x] #7: `python -c "import subprocess; r=subprocess.run(['python','-m','pytest','tests/','--tb=no','-q'],capture_output=True,text=True); print(r.stdout.splitlines()[-1] if r.stdout else r.stderr.splitlines()[-1]); exit(r.returncode)"`
- [x] #8: `python -c "import pathlib; assert pathlib.Path('tests/test_smoke.py').exists(); print('OK')"`
- [x] #9: `python -c "import pathlib; assert pathlib.Path('.opencode/plans/plan-014-archival-rotation-design.md').exists(); print('OK')"`
- [x] #10: `python -c "import pathlib; p=pathlib.Path('CONTRIBUTING.md'); assert p.exists(); assert '### 1' in p.read_text(); print('OK')"`
- [x] #11: `python -c "assert 'Model inheritance' in open('AGENTS.md').read(); print('OK')"`
- [x] #12: `python -c "p=open('scripts/pre-commit').read(); assert 'TIMEOUT_CMD' in p; assert 'IS_WINDOWS' in p; print('OK')"`
- [x] #15: `python -m pytest tests/test_agent_safety.py::test_T_AS_16_path_scoped_permission_keys_are_valid -q 2>&1 | findstr /C:"passed"`

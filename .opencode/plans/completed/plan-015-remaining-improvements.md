# Plan 015: Remaining Improvements (items #13-#22)

## Goal

Complete all 7 remaining improvement items from the full audit that were deferred in plan-014: config hardening, CI, archival rotation, mutation/property testing.

## Tasks

### Layer 1 (parallel, no deps) — ALL COMPLETED
- [x] @builder #13: Implement `scripts/archive-jobs.py` for jobs.md archival rotation
- [x] @builder #16: Add `variant` field to all 13 agents in `opencode.json`
- [x] @builder #17: Add `fallback_model` field to all 13 agents in `opencode.json`
- [x] @builder #18: Create `.github/workflows/ci.yml` CI workflow
- [x] @architect #20: TUI render research document for `.opencode/jobs.md`
- [x] @tester #21: Mutation testing setup (config + smoke test)
- [x] @tester #22: Hypothesis property-based tests for `scripts/verify-plan.py`

### Layer 2 — ALL COMPLETED
- [x] @tester #19: Add `.bat` execution tests to CI (depends on #18)
- [x] @builder #14: Add linting via `scripts/archive-jobs.py` format validation (depends on #13)
- [x] @tester @builder #15: Re-verify all tests pass (199 passed, 1 skipped)

## Verification
- [ ] #13: `python -c "import pathlib; assert pathlib.Path('scripts/archive-jobs.py').exists(); print('OK')"`
- [ ] #16: `python -c "import json; c=json.load(open('opencode.json')); agents=[n for n in c['agent']]; missing=[n for n in agents if isinstance(c['agent'][n], dict) and not c['agent'][n].get('variant')]; assert not missing, f'missing: {missing}'; print(f'{len(agents)-len(missing)}/{len(agents)} have variant')"`
- [ ] #17: `python -c "import json; c=json.load(open('opencode.json')); agents=[n for n in c['agent']]; missing=[n for n in agents if isinstance(c['agent'][n], dict) and not c['agent'][n].get('fallback_model')]; assert not missing; print('OK')"`
- [ ] #18: `python -c "import pathlib; assert pathlib.Path('.github/workflows/ci.yml').exists(); print('OK')"`
- [x] #20: `python -c "import pathlib; p=pathlib.Path('.opencode/plans/plan-015-tui-render-research.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) > 200; print('OK')"`
- [ ] #21: `python -c "import pathlib; assert pathlib.Path('pyproject.toml').exists() or pathlib.Path('mutmut_config.py').exists(); assert 'mutmut' in open('pyproject.toml').read() if pathlib.Path('pyproject.toml').exists() else True; print('OK')"`
- [ ] #22: `python -c "import pathlib; exists = [f for f in pathlib.Path('tests/').glob('*hypothesis*')] or [f for f in pathlib.Path('tests/').glob('*property*')]; assert exists, 'no hypothesis test file found'; print('OK:', exists[0].name)"`
- [ ] #19: `.github/workflows/ci.yml` contains `bat` or `setup.bat` or `global-setup`
- [x] #14: `scripts/archive-jobs.py` parses jobs.md with format validation
- [x] #15: `python -m pytest tests/ -q --tb=no 2>&1 | findstr /C:"passed"` ">`

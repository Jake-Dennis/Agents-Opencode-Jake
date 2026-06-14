# Plan 016: Ten Structural Improvements

## Goal
Implement 10 improvements identified during project audit: externalize prompts, fix model strategy, add sync checks, fix CI, add commands, and more.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1 - Fix hard-coded absolute path in test_agents_runtime.py (assigned: @builder)
- [ ] #2 - Make knowledge graph check a warning not hard failure in verify-plan.py (assigned: @builder)
- [ ] #3 - Add top-level model key + fix model inheritance test + fix README model docs (assigned: @builder)
- [ ] #4 - Fix CI: run full test suite on Windows + merge overlapping workflows (assigned: @builder)
- [ ] #5 - Add /status slash command (assigned: @builder)

### Layer 2 (depends on Layer 1 — tests must pass first)
- [ ] #6 - Externalize all 13 agent prompts to .md files, extract shared sections (assigned: @builder)
- [ ] #7 - Add agent-registry sync check (7th mechanical check) to verify-plan.py (assigned: @builder)

### Layer 3 (depends on Layer 2 — new checks need tests)
- [ ] #8 - Add tests for agent-registry sync check (assigned: @tester)
- [ ] #9 - Add structured jobs.md entry format documentation (assigned: @docs)

### Layer 4 (final verification)
- [ ] #10 - Run full test suite, verify-plan.py, and confirm all changes (assigned: @reviewer)

## Verification
- [ ] #1 - `python -c "from pathlib import Path; p=Path('tests/test_agents_runtime.py'); t=p.read_text(); assert 'C:\\\\Users\\\\JakeP' not in t; assert '__file__' in t"`
- [ ] #2 - `python scripts/verify-plan.py .opencode/plans/completed/plan-014-full-improvements.md`
- [ ] #3 - `python -c "import json; c=json.load(open('opencode.json')); assert 'model' in c; print('Top-level model:', c['model'])"`
- [ ] #4 - `python -m pytest tests/test_schema.py tests/test_verify_plan.py -v --tb=short`
- [ ] #5 - `python -c "from pathlib import Path; assert Path('.opencode/commands/status.md').exists()"`
- [ ] #6 - `python -c "import json; c=json.load(open('opencode.json')); [assert '{file:' in c['agent'][n]['prompt'] or len(c['agent'][n]['prompt'])<100 for n in c['agent']]"` (all prompts under 100 chars = file references)
- [ ] #7 - `python scripts/verify-plan.py .opencode/plans/plan-016-ten-improvements.md`
- [ ] #8 - `python -m pytest tests/ -v --tb=short`
- [ ] #9 - `python -c "from pathlib import Path; j=Path('.opencode/jobs.md'); t=j.read_text(); assert '## [' in t; assert 'Status:' in t"`
- [ ] #10 - `python -m pytest tests/ -v --tb=short && python scripts/verify-plan.py .opencode/plans/plan-016-ten-improvements.md`
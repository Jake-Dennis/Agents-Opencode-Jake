# Plan 017: Improve Agent Quality and Fix Graphify MCP

## Goal
Implement 10 agent improvements (shared sections, tool preferences, graphify dispatch, handoff format, boundaries, context, output formats, planner validation, self-review, context protocol) and fix the graphify MCP to use https://github.com/safishamsi/graphify.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1 - Extract shared sections into .opencode/agents/shared/ (assigned: @builder)
- [ ] #2 - Rewrite each agent prompt with per-agent tool preference, boundaries, output format, self-review (assigned: @builder)
- [ ] #3 - Add graphify dispatch context rule to conductor (assigned: @builder)
- [ ] #4 - Add structured handoff format to each agent (assigned: @builder)
- [ ] #5 - Add planner self-validation rule (assigned: @builder)
- [ ] #6 - Create .opencode/context.md protocol (assigned: @builder)
- [ ] #7 - Fix graphify MCP config (assigned: @builder)

### Layer 2 (depends on Layer 1)
- [ ] #8 - Update tests for new prompt structure (assigned: @tester)
- [ ] #9 - Update test_jobs.py for new shared section refs (assigned: @tester)
- [ ] #10 - Run full test suite and verify (assigned: @reviewer)

## Verification
- [ ] #1 - `python -c "from pathlib import Path; shared=Path('.opencode/agents/shared'); assert shared.is_dir(); assert (shared/'honesty.md').exists(); assert (shared/'consult.md').exists(); assert (shared/'tools.md').exists(); assert (shared/'graphify.md').exists(); assert (shared/'progress-tracking.md').exists()"`
- [ ] #2 - `python -c "import json; c=json.load(open('opencode.json',encoding='utf-8')); prompts=[]; [prompts.append(c['agent'][n]['prompt']) for n in c['agent']]; assert all('{file:' in p for p in prompts); assert all(len(p) < 100 for p in prompts); print('All prompts are file refs under 100 chars')"`
- [ ] #3 - `python -c "t=open('.opencode/agents/conductor.md',encoding='utf-8').read(); assert 'graphify context' in t.lower() or 'Graph context' in t; print('Conductor has graphify dispatch rule')"`
- [ ] #4 - `python -c "from pathlib import Path; assert Path('.opencode/context.md').exists(); print('context.md exists')"`
- [ ] #5 - `python scripts/verify-plan.py .opencode/plans/completed/plan-014-full-improvements.md`
- [ ] #6 - `python -m pytest tests/ -v --tb=short`
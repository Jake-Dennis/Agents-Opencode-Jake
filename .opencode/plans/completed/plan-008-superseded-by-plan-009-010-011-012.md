# Plan 008: Smoke-test all 13 agents

## Goal
Run `tests/test_agents_runtime.py` to invoke every agent (2 primary + 11 subagents) via
the `opencode` CLI, then delegate a review pass to interpret the results.

## Tasks

### Layer 1 (single, no deps)
- [ ] Conductor runs `python tests/test_agents_runtime.py` to invoke all 13 agents

### Layer 2 (depends on Layer 1)
- [ ] @reviewer interprets the runtime output and flags any failures or anomalies

## Verification
- [ ] Layer 1: exit code from `python tests/test_agents_runtime.py` saved verbatim in plan-008 log
  - `python -c "import json,sys; r=json.load(open('graphify-out/.graphify_labels.json'))" ; echo ok`
- [ ] Layer 2: @reviewer output written to `.opencode/plans/plan-008-review.md` with PASS/FAIL per agent
  - `Test-Path .opencode/plans/plan-008-review.md`
- [ ] work-log entry appended
  - `Get-Content .opencode/work-log.md | Select-String "Plan 008"`

## Notes
- Known Windows issue: `opencode agent list` segfaults; this test uses `opencode run` instead
  (avoiding the bug). If any agent segfaults, the test should still record it (timeout or rc!=0).
- 90s timeout per agent -> worst case ~20 min for all 13.

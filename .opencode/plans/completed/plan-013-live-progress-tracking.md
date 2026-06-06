# Plan 013: Live progress tracking for subagents

## Goal

Each of the 11 write-capable subagents (builder, tester, docs, debugger, refactor, perf, planner, architect, reviewer, explorer, security) updates a shared `.opencode/jobs.md` file as it works, so the conductor and the user can see live progress — not just the start and end. The 2 conductor-only artifacts (`.opencode/todo.md` and `.opencode/work-log.md`) keep their current roles.

## Why

The current model has 3 blind spots:

1. **Silence during long tasks.** A subagent may take 5-10 minutes on a multi-step task. The conductor has no signal of progress during that window.
2. **Ambiguous failure.** If a subagent disappears (e.g., hits its `steps` cap mid-task), the conductor only sees the absence of a completion report — not where it stalled.
3. **No audit trail of sub-step work.** The work-log captures the END of a plan; jobs.md captures the DURING.

A 1-3 line update from each subagent, written live, fixes all three.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @architect designs the jobs.md format, the per-agent prompt addition, and the opencode.json permission changes; writes `.opencode/plans/plan-013-design.md` (assigned: @architect)
- [ ] #2: @tester writes `tests/test_jobs.py` with 6 tests T-JB-1..T-JB-6 covering the format, the permission rules, and the prompt-addition coverage (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] #3: @builder updates `opencode.json` (path-scoped `edit` for 5 read-only agents; existing `edit: allow` for 6 implementation agents stays) (assigned: @builder)
- [ ] #4: @builder adds the "Live progress tracking" prompt section to all 11 write-capable agents (assigned: @builder)
- [ ] #5: @docs creates `.opencode/jobs.md` with a comment block documenting the format and one example entry (assigned: @docs)

### Layer 3 (depends on Layer 2)
- [ ] #6: @reviewer reviews all 5 deliverables; runs `scripts/verify-plan.py` FIRST (assigned: @reviewer)

### Layer 4 (conductor, depends on Layer 3)
- [ ] #7: @conductor runs final verify, archives plan, appends work-log, asks user to commit (assigned: @conductor)

## T1 Spec (@architect)

Read first:
- `opencode.json` (current 13-agent state with the new `color`/`temperature` fields)
- `AGENT-ROLES.md` (13-agent table; identifies which agents are read-only by design)
- `.opencode/plans/completed/plan-012-design.md` (the most recent agent-tuning work)
- `.opencode/work-log.md` (for the existing per-entry format style)

Write to: `.opencode/plans/plan-013-design.md` (new, 50-200 lines)

Output must contain:

### Section 1: The two-artifact split (todo vs jobs)
- `.opencode/todo.md` = high-level plan checklist, conductor-only, one row per Layer 1/2 task
- `.opencode/jobs.md` = fine-grained live progress, written by subagents, one entry per dispatch

### Section 2: The jobs.md format (must include)
- Entry header: `## [<plan-id>] @<agent> - <task summary>`
- Required fields: `Status` (5 values), `Started`, `Last update`, `Current step`, `Sub-steps` (checkbox list)
- Optional field: `Notes` (blockers, decisions, links)
- A regex for parsing: `^## \[(?P<plan_id>[^\]]+)\] @(?P<agent>\w+) - (?P<task>.+)$`

### Section 3: The 3 update rules (when to write)
1. **Start**: append a new entry with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: update `Last update` + `Current step`; flip sub-steps `[ ]` -> `[~]` -> `[x]`.
3. **Finish**: set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

### Section 4: The permission matrix (11 write-capable + 2 read-only agents)
- 6 implementation agents: `edit: "allow"` (existing — no change)
- 5 read-only agents: `edit: { ".opencode/jobs.md": "allow", "*": "deny" }` (new)
- git agent: NO edit access (git only does git, no change)
- conductor: NO change to permissions (conductor still owns todo.md and work-log.md)

### Section 5: The prompt addition (one section, applied to 11 agents)
A "Live progress tracking" section (~200-400 chars) added to each of the 11 write-capable agents. Section includes:
- The 3 update rules (Start, As you work, Finish)
- A 1-line reference to the format block in `.opencode/jobs.md`
- A worked example (3 lines max)

For the 5 read-only agents, the section clarifies "you have edit access to jobs.md ONLY" so the agent doesn't try to edit code.

### Section 6: Risk analysis
- **Risk 1: Path-scoped `edit` syntax.** The opencode docs use glob-style patterns. The pattern `".opencode/jobs.md"` may need to be `"**/.opencode/jobs.md"` or similar to match across the workdir. Architect must verify the exact pattern syntax and add a test for it.
- **Risk 2: jobs.md grows unbounded.** A plan with 30 dispatches leaves 30 entries. Mitigation: the conductor's prompt step 10 ("SYNC TODO") now also includes "archive completed entries older than 7 days to a sibling jobs-archive.md file (under .opencode/)". (Out of scope for plan-013; flag for a follow-up plan.)
- **Risk 3: Subagent writes are racy.** Two subagents dispatched in parallel could try to write at the same time. Mitigation: each subagent writes to a UNIQUE section keyed by `[@agent-name]` in the header. The plan-id + agent pair is unique per dispatch. The "as you work" updates within a single entry are serial (one agent, one entry).
- **Risk 4: Permission changes break existing tests.** T-AS-4 (permission preservation) and T-AS-15 (no temperature+top_p) will need to be reviewed. Architect should run pytest before/after the permission changes.
- **Risk 5: Subagents write verbose jobs.md entries.** Mitigation: the prompt addition says "Keep entries short — the file is for live status, not detailed logs." The conductor's work-log.md is the detailed log; jobs.md is the status board.

## T2 Spec (@tester)

New file: `tests/test_jobs.py` (stdlib only, 100-200 lines, pytest-compatible)

Tests:

- **T-JB-1**: 5 read-only agents (planner, architect, reviewer, explorer, security) have an `edit` permission that is an OBJECT (not a string) with `*` set to `deny` and `.opencode/jobs.md` set to `allow`.
- **T-JB-2**: 6 implementation agents (builder, tester, docs, debugger, refactor, perf) have an `edit` permission of `"allow"` (string, not object). This was the existing state; plan-013 does not change it.
- **T-JB-3**: The git agent does NOT have an `edit` permission that includes `.opencode/jobs.md`. (git has no `edit` key at all, or `edit: "deny"`.)
- **T-JB-4**: All 11 write-capable agents' prompts contain the string `Live progress tracking`. Verifies the prompt addition was applied.
- **T-JB-5**: The conductor's prompt does NOT contain the "Live progress tracking" section (the conductor owns todo.md and work-log.md, NOT jobs.md).
- **T-JB-6** (optional): The format regex from the design doc compiles and matches the example entry in `.opencode/jobs.md`. Guards against drift between the spec and the actual file.

Use helpers:
- `_load_config()` (same as test_agent_safety.py)
- `_load_agent_prompt(name, repo_path)` — reads the in-JSON prompt OR resolves a `{file:...}` ref (same pattern as test_conductor_workflow.py's helper)
- `_get_permission(agent, key)` — returns `cfg["agent"][name]["permission"][key]`, handling the case where the key is absent (git has no `edit` key)

## T3 Spec (@builder for opencode.json)

For each of the 5 read-only agents, replace `"edit": "deny"` with:
```json
"edit": {
  ".opencode/jobs.md": "allow",
  "*": "deny"
}
```

The 6 implementation agents keep `"edit": "allow"`.
The git agent's `permission` block is unchanged.
The conductor agent has no `permission.edit` key (and should not get one).

Field placement: inside the existing `permission` object. The order within `permission` is: `edit`, `bash`, `task` (the existing convention). The new `edit` object goes in the same position as the old `edit` string.

## T4 Spec (@builder for prompts)

For each of the 11 write-capable agents, append a "Live progress tracking" section to the END of the agent's `prompt` field (which is an in-JSON string for 10 of the 11; the conductor is the 11th but has its prompt in a markdown file).

The section text is:
```markdown

## Live progress tracking

As you work, update `.opencode/jobs.md` so the conductor and the user can see live status. Rules:

1. **Start**: append a new entry `## [<plan-id>] @<your-name> - <task>` with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: update `Last update` and `Current step`; flip sub-steps `[ ]` -> `[~]` -> `[x]`.
3. **Finish**: set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

The exact format and a worked example are in `.opencode/jobs.md` (the comment block at the top). Keep entries short — jobs.md is for status, work-log.md is for detail.
```

For the 5 read-only agents, prepend this clarification (within the same section):
```
You have edit access to `.opencode/jobs.md` ONLY (other files remain read-only).
```

## T5 Spec (@docs for jobs.md)

Create `.opencode/jobs.md` with:

1. A short header comment block documenting the format, the 3 update rules, and the per-agent ownership.
2. One example entry showing a complete (finished) dispatch.

File length: 30-80 lines.

## Verification

- [x] #1: `python -c "import json; c=json.load(open('opencode.json')); readonly=['planner','architect','reviewer','explorer','security']; impl=['builder','tester','docs','debugger','refactor','perf']; bad=[a for a in readonly if not (isinstance(c['agent'][a]['permission'].get('edit'), dict) and c['agent'][a]['permission']['edit'].get('.opencode/jobs.md')=='allow' and c['agent'][a]['permission']['edit'].get('*')=='deny')]; assert not bad, f'readonly agents missing path-scoped edit for jobs.md: {bad}'; bad2=[a for a in impl if c['agent'][a]['permission'].get('edit')!='allow']; assert not bad2, f'implementation agents missing edit:allow: {bad2}'; print(f'OK: 5 readonly + 6 impl agents have correct edit permissions')"`
- [x] #2: `python -c "import json; c=json.load(open('opencode.json')); assert 'edit' not in c['agent']['git']['permission'] or c['agent']['git']['permission'].get('edit')=='deny' or (isinstance(c['agent']['git']['permission'].get('edit'), dict) and c['agent']['git']['permission']['edit'].get('.opencode/jobs.md')!='allow'); print('OK: git agent does not have jobs.md edit access')"`
- [x] #3: `python -c "import json; c=json.load(open('opencode.json')); readonly=['planner','architect','reviewer','explorer','security']; impl=['builder','tester','docs','debugger','refactor','perf']; all_a=readonly+impl; missing=[a for a in all_a if 'Live progress tracking' not in str(c['agent'][a].get('prompt',''))]; assert not missing, f'agents missing Live progress tracking section: {missing}'; print(f'OK: all {len(all_a)} write-capable agents have the section')"`
- [x] #4: `python -c "import os; assert os.path.exists('tests/test_jobs.py'); content=open('tests/test_jobs.py', encoding='utf-8').read(); assert all(f'T-JB-{n}' in content for n in range(1, 7))"`
- [x] #5: `python -m pytest tests/test_jobs.py -q --tb=no`
- [x] #6: `python -c "import os; assert os.path.exists('.opencode/jobs.md'); content=open('.opencode/jobs.md', encoding='utf-8').read(); assert '## Format' in content or '## format' in content.lower(); assert 'Status:' in content; assert '## [' in content; print('OK: jobs.md exists with format + example entry')"`
- [x] #7: `python -c "import os; assert os.path.exists('.opencode/plans/plan-013-design.md') and 30 <= len(open('.opencode/plans/plan-013-design.md', encoding='utf-8').readlines()) <= 250"`
- [x] #8: `python -c "import os, json; c=json.load(open('opencode.json')); print(f'agents: {len(c[\"agent\"])}'); [print(f'{a}: steps={c[\"agent\"][a].get(\"steps\")}') for a in sorted(c['agent'])]"` (sanity check the config still loads)
- [x] #9: `python -m pytest tests/ -q --tb=no` (full suite — 150 + 6 new = 156 expected)
- [x] #10: `python -c "import re; t=open('.opencode/plans/plan-013-live-progress-tracking.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables', '## Notes']); print('OK: plan-013 structure')"`

## Deliverables

- `.opencode/jobs.md` (new, 30-80 lines, format + example)
- `opencode.json` (modified: 5 read-only agents gain path-scoped `edit` for jobs.md)
- 11 agent prompts in `opencode.json` (modified: each gets a "Live progress tracking" section appended)
- `tests/test_jobs.py` (new, 100-200 lines, 6 tests T-JB-1..T-JB-6)
- `.opencode/plans/plan-013-design.md` (new, 50-200 lines)
- Archived copies of the plan and design in `.opencode/plans/completed/` (created in L4)

## Out of scope

- **jobs.md archival/rotation** (a future plan adds a "archive completed entries older than 7 days to a sibling jobs-archive.md file" step to the conductor's prompt)
- **Real-time UI/TUI display of jobs.md** (the opencode TUI does not currently render jobs.md; that's a future feature)
- **Sub-step auto-population from the plan's L1/L2 task list** (the agent writes sub-steps manually; could be auto-populated from `## Tasks` in a future plan)
- **Cross-repo jobs aggregation** (each project has its own jobs.md; multi-project views are out of scope)
- **Markdown vs JSON for jobs.md** (markdown is more diffable and human-readable; JSON would be more parseable but worse for the user reading the file directly)

## Notes

- The conductor continues to own `.opencode/todo.md` (plan-level checklist) and `.opencode/work-log.md` (append-only log). The 11 subagents own `.opencode/jobs.md` (live status). This is a 3-file split with clear ownership.
- The "Live progress tracking" prompt addition is ~600 chars per agent. Across 11 agents, that's ~6.6 KB of additional prompt text. Acceptable context overhead.
- The path-scoped `edit` permission is a new pattern in this project. The git agent already uses a path-scoped `bash` (`{ "git *": "allow", "*": "deny" }`), so the syntax is established.
- The conductor's step 8 "VERIFY PLAN" still runs verify-plan.py. The new jobs.md file does not affect verify-plan.py's mechanical checks (none of the checks look at jobs.md).
- The pre-existing T-AS-4 test (permission preservation) checks the COUNT of permission keys, not their VALUES. The 5 read-only agents go from 1 edit value to 1 edit object (still 1 key). The test should still pass; architect verifies.

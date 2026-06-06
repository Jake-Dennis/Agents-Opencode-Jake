# Plan 009: Safety + cost-control primitives for 13 agents

## Goal

Add three production-grade safety + cost-control primitives to `opencode.json` — all config-only, additive, no prompt changes:

1. **`steps` cap on every agent** — hard upper bound on agentic iterations; prevents runaway loops from burning cost/tokens
2. **`permission.task: {"*": "deny"}` on every agent** — forces the conductor to be the sole dispatcher; no subagent recursion
3. **`compaction.prune: true` globally** — prunes old tool outputs during context compaction, saving tokens on long sessions

All three are mechanical upper-bounds (fits project priority #5: "mechanical, not LLM-judgment"). Default in upstream opencode for `compaction.prune` is `false`; default for `steps` is unbounded (model chooses when to stop); default for `permission.task` is "allow all subagents." We tighten all three.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @architect designs the per-agent `steps` matrix and confirms the `permission.task` deny-all + `compaction.prune: true` policy (assigned: @architect)
- [ ] #2: @tester writes `tests/test_agent_safety.py` with 4-5 structural tests against `opencode.json` (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] #3: @builder applies the architect's matrix to `opencode.json` — adds `steps`, adds `task` to each agent's `permission`, adds top-level `compaction` block (assigned: @builder)

### Layer 3 (depends on Layer 2)
- [ ] #4: @reviewer reviews all 3 deliverables (design doc + test file + config edit) (assigned: @reviewer)

### Layer 4 (conductor, depends on Layer 3)
- [ ] #5: @conductor runs `scripts/verify-plan.py`, archives plan, appends work-log, asks user to commit

## T1 Spec (@architect)

Read first:
- `opencode.json` (current 13-agent state)
- `AGENT-ROLES.md` (13-agent table — basis for `steps` values)
- `.opencode/decisions/adr-004-agent-roles.md` (rationale: 7 conductor-only reserved actions)
- The OpenCode schema at https://opencode.ai/config.json (already confirmed upstream: `AgentConfig.steps`, `PermissionConfig.task`)

Write to: `.opencode/plans/plan-009-design.md` (new file, 50-250 lines, markdown)

Output must contain:

### Section 1: `steps` matrix (proposed default)
| Agent | steps | Reasoning (cite AGENT-ROLES phase) |
|-------|-------|------------------------------------|
| conductor | 50 | Dispatch + verify + commit takes ~10-30 steps in normal use; 50 is comfortable headroom |
| planner | 30 | Analysis-only; bounded by section count of plan produced |
| architect | 30 | Design-only; bounded by ADR length |
| builder | 100 | Heaviest worker (multi-file edits, dependency install, test runs) |
| reviewer | 20 | Mechanical checklist; runs `scripts/verify-plan.py` + reads diffs |
| tester | 50 | Writes tests + runs them + iterates on failures |
| docs | 30 | Read code + write markdown; bounded by file count |
| debugger | 40 | Reproduce + isolate + fix + regression test |
| refactor | 50 | Multi-step refactor + run tests + iterate |
| git | 10 | Commit/push/PR is short |
| explorer | 20 | Read-only grep/glob; bounded by file count searched |
| security | 40 | Read code + CVE lookup + write report |
| perf | 40 | Profile + identify + measure + fix |

Architect MAY adjust these (e.g., bump builder to 150 if they think 100 is too tight). Document any change in the design doc with reasoning.

### Section 2: `permission.task` policy
**Recommendation: `"task": {"*": "deny"}` on ALL 13 agents (uniform).**

Rationale:
- The conductor is the sole dispatcher per ADR-004 (7 reserved actions: commit, push, archive, manifest edit, `opencode.json` edit, install scripts).
- Subagents invoking other subagents violates the dispatch architecture and creates recursion risk.
- Future plans may open specific edges (e.g., `builder → tester` for self-verifying loops) — but the safe default is deny-all.
- Per OpenCode docs: "When set to deny, the subagent is removed from the Task tool description entirely, so the model won't attempt to invoke it."
- Conductor and planner are `mode: primary` so the `task` field is mostly moot for them (they don't get invoked via task tool from other agents), but applying it uniformly is the no-surprise default.

### Section 3: `compaction` block
**Recommendation: `compaction: {"auto": true, "prune": true}` at the top level of `opencode.json`.**

- `auto: true` — opencode default; keeps it explicit for documentation
- `prune: true` — opt into pruning old tool outputs (default upstream is `false`)
- `tail_turns` / `preserve_recent_tokens` / `reserved` — leave at upstream defaults

## T2 Spec (@tester)

New file: `tests/test_agent_safety.py` (stdlib only, 50-300 lines, pytest-compatible)

Tests (each must be a function whose name starts with `test_`):

- **T-AS-1**: All 13 agents in `opencode.json` have a `steps` field that is a positive integer. Failure message lists which agents are missing or have invalid `steps`.
- **T-AS-2**: All 13 agents have `permission.task` equal to `{"*": "deny"}` (or its equivalent, e.g., `{"*": "deny", "ignored": "allow"}` — the test should normalize via "is `*` denied and no other rule allows?"). For agents with no `permission` block, this test should FAIL (must have at least `permission.task`).
- **T-AS-3**: Global `compaction.prune` is `True`. Global `compaction.auto` is `True` (defensive — we want to keep auto on even if we change prune).
- **T-AS-4**: For each of the 11 agents that have an EXISTING `permission` block (builder, architect, reviewer, tester, docs, debugger, refactor, git, explorer, security, perf), the new `task` field is present alongside the existing fields. Test loads `opencode.json`, iterates agents, asserts `set(permission.keys()) >= {"task", ...existing}`. This guards against accidental overwrite.
- **T-AS-5** (optional but recommended): Conductor's `steps` is >= 30 (regression check: we never accidentally cap the orchestrator at 5 like the OpenCode docs example for `quick-thinker`).

Pattern to follow: `tests/test_verify_plan.py` (existing mechanical-check test pattern from plan-007).

Constraints:
- Stdlib only, no new dependencies
- Existing 86 tests must still pass
- All assertions should print clear failure messages naming the offending agent

## T3 Spec (@builder)

Apply T1's design to `opencode.json`:

1. **For each of 13 agents**, add `"steps": <int>` (per architect's matrix in `.opencode/plans/plan-009-design.md`).
2. **For each of 13 agents**, add `"task": {"*": "deny"}` to the agent's `permission` block.
   - If agent has no `permission` block: add `{"task": {"*": "deny"}}`
   - If agent has `permission` as a string (e.g., `"deny"`): convert to object `{"task": {"*": "deny"}, "*": "deny"}` — wait, this is wrong. The `*` is not a valid top-level permission key; the keys are `read`/`edit`/`bash`/`task`/etc. If a current agent uses `"permission": "deny"` (a shorthand), that means "deny everything." To add `task` we must convert to the object form. For agents with `"permission": "deny"`, replace with `{"task": {"*": "deny"}}` (which is stronger than global defaults, equivalent to "deny everything for this agent") — BUT this is a behavior change. The architect's design should call this out.
   - If agent has `permission` as an object: add `"task": {"*": "deny"}` as a new key alongside existing.
3. **At the top level of `opencode.json`**, add a `compaction` block:
   ```json
   "compaction": {
     "auto": true,
     "prune": true
   }
   ```

Maintain all existing fields (`$schema`, `model`, `small_model`, `enabled_providers`, `provider`, `mcp`, `skills`, `command`, `instructions`, global `permission`) unchanged.

After the edit, verify JSON validity with:
```bash
python -c "import json; json.load(open('opencode.json')); print('valid')"
```

## T4 Spec (@reviewer)

Read `.opencode/plans/plan-009-design.md`, `tests/test_agent_safety.py`, and the modified `opencode.json`. Report on:

1. Does the `steps` matrix match the architect's design (or are there discrepancies)?
2. Are all 13 agents covered with both `steps` and `permission.task`?
3. Did the builder preserve the existing `permission` fields for agents that had them (e.g., `git`'s `bash: { "git *": "allow", "*": "deny" }` should still be there)?
4. Is the test file complete (T-AS-1 through T-AS-5, stdlib only, clear failure messages)?
5. Run `python scripts/verify-plan.py .opencode/plans/plan-009-agent-safety-primitives.md` FIRST (mechanical verification per conductor step 8). Report exit code 0 or non-zero + which checks failed.
6. Run `python -m pytest tests/test_agent_safety.py -q --tb=short` and report.

Per project discipline, this reviewer MUST run `scripts/verify-plan.py` and report its exit code before approving. Skipping this is a process violation.

## Verification

- [x] #1: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; assert len(agents)==13, f'expected 13 agents, got {len(agents)}'; missing=[a for a in agents if not isinstance(agents[a].get('steps'), int) or agents[a]['steps']<=0]; assert not missing, f'agents missing positive steps: {missing}'; print('OK: all 13 agents have positive steps')"`
- [x] #2: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; bad=[a for a in agents if agents[a].get('permission',{}).get('task',{}).get('*')!='deny']; assert not bad, f'agents missing deny-all task policy: {bad}'; print('OK: all 13 agents have permission.task deny-all')"`
- [x] #3: `python -c "import json; c=json.load(open('opencode.json')); assert c.get('compaction',{}).get('prune') is True; assert c.get('compaction',{}).get('auto') is True; print('OK: compaction.auto=True and compaction.prune=True')"`
- [x] #4: `python -c "import os; assert os.path.exists('tests/test_agent_safety.py'); content=open('tests/test_agent_safety.py', encoding='utf-8').read(); assert 'T-AS-1' in content and 'T-AS-2' in content and 'T-AS-3' in content; assert 50 <= len(content.splitlines()) <= 300, f'test file should be 50-300 lines, got {len(content.splitlines())}'"`
- [x] #5: `python -c "import os; assert os.path.exists('.opencode/plans/plan-009-design.md'); content=open('.opencode/plans/plan-009-design.md', encoding='utf-8').read(); assert 'steps' in content.lower() and 'permission' in content.lower() and 'compaction' in content.lower(); assert 30 <= len(content.splitlines()) <= 300"`
- [x] #6: `python -m pytest tests/test_agent_safety.py -q --tb=no`
- [x] #7: `python -c "import json; c=json.load(open('opencode.json')); p=c['agent']['git']['permission']; assert 'bash' in p and 'task' in p, f'git agent must keep existing bash permission AND new task; got {p}'; assert p['bash'] == {'git *': 'allow', '*': 'deny'}; print('OK: git agent preserves existing bash permission')"`
- [x] #8: `python -c "import re; t=open('.opencode/plans/plan-009-agent-safety-primitives.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables']); print('OK: plan has all required sections')"`

## Deliverables

- `opencode.json` (modified: +13 `steps` fields, +13 `permission.task` fields, +top-level `compaction` block)
- `.opencode/plans/plan-009-design.md` (new, 30-300 lines: `steps` matrix + `permission.task` policy + `compaction` block)
- `tests/test_agent_safety.py` (new, 50-300 lines, 4-5 tests T-AS-1..T-AS-5)
- archive plan to completed/ subfolder after verification passes

## Out of scope (future plans)

- **Item 0** (verify/fix model name `opencode/minimax-m3-free`): cannot verify locally because `opencode models` crashes with a SQLite error. Surface to user as a question in the final report.
- **Item 3** (move conductor + commands to markdown files): deserves its own plan with thorough testing of agent resolution and pre-commit hook integration.
- **Item 4** (add project-specific SKILL files for reusable workflows): separate plan.
- **Item 5** (per-agent variants + `temperature`/`top_p`/`color`): separate plan.

## Notes

- The 3 primitives are config-only and additive. They do not change agent prompts or user-visible behavior in the happy path. They only kick in at upper bounds (steps exhausted) or at denial points (task invocations).
- `compaction.prune` saves tokens on long sessions (default is `false` upstream). This is the safest "free win" — opt-in token savings.
- `permission.task: {"*": "deny"}` is the load-bearing safety primitive. It enforces the "conductor is sole dispatcher" architecture at the JSON level rather than relying on prompt prose.
- All 3 primitives are upstream-supported (verified against https://opencode.ai/config.json schema).
- The local `opencode.schema.json` (project-internal) does NOT validate these new fields explicitly (it only checks `description`/`mode`/`prompt`/`model`/`permission` keys), but its `agentEntry` and `permission` objects don't set `additionalProperties: false`, so the new fields are schema-safe.

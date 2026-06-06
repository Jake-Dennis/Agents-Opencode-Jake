# Plan 012: Per-agent color + temperature + top_p + variant

## Goal

Add per-agent visual differentiation (`color`) and behavioral tuning (`temperature`, `top_p`, optionally `variant`) to all 13 agents in `opencode.json`. Three concrete wins:

1. **TUI differentiation** — each agent gets a distinct color in the opencode TUI; conductor is one color, reviewer is another, etc. Easier to follow multi-agent dispatches.
2. **Determinism tuning** — code-review-class agents (reviewer, security, perf) get low `temperature` for stable checklists; creative-class agents (none in this project, all are task-focused) would get high.
3. **Variant override per agent** — the project's model is `opencode/minimax-m3-free` (unverified, see Risks). If the model supports variants (the upstream default for most Zen models is `default` plus a `low`/`high` reasoning variant), each agent can pick its variant.

All 3 fields are documented at https://opencode.ai/docs/agents (the "Options" section). All are additive; none change agent prompts.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @architect designs the per-agent matrix (13 agents × 4 fields), investigates whether `opencode/minimax-m3-free` supports variants, and writes `.opencode/plans/plan-012-design.md` (assigned: @architect)
- [ ] #2: @tester extends `tests/test_agent_safety.py` with T-AS-11..T-AS-15 (color/temperature/top_p/variant validity per agent) (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] #3: @builder applies the matrix to `opencode.json` (assigned: @builder)

### Layer 3 (depends on Layer 2)
- [ ] #4: @reviewer reviews all 3 deliverables (design + test + config) (assigned: @reviewer)

### Layer 4 (conductor, depends on Layer 3)
- [ ] #5: @conductor runs final verify, archives plan, appends work-log, asks user to commit (assigned: @conductor)

## T1 Spec (@architect)

Read first:
- https://opencode.ai/docs/agents (Options section: Temperature, Top P, Color, Variant, Model)
- `opencode.json` (current 13-agent state)
- `AGENT-ROLES.md` (13-agent table — basis for color/temperature decisions)
- `.opencode/decisions/adr-004-agent-roles.md` (rationale: 7 conductor-only reserved actions)

Investigate:
- Does the project's model `opencode/minimax-m3-free` support variants? (Caveat: `opencode models` CLI crashes on this machine, so architect may need to either (a) use webfetch on `https://opencode.ai/docs/models`, (b) read the project's own knowledge graph for model info, or (c) accept the uncertainty and only add `variant` to agents where it's clearly safe.)
- If the model doesn't support variants, the `variant` field is silently ignored by opencode. Test only checks the field is well-formed; behavior verification requires running opencode.

Write to: `.opencode/plans/plan-012-design.md` (new, 50-300 lines, markdown)

Output must contain:

### Section 1: Color matrix (13 agents)
| Agent | color (hex or theme name) | Reasoning |
|-------|--------------------------|-----------|
| conductor | `primary` | Orchestrator — the "default" color |
| planner | `secondary` | Planning — distinct from implementation |
| builder | `success` | Implementation — green for "go" |
| reviewer | `warning` | Review — yellow for "caution, look closely" |
| tester | `info` | Testing — blue for "info" |
| architect | `secondary` | Same family as planner |
| docs | `accent` | Documentation — accent color |
| debugger | `error` | Debugging — red for "fix this" |
| refactor | `success` | Same family as builder |
| git | `accent` | Operations |
| explorer | `info` | Read-only — blue for "info" |
| security | `error` | Security — red for "be careful" |
| perf | `warning` | Performance — yellow for "measure" |

Architect MAY adjust. The key constraint: 13 distinct-ish colors, semantically grouped.

### Section 2: Temperature matrix
**Recommendation:** only add `temperature` to a small subset of agents (3-5). Most agents use the model default. Specifically:

| Agent | temperature | Reasoning |
|-------|-------------|-----------|
| reviewer | 0.1 | Mechanical checklist; deterministic |
| security | 0.1 | Audit report; deterministic, no false positives |
| planner | 0.2 | Plan should be predictable, not creative |
| architect | 0.2 | Design should be predictable |
| (others) | (default) | Use model default; `reasoningEffort: max` is the override |

### Section 3: Top P matrix
**Recommendation:** only add `top_p` to the same 4 agents as temperature, with `top_p: 0.9` (slightly different from temperature but similar effect — both reduce randomness). Architect MAY choose one or the other; do not apply both to the same agent (mutually exclusive in practice).

### Section 4: Variant matrix (conditional)
**If the model supports variants**, add `variant: <name>` to selected agents. Variants are model-specific; for the project's model (likely `minimax-m3` from the Go sub or `big-pickle` from Zen), the common variants are `default`, `low`, `high`, `max`. Architect should:
- If model has `low` variant: set `variant: "low"` on reviewer, security, planner, architect (deterministic, fast)
- If model has `max` variant: leave at default (the project already sets `reasoning_effort: max` globally)
- If model has no variants: skip this section; just note in the design doc that variant was investigated and not supported

**If the model is unverifiable** (CLI broken, docs unclear), err on the side of NOT setting `variant` and note in the design doc. The `variant` field is safe to omit; setting it on a model that ignores it is a no-op.

### Section 5: Risk analysis
- **Risk 1**: `color` requires a valid hex code (`^#[0-9a-fA-F]{6}$`) or one of 8 theme names: `primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info`. Architect must verify each color.
- **Risk 2**: `temperature` and `top_p` may interact with `reasoningEffort: max` (which is set globally). The interaction is provider-specific. Some providers ignore `temperature` when `reasoningEffort` is set; others multiply. Test only checks the field is well-formed; behavior verification requires running opencode.
- **Risk 3**: `variant` is silently ignored if the model doesn't support it. Setting a wrong variant name is also silently ignored (no error). Test only checks the field is a non-empty string.
- **Risk 4**: The pre-existing config already sets `reasoning_effort: max` globally. Adding per-agent `temperature` may cause inconsistency (some agents run at temp=0.1 + reasoningEffort=max, others at model-default + reasoningEffort=max). Document this in the design doc.

## T2 Spec (@tester)

Extend `tests/test_agent_safety.py` with 5 new tests:

- **T-AS-11**: All 13 agents have a `color` field that is either a hex color (`^#[0-9a-fA-F]{6}$`) or one of the 8 theme names (`primary`/`secondary`/`accent`/`success`/`warning`/`error`/`info`/their `*-foreground` variants).
- **T-AS-12**: For agents with a `temperature` field, the value is a number in [0.0, 2.0]. (The upstream docs say 0.0-1.0 but providers may accept up to 2.0.)
- **T-AS-13**: For agents with a `top_p` field, the value is a number in [0.0, 1.0].
- **T-AS-14**: For agents with a `variant` field, the value is a non-empty string.
- **T-AS-15** (optional but recommended): No agent has BOTH `temperature` and `top_p` set (the architect's design said they're mutually exclusive; this guards against accidental dual-set).

## T3 Spec (@builder)

Apply T1's matrix to `opencode.json`. For each of 13 agents:
- Add `color: <value>` (per architect's color matrix)
- Conditionally add `temperature`, `top_p`, `variant` (only for the agents the architect specifies)

Maintain all existing fields. Place new fields in any position within the agent object (convention: after `permission`).

## T4 Spec (@reviewer)

Per project discipline, run `python scripts/verify-plan.py .opencode/plans/plan-012-agent-tunings.md` FIRST. Report exit code.

Then verify:
- All 5 new tests (T-AS-11..T-AS-15) pass
- The 13 agents' `color` values are valid
- The `temperature` / `top_p` / `variant` values match the architect's matrix
- No field conflicts with existing fields (`mode`, `permission`, `steps`, etc.)
- `git diff opencode.json` shows ONLY the new field additions (no other changes)

## Verification

- [x] #1: `python -c "import json, re; c=json.load(open('opencode.json')); agents=c['agent']; assert len(agents)==13; theme={'primary','secondary','accent','success','warning','error','info'}; bad=[(a,agents[a]['color']) for a in agents if not (re.match(r'^#[0-9a-fA-F]{6}$', agents[a].get('color','')) or agents[a].get('color') in theme)]; assert not bad, f'invalid colors: {bad}'; print('OK: all 13 agents have valid colors')"`
- [x] #2: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; bad=[(a,agents[a]['temperature']) for a in agents if 'temperature' in agents[a] and not (isinstance(agents[a]['temperature'],(int,float)) and 0.0 <= agents[a]['temperature'] <= 2.0)]; assert not bad, f'invalid temperatures: {bad}'; print('OK: all temperatures in [0.0, 2.0]')"`
- [x] #3: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; bad=[(a,agents[a]['top_p']) for a in agents if 'top_p' in agents[a] and not (isinstance(agents[a]['top_p'],(int,float)) and 0.0 <= agents[a]['top_p'] <= 1.0)]; assert not bad, f'invalid top_p: {bad}'; print('OK: all top_p in [0.0, 1.0]')"`
- [x] #4: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; bad=[(a,agents[a]['variant']) for a in agents if 'variant' in agents[a] and not (isinstance(agents[a]['variant'], str) and agents[a]['variant'].strip())]; assert not bad, f'invalid variants: {bad}'; print('OK: all variants are non-empty strings')"`
- [x] #5: `python -c "import json; c=json.load(open('opencode.json')); agents=c['agent']; bad=[a for a in agents if 'temperature' in agents[a] and 'top_p' in agents[a]]; assert not bad, f'agents with both temperature and top_p (should be mutually exclusive): {bad}'; print('OK: no agent has both temperature and top_p')"`
- [x] #6: `python -c "import os; assert os.path.exists('tests/test_agent_safety.py'); content=open('tests/test_agent_safety.py', encoding='utf-8').read(); assert all(f'T-AS-{n}' in content for n in range(11, 16))"`
- [x] #7: `python -m pytest tests/test_agent_safety.py -q --tb=no`
- [x] #8: `python -c "import os; assert os.path.exists('.opencode/plans/plan-012-design.md') and 30 <= len(open('.opencode/plans/plan-012-design.md', encoding='utf-8').readlines()) <= 350"`
- [x] #9: `python -c "import re; t=open('.opencode/plans/plan-012-agent-tunings.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables', '## Notes']); assert 'temperature' in t and 'top_p' in t and 'variant' in t and 'color' in t; print('OK: plan-012 structure + 4 tuning fields present')"`

## Deliverables

- `opencode.json` (modified: +13 `color` fields, +0-4 `temperature` fields, +0-4 `top_p` fields, +0-13 `variant` fields per architect's design)
- `.opencode/plans/plan-012-design.md` (new, 30-350 lines)
- `tests/test_agent_safety.py` (extended: +5 tests T-AS-11..T-AS-15)
- archive plan to completed/ subfolder after verification passes

## Out of scope

- **Plan-010** (markdown agent migration): separate plan, runs first
- **Plan-011** (project-specific SKILL.md files): separate plan
- **Model name verification** (`opencode/minimax-m3-free`): separate plan or user clarification. Affects plan-012's `variant` section.
- **`hidden: true` flag** (currently unused): could be applied to internal-only subagents in a future plan
- **`disable: true` flag** (currently unused): not needed unless an agent is being sunset

## Notes

- The `color` field is purely visual (TUI differentiation). Safe and reversible.
- The `temperature` and `top_p` fields are behavioral. They're provider-specific and may not behave as expected with `reasoningEffort: max`. Architect should document the expected behavior change.
- The `variant` field is model-specific. If the model doesn't support variants, the field is a no-op. Test only validates the field shape, not the behavior.
- All 3 fields are upstream-supported per https://opencode.ai/docs/agents.
- The local `opencode.schema.json` (project-internal) does NOT explicitly validate these fields, but its `agentEntry` doesn't set `additionalProperties: false`, so the new fields are schema-safe.

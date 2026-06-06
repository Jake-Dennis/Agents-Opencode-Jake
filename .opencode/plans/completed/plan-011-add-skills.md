# Plan 011: Add project-specific SKILL.md files

## Goal

Add 3-4 SKILL.md files for project-specific reusable workflows. The upstream opencode skill mechanism is configured (`skills.paths: [".opencode/skills"]`) but only the generic `graphify-agent-workflow` skill exists. The project has 3-4 workflows that are repeatedly invoked by the conductor and subagents — they're "tribal knowledge" in the work-log, but should be first-class `Skill` invocations.

Candidates (the 4 most-cited workflows in the work-log):

1. **plan-review** — Momus 4-criteria rubric (correctness/spec/clarity/operability) used to evaluate plans. Currently referenced in plan-005, plan-006, plan-007 work-log entries.
2. **batch-quoting** — the `%VAR%` vs `!VAR!` (parse-time vs delayed expansion) rules for `.bat` files. Currently referenced in plan-002, plan-004 work-log entries as a recurring gotcha.
3. **opencode-config-merge** — the per-key merge policy (scalars overwrite, arrays union+dedupe, agents deep-merge). Currently referenced in plan-002, plan-003 ADR-002.
4. **verify-plan-gate** — when `scripts/verify-plan.py` is non-zero, the canonical 5-step recovery (read the failure output, identify which check failed, fix the plan file or the underlying code, re-run, archive). Currently referenced in plan-007 work-log as a process invariant.

Upstream skill format: SKILL.md with YAML frontmatter (`name:`, `description:`) and markdown body. Name regex: `^[a-z0-9]+(-[a-z0-9]+)*$` (1-64 chars). Description is 1-1024 chars and shown in agent context.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @architect selects the final 3 or 4 candidates from the list above, designs the folder structure, and confirms the frontmatter shape against upstream spec (assigned: @architect)
- [ ] #2: @tester writes `tests/test_skills.py` with 6-8 tests covering frontmatter validity, name regex, description length, body content presence, and the upstream "skill loads on demand" pattern (assigned: @tester)

### Layer 2 (depends on Layer 1)
- [ ] #3: @docs writes 3-4 SKILL.md files in the per-skill subdir under `.opencode/skills/` per the architect's design (assigned: @docs)

### Layer 3 (depends on Layer 2)
- [ ] #4: @reviewer reviews all 3-4 skill files + the test file; runs `scripts/verify-plan.py` FIRST (assigned: @reviewer)

### Layer 4 (conductor, depends on Layer 3)
- [ ] #5: @conductor runs final verify, archives plan, appends work-log, asks user to commit (assigned: @conductor)

## T1 Spec (@architect)

Read first:
- https://opencode.ai/docs/skills (upstream skill spec)
- `.opencode/skills/graphify-agent-workflow/SKILL.md` (the existing project skill — match its style)
- `.opencode/work-log.md` (the 4 workflow citations above)
- `.opencode/plans/completed/plan-007-process-improvements.md` (the 5 mechanical checks referenced in `verify-plan-gate`)

Write to: `.opencode/plans/plan-011-design.md` (new file, 30-150 lines, markdown)

Output must contain:

### Section 1: Final candidate list (pick 3 or 4)
- Confirm or trim the 4 candidates above
- For each, give the rationale: where it's cited in the work-log, how often it's invoked per plan, and what goes in the body
- Recommend 3 or 4 (not all 4 if any are weak)

### Section 2: Folder structure
```
.opencode/skills/
├── graphify-agent-workflow/   # already exists
├── plan-review/                # new
│   └── SKILL.md
├── batch-quoting/              # new
│   └── SKILL.md
├── opencode-config-merge/      # new
│   └── SKILL.md
└── verify-plan-gate/           # new (optional)
    └── SKILL.md
```

### Section 3: Frontmatter shape (per skill)
For each skill, specify the frontmatter `name` and `description` (the description should explain WHEN to invoke, not WHAT it does). Example for `plan-review`:

```yaml
---
name: plan-review
description: Use when reviewing a plan against the Momus 4-criteria rubric (correctness, specification, clarity, operability). Invoke BEFORE approving a plan or before /build commits a plan to the archive.
---
```

### Section 4: Body content outline
For each skill, a 1-2 sentence body summary + a bullet list of what the body should contain (the 4-criteria checklist for `plan-review`, the `%VAR%` vs `!VAR!` rules for `batch-quoting`, etc.).

### Section 5: Risk analysis
- **Risk 1**: Skills are loaded into LLM context. 4 new skills = ~500 tokens of context overhead. Acceptable.
- **Risk 2**: The `name` regex is strict (`^[a-z0-9]+(-[a-z0-9]+)*$`). Architect must verify all 4 names pass.
- **Risk 3**: The skill `description` is what the LLM sees to decide whether to invoke. Bad descriptions = skill never gets loaded. Architect should write descriptions from the AGENT'S perspective (when does an agent want this?).
- **Risk 4**: Name collisions with built-in skills (`graphify` already exists in user-scope via `python -m graphify install`). Project-scope names must not collide with user-scope names. Confirm: `plan-review`, `batch-quoting`, `opencode-config-merge`, `verify-plan-gate` do not collide with any built-in or user-scope skill.

## T2 Spec (@tester)

New file: `tests/test_skills.py` (stdlib only, 100-300 lines, pytest-compatible)

Tests:

- **T-SK-1**: All 3-4 new SKILL.md files exist at the canonical per-skill subdir under `.opencode/skills/`.
- **T-SK-2**: Each SKILL.md starts with `---` (YAML frontmatter delimiter on line 1).
- **T-SK-3**: Each skill's `name` field matches the regex `^[a-z0-9]+(-[a-z0-9]+)*$` and is 1-64 chars.
- **T-SK-4**: Each skill's `description` is 1-1024 chars and is non-empty after strip.
- **T-SK-5**: No name collision with the existing `graphify` skill (or with any built-in).
- **T-SK-6** (optional but recommended): Each skill's body (after the closing `---`) is at least 100 chars and at most 10000 chars. Guards against empty skills and bloated ones. (5000 was found to be too tight for the opencode-config-merge per-key table + worked examples; 10000 is the upper bound chosen for this project.)
- **T-SK-7** (optional): The `plan-review` skill's body contains the 4 criteria keywords: "correctness", "specification", "clarity", "operability" (case-insensitive). Ensures the rubric actually landed in the body.
- **T-SK-8** (optional): The `batch-quoting` skill's body contains both `%` and `!` (the two expansion types). Ensures the gotcha is documented.

Use a helper `_load_skill(name) -> dict` that parses the YAML frontmatter with a simple regex (no PyYAML dep — split on `---` lines, parse the inner block with `re` or `yaml` if available; fall back to a minimal manual parser if PyYAML not installed).

## T3 Spec (@docs)

Per architect's design, write 3-4 SKILL.md files. Each file is:

```yaml
---
name: <skill-name>
description: <when to invoke, from agent's perspective>
---

# <Skill Title>

## When to use
<2-3 sentences>

## Process / Checklist
<the actual workflow — bullet list or numbered steps>

## Examples
<1-2 concrete examples from the work-log>

## Common pitfalls
<1-2 things that go wrong>
```

Target: 80-400 lines per file. Not too short (no value), not too long (context bloat).

## T4 Spec (@reviewer)

Per project discipline, run `python scripts/verify-plan.py .opencode/plans/plan-011-add-skills.md` FIRST. Report exit code.

Then verify:
- All 8 tests (T-SK-1..T-SK-8) pass
- Each SKILL.md is well-formed (frontmatter delimiters, body is real content not "TODO")
- The descriptions are agent-perspective ("Use when...") not author-perspective ("This skill does...")
- The bodies contain the actual workflow content (cross-check against the work-log citations)

## Verification

- [x] #1: `python -c "import os, re; n=4; skills=['plan-review','batch-quoting','opencode-config-merge','verify-plan-gate']; missing=[s for s in skills if not os.path.exists(f'.opencode/skills/{s}/SKILL.md')]; assert not missing, f'missing skills: {missing}'; print(f'OK: all {n} skills present')"`
- [x] #2: `python -c "import os, re; skills=['plan-review','batch-quoting','opencode-config-merge','verify-plan-gate']; bad=[]; 
for s in skills:
    p=f'.opencode/skills/{s}/SKILL.md'
    content=open(p, encoding='utf-8').read()
    lines=content.splitlines()
    if not lines or lines[0].strip() != '---':
        bad.append(f'{s}: no frontmatter start')
        continue
    m=re.search(r'^name:\s*(\S+)', content, re.M)
    if not m or not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', m.group(1)) or len(m.group(1))>64:
        bad.append(f'{s}: invalid name')
    m=re.search(r'^description:\s*(.+)$', content, re.M)
    if not m or not (1 <= len(m.group(1).strip()) <= 1024):
        bad.append(f'{s}: invalid description')
assert not bad, f'skill validation failed: {bad}'
print('OK: all skills pass frontmatter validation')"`
- [x] #3: `python -c "import os; assert os.path.exists('tests/test_skills.py'); content=open('tests/test_skills.py', encoding='utf-8').read(); assert 'T-SK-1' in content and 'T-SK-2' in content and 'T-SK-3' in content; assert 80 <= len(content.splitlines()) <= 350"`
- [x] #4: `python -m pytest tests/test_skills.py -v --tb=short`
- [x] #5: `python -c "import os; assert os.path.exists('.opencode/plans/plan-011-design.md') and 20 <= len(open('.opencode/plans/plan-011-design.md', encoding='utf-8').readlines()) <= 200"`
- [x] #6: `python -c "import re; t=open('.opencode/plans/plan-011-add-skills.md', encoding='utf-8').read(); assert all(s in t for s in ['## Goal', '## Tasks', '## Verification', '## Deliverables', '## Notes']); assert 'plan-review' in t and 'batch-quoting' in t and 'opencode-config-merge' in t and 'verify-plan-gate' in t; print('OK: plan-011 structure + candidate names present')"`

## Deliverables

- `.opencode/skills/plan-review/SKILL.md` (new, 80-400 lines)
- `.opencode/skills/batch-quoting/SKILL.md` (new, 80-400 lines)
- `.opencode/skills/opencode-config-merge/SKILL.md` (new, 80-400 lines)
- `.opencode/skills/verify-plan-gate/SKILL.md` (new, 80-400 lines) — drop if architect decides 3 is the right count
- `.opencode/plans/plan-011-design.md` (new: architect's design, 20-200 lines)
- `tests/test_skills.py` (new: 6-8 tests, 80-350 lines)
- archive plan to completed/ subfolder after verification passes

## Out of scope

- **Plan-010** (markdown agent migration): separate plan, runs first
- **Plan-012** (per-agent variants + temperature/top_p/color): separate plan
- **More skills** (e.g., `pre-commit-hook`, `graph-builder`): 3-4 is the right count for now; add more when there's a clear use case
- **Skill auto-invocation tests** (does the LLM actually invoke the skill when given a matching task?): that's an integration test; not in scope

## Notes

- The upstream skill spec is at https://opencode.ai/docs/skills. The frontmatter keys are `name` and `description` (other keys may be supported but these are the documented required ones).
- Skills are loaded on demand — the LLM sees the skill descriptions and decides when to load. So the `description` field is the most important: bad descriptions = skill never gets loaded.
- Each skill adds ~100-500 tokens of context overhead when loaded. With 4 new skills, peak context overhead is ~2 KB. Acceptable.
- The `graphify-agent-workflow` skill is already installed (user-scope, from the `python -m graphify install --platform opencode` invocation in plan-004's work-log). The new project-scope skills are additive; they don't replace it.
- Skill names with hyphens (kebab-case) match the upstream name regex. Underscores would not.

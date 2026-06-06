# Plan 011 Design: SKILL.md candidates, structure, frontmatter

## Section 1: Final candidate list (4 picked, all 4 retained)

All 4 candidates earn their place. Rationale + work-log citation per skill:

### 1. `plan-review` (KEEP)
- **When invoked:** Before approving a plan, before /build commits, and any time a subagent's output needs to be sanity-checked against the original spec.
- **Citations:** plan-005 (Momus rubric applied to light-survey docs), plan-006 (applied to full-survey docs; 13/13 verify approval), plan-007 (the 4-criteria were translated into 5 mechanical regex checks; this is the design rationale).
- **Body:** the 4 criteria (correctness, specification, clarity, operability) with what "pass" looks like for each; a worked example from plan-007's review.

### 2. `batch-quoting` (KEEP)
- **When invoked:** Any time the conductor or @builder writes or edits a `.bat` file; any time a value is passed from a `set VAR=...` line into a parenthesized `( ... )` block.
- **Citations:** plan-002 (work-log has 5+ `cmd : : was unexpected` / `findstr` / `(admin?)` bugs all rooted in batch parser confusion), plan-004 (`%REFRESH_ARGS%` vs `!REFRESH_ARGS!` parse-time vs delayed expansion gotcha), plan-002 follow-up (5 `::` comments inside parens blocks all fixed by converting to `REM`).
- **Body:** the `%VAR%` (parse-time) vs `!VAR!` (delayed, needs `setlocal enabledelayedexpansion`) rules; the `set "VAR=..."` (quote-strip) form; the `( ... )` block parens escaping rules; the `::` label inside parens trap.

### 3. `opencode-config-merge` (KEEP)
- **When invoked:** When global-setup.bat / setup.bat runs, when a per-key merge policy is questioned, when uninstall is questioned.
- **Citations:** plan-002 (initial per-key merge policy, 710-line merge helper, 30 tests), plan-003 (extended to `command`/`mcp`/`provider`/`permission` deep-merge, snapshot+restore, FIRST-wins; 59 tests), ADR-002 (the canonical reference).
- **Body:** the full per-key table (scalars overwrite, arrays union+dedupe, `agent.<name>` deep-merge with warning, `command.<name>` / `mcp.<name>` project-wins, `provider`/`permission` deep-merge+restore, `enabled_providers` union+filter, `$schema` overwrite); the snapshot+restore semantic; the FIRST-wins on re-runs rule.

### 4. `verify-plan-gate` (KEEP)
- **When invoked:** Any time a plan's verify-plan.py run fails; any time the LLM is tempted to trust a subagent's "I did it" report; any time the /build command's step 7.5 fires.
- **Citations:** plan-007 (the 5 mechanical checks were added to make this gate objective), work-log entry "Make plan verification automatic in all future agent invocations" (the 3-layer enforcement — conductor prompt + reviewer subagent + /build command + pre-commit hook).
- **Body:** the 5 mechanical checks, the 3-layer enforcement, the canonical 5-step recovery (read the failure output, identify which check failed, fix the plan file or the underlying code, re-run, archive).

## Section 2: Folder structure

```
.opencode/skills/
├── graphify-agent-workflow/   # already exists (project-scope, used by graphify plugin)
│   └── SKILL.md
├── plan-review/                # new
│   └── SKILL.md
├── batch-quoting/              # new
│   └── SKILL.md
├── opencode-config-merge/      # new
│   └── SKILL.md
└── verify-plan-gate/           # new
    └── SKILL.md
```

No `references/` subdirs needed — each skill's body is self-contained (80-400 lines). Matches the existing `graphify-agent-workflow` style.

## Section 3: Frontmatter shape (per skill)

```yaml
---
name: <kebab-case-skill-name>
description: Use when <when to invoke, from agent's perspective>. Avoid <when NOT to invoke>.
---
```

The `description` is what the LLM sees to decide whether to load. The format is "Use when... Avoid..." (positive then negative) so the LLM can pattern-match both ways.

| Skill | name | description |
|---|---|---|
| plan-review | `plan-review` | Use when reviewing a plan or subagent output against the Momus 4-criteria rubric (correctness, specification, clarity, operability). Invoke before approving a plan, before /build commits it, or whenever a subagent's claim needs sanity-checking. Avoid for casual code review — use the `reviewer` agent for that. |
| batch-quoting | `batch-quoting` | Use when writing or editing a `.bat` file, or when a value flows from `set VAR=...` into a parenthesized `( ... )` block. Covers `%VAR%` parse-time vs `!VAR!` delayed expansion, the `set "VAR=..."` quote-strip form, and the `::` label-inside-parens trap. Avoid for shell scripts — this is Windows `.bat` only. |
| opencode-config-merge | `opencode-config-merge` | Use when running or troubleshooting the global-install / uninstall scripts, or when a per-key merge policy is questioned. Documents the per-key table (scalars overwrite, arrays union+dedupe, `agent.<name>` deep-merge with warning, `command.<name>`/`mcp.<name>` project-wins, `provider`/`permission` deep-merge+restore, `enabled_providers` union+filter, `$schema` overwrite) and the snapshot+restore semantic. |
| verify-plan-gate | `verify-plan-gate` | Use when `verify-plan.py` returns non-zero, or when the LLM is tempted to trust a subagent's "I did it" report. The 3-layer enforcement (conductor prompt step 8, reviewer subagent first action, /build command step 7.5, pre-commit hook) is non-negotiable. Invoke the canonical 5-step recovery: read failure, identify check, fix plan or code, re-run, archive. |

## Section 4: Body content outline

Each skill: 80-400 lines, with the following sections:

### 1. `# <Title>`
### 2. `## When to use`
   2-3 sentences from the agent's perspective.
### 3. `## Process / Checklist`
   The actual workflow as a numbered list or bullet list.
### 4. `## Examples`
   1-2 concrete examples from the work-log (with the citation).
### 5. `## Common pitfalls`
   1-2 things that go wrong + how to avoid them.

### Per-skill body specifics

- **plan-review** body must contain: the 4 criteria (correctness, specification, clarity, operability); what "pass" looks like for each; a worked example from plan-007's review of verify-plan.py.
- **batch-quoting** body must contain: `%VAR%` (parse-time) vs `!VAR!` (delayed); `setlocal enabledelayedexpansion` requirement; `set "VAR=..."` quote-strip form; the `( ... )` block trap; the `::` label-inside-parens trap; at least one example showing a parse-time bug and its fix.
- **opencode-config-merge** body must contain: the per-key table (or the ADR-002 link + a summary); the `provider`/`permission` snapshot+restore semantic; the FIRST-wins rule; the manifest v2 schema; at least one worked example from plan-002/003.
- **verify-plan-gate** body must contain: the 5 mechanical checks; the 3-layer enforcement; the canonical 5-step recovery; the `python scripts/verify-plan.py <plan>` command.

## Section 5: Risk analysis

- **Risk 1: Context overhead.** 4 new skills = peak ~2 KB of context when loaded (per upstream guidance, skills load on demand). Acceptable. Mitigation: keep bodies under 400 lines each.
- **Risk 2: Name regex strictness.** `^[a-z0-9]+(-[a-z0-9]+)*$`, 1-64 chars. All 4 names (`plan-review`, `batch-quoting`, `opencode-config-merge`, `verify-plan-gate`) match. Verified.
- **Risk 3: Description-driven invocation.** Bad descriptions = skill never loaded. Mitigated by the "Use when... Avoid..." pattern (positive AND negative guidance); verified by T-SK-7 / T-SK-8 (rubric keywords + expansion-type symbols).
- **Risk 4: Name collisions.** Built-in opencode skills are: `graphify` (user-scope, from `python -m graphify install --platform opencode`). Project-scope names: `plan-review`, `batch-quoting`, `opencode-config-merge`, `verify-plan-gate`. No collisions. The `graphify-agent-workflow` (project-scope, plugin-loaded) is also non-colliding.
- **Risk 5: Skill loads on which agent?** Skills are project-scope; any agent can load any skill by name. The descriptions are written generically so the LLM (any agent) can decide. No per-agent `permission.skill` denylist needed.
- **Risk 6: Stale content.** The bodies cite specific work-log entries (plan-002, plan-003, etc.). If those plans are renamed/removed, the citations become stale. Mitigation: archive plans live in `.opencode/plans/completed/`; the file paths are stable.

## Section 6: Test plan (T-SK-1..T-SK-8)

See plan body. New file: `tests/test_skills.py`, stdlib only, ~100-300 lines, pytest-compatible. Uses a regex-based YAML frontmatter parser (no PyYAML dep) that splits on `---` lines and parses `name:`/`description:` keys.

## Section 7: Out of scope

- More skills (e.g., `pre-commit-hook`, `graph-builder`, `verify-plan-bugfix-catalog`): the catalog is a future plan; 4 is the right count for now.
- Skill auto-invocation tests (does the LLM actually invoke the skill on a matching task?): that's an integration test; requires a live LLM. Not in scope.
- `references/` subdirs per skill: bodies are self-contained. Add if any skill grows past 400 lines.
- `opencode.json` `skills.paths` update: `["~/.config/opencode/skills", "./.opencode/skills"]` is already set (per the `setup-project` and the graphify install work-log). New skills auto-discovered from `.opencode/skills/`.

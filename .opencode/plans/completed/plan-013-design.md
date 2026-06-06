# Plan 013 Design: Live progress tracking for subagents

## Section 1: The two-artifact split (todo vs jobs)

The project has 3 long-lived markdown files for state, with 3 distinct owners:

| File | Owner | Purpose | When written | Granularity |
|---|---|---|---|---|
| `.opencode/todo.md` | Conductor only | High-level plan checklist | Layer 1 of the workflow | One row per L1/L2 task |
| `.opencode/work-log.md` | Conductor only | Append-only plan audit | End of each plan | One entry per plan |
| `.opencode/jobs.md` (new) | Subagents (11) | Live subagent status | Start, as-you-work, finish | One entry per dispatch, with sub-steps |

The new `jobs.md` is the missing middle layer: it captures WHAT each subagent is doing RIGHT NOW, which neither todo.md (plan-level, not agent-level) nor work-log.md (plan-end summary, not live) provides.

## Section 2: The jobs.md format

```markdown
# Jobs (live progress)

> Auto-managed by subagents. Do not edit by hand. See plan-013 design
> for the format and update rules.

## Format (read this before writing)

Each entry is one subagent dispatch. Use this exact shape:

```
## [<plan-id>] @<agent> - <task summary>
- **Status:** pending | in_progress | complete | failed | blocked
- **Started:** <ISO 8601 timestamp, e.g. 2026-06-06T16:00:00Z>
- **Last update:** <ISO 8601 timestamp>
- **Current step:** <one-line description of what the agent is doing RIGHT NOW>
- **Sub-steps:**
  - [x] <completed sub-step>
  - [~] <in-progress sub-step>
  - [ ] <pending sub-step>
- **Notes:** <optional — blockers, decisions, links to artifacts>
```

**3 update rules:**

1. **Start**: append a new entry with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: update `Last update` and `Current step`; flip sub-steps `[ ]` -> `[~]` -> `[x]`.
3. **Finish**: set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

## Example (a finished dispatch)

## [plan-013] @builder - Add T-JB-1..T-JB-6 to test_jobs.py
- **Status:** complete
- **Started:** 2026-06-06T16:00:00Z
- **Last update:** 2026-06-06T16:08:00Z
- **Current step:** marked Status: complete; all 6 sub-steps [x]
- **Sub-steps:**
  - [x] Read opencode.json permission block
  - [x] Read existing test_agent_safety.py for style
  - [x] Write T-JB-1 (5 readonly agents have path-scoped edit)
  - [x] Write T-JB-2 (6 impl agents have edit: allow)
  - [x] Write T-JB-3 (git agent has no jobs.md access)
  - [x] Write T-JB-4 (11 agents' prompts contain jobs.md OR Live progress tracking)
- **Notes:** 6/6 tests passing on first run; no edge cases hit.
```

**Parsing regex** (for tools that want to consume jobs.md):

```python
import re
ENTRY_HEADER_RE = re.compile(
    r"^## \[(?P<plan_id>[^\]]+)\] @(?P<agent>\w+) - (?P<task>.+)$",
    re.MULTILINE,
)
```

The header uniquely identifies an entry; the body fields are stable, but tools should be lenient about which fields are present (some agents may skip `Notes`).

## Section 3: The 3 update rules (when to write)

1. **Start** — append a new entry. Status: `in_progress`. Started: now. Current step: 1-line description. Sub-steps: first one is `[~]`, rest are `[ ]`. The `[@agent]` in the header is your agent name (e.g., `@builder`, `@reviewer`).
2. **As you work** — update `Last update` (now), `Current step` (what you're doing). Flip a sub-step from `[ ]` to `[~]` when you start it; flip `[~]` to `[x]` when you finish it. Don't try to maintain a real-time sub-step list (too much writing); aim for 1-3 updates per entry total.
3. **Finish** — Status: `complete` (or `failed`/`blocked` if you couldn't complete the task). Mark the last sub-step `[x]`. The `Last update` is your finish timestamp.

**Why 1-3 updates, not real-time:** the LLM context is the bottleneck. Each jobs.md write consumes prompt tokens. The 3-rule pattern is "one entry, 3 phases, ~3 writes total" — minimum overhead with maximum status value.

## Section 4: The permission matrix (11 write-capable + 2 read-only agents)

The 13-agent system splits into 3 groups for plan-013:

| Group | Agents | `edit` permission (after plan-013) |
|---|---|---|
| Implementation (6) | builder, tester, docs, debugger, refactor, perf | `"edit": "allow"` (existing — no change) |
| Read-only (5) | planner, architect, reviewer, explorer, security | `"edit": { ".opencode/jobs.md": "allow", "*": "deny" }` (new — path-scoped) |
| Special (2) | conductor, git | unchanged (conductor has no `edit` key; git has no `edit` key) |

The path-scoped `edit` for the 5 read-only agents is a NEW pattern in this project (the git agent already uses path-scoped `bash`, so the syntax is established). The pattern syntax matches the opencode docs' "file path patterns" — exact path with `*` as the catch-all wildcard.

**Test T-JB-1** asserts the exact shape of the 5 read-only agents' `edit` permission. **Test T-JB-2** asserts the 6 implementation agents' `edit: "allow"`. **Test T-JB-3** asserts git does NOT have jobs.md access.

## Section 5: The prompt addition (one section, applied to 11 agents)

A "Live progress tracking" section (~600 chars) appended to the end of each of the 11 write-capable agents' `prompt` fields. The section text is:

```markdown

## Live progress tracking

As you work, update `.opencode/jobs.md` so the conductor and the user can see live status. Rules:

1. **Start**: append a new entry `## [<plan-id>] @<your-name> - <task>` with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: update `Last update` and `Current step`; flip sub-steps `[ ]` -> `[~]` -> `[x]`.
3. **Finish**: set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

The exact format and a worked example are in `.opencode/jobs.md` (the comment block at the top). Keep entries short — jobs.md is for status, work-log.md is for detail.
```

For the 5 read-only agents, prepend a clarification within the same section:

```markdown
You have edit access to `.opencode/jobs.md` ONLY (other files remain read-only).
```

**Field placement:** appended to the END of the agent's `prompt` string. The conductor's prompt is in `.opencode/agents/conductor.md` and is NOT modified (the conductor does not write to jobs.md).

## Section 6: Risk analysis

- **Risk 1: Path-scoped `edit` syntax.** The opencode docs use glob-style patterns. The exact path `".opencode/jobs.md"` should match the file at the repo root. T-JB-1 will catch any syntax error. If the path pattern requires `**/` prefix, the prompt addition includes a note for the builder.
- **Risk 2: jobs.md grows unbounded.** A plan with 30 dispatches leaves 30 entries. Mitigation: the conductor's prompt step 10 ("SYNC TODO") is updated in a FOLLOW-UP plan to also include "archive completed entries older than 7 days to `.opencode/jobs-archive.md`". Out of scope for plan-013; the file is small enough (a few KB per plan) that this can wait.
- **Risk 3: Subagent writes are racy.** Two subagents dispatched in parallel (e.g., builder + tester in Layer 2) could try to write to jobs.md at the same time. Mitigation: each subagent writes to a UNIQUE section keyed by `[@agent-name]` in the header. The pair `(<plan-id>, @<agent-name>)` is unique per dispatch. The "as you work" updates within a single entry are serial (one agent, one entry, one set of sub-steps). Cross-entry races are still possible but benign — each agent appends a new entry; no agent overwrites another's entry.
- **Risk 4: Permission changes break T-AS-4 (permission preservation).** T-AS-4 in test_agent_safety.py checks the COUNT of permission keys. The 5 read-only agents go from 1 edit value to 1 edit object (still 1 key in the permission block). The test should still pass. The architect runs the full test suite before/after the changes to confirm.
- **Risk 5: Subagents write verbose jobs.md entries.** Mitigation: the prompt addition says "Keep entries short — jobs.md is for status, work-log.md is for detail." Future plans could add a size cap (e.g., max 50 lines per entry) but that's out of scope.
- **Risk 6: The `edit: { ... }` object might not be supported by the opencode CLI on this machine.** The git agent already uses a path-scoped `bash: { "git *": "allow", "*": "deny" }` object, so the opencode CLI version supports this pattern. Risk is low.
- **Risk 7: The conductor's prompt doesn't mention jobs.md.** The conductor continues to own todo.md and work-log.md. The conductor's prompt (`.opencode/agents/conductor.md`) is unchanged. T-JB-5 asserts the conductor's prompt does NOT contain "Live progress tracking".

## Section 7: Implementation order

1. **L1**: Write `tests/test_jobs.py` (T-JB-1..T-JB-6) — should fail (the prompt additions and permission changes aren't applied yet).
2. **L2a**: Update `opencode.json` permission blocks for the 5 read-only agents.
3. **L2b**: Append the "Live progress tracking" section to all 11 write-capable agent prompts.
4. **L2c**: Create `.opencode/jobs.md` with the format + example.
5. **L3**: Run the test suite — all 150 + 6 = 156 tests should pass.
6. **L3.5**: Run verify-plan.py on plan-013 — all 10 checks should pass.
7. **L4**: Archive + log + commit + push.

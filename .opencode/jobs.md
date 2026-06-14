# Jobs (live progress)

> Auto-managed by subagents. Do not edit by hand. See
> `.opencode/plans/completed/plan-013-design.md` for the design and
> `.opencode/plans/completed/plan-013-live-progress-tracking.md` for
> the implementation plan.

## Format (read this before writing)

Each entry is one subagent dispatch. Use this exact shape:

```markdown
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

**Machine-parseable fields** (for `verify-plan.py` and other tooling):
- `Status` — one of: `pending`, `in_progress`, `complete`, `failed`, `blocked`
- `Started` — ISO 8601 timestamp
- `Last update` — ISO 8601 timestamp
- `Current step` — free-text one-liner
- `Sub-steps` — checkbox list (`[x]`, `[~]`, `[ ]`)
- `Notes` — free-text (optional)

The header `## [<plan-id>] @<agent> - <task summary>` is parsed as:
- `<plan-id>` — matches `plan-\d+` or the word `adhoc`
- `<agent>` — must match one of the 13 agent names in `opencode.json`
- `<task summary>` — free-text, min 10 chars

**3 update rules:**

1. **Start** — append a new entry. Status: `in_progress`. Started: now. Current step: 1-line description. Sub-steps: first one is `[~]`, rest are `[ ]`.
2. **As you work** — update `Last update` (now) and `Current step` (what you're doing). Flip a sub-step from `[ ]` to `[~]` when you start it; flip `[~]` to `[x]` when you finish it. Aim for 1-3 updates per entry total.
3. **Finish** — Status: `complete` (or `failed`/`blocked`). Mark the last sub-step `[x]`. The `Last update` is your finish timestamp.

**Keep entries short.** jobs.md is for live status, not detailed logs. Use work-log.md for the post-plan summary.

**The header uniquely identifies an entry.** The pair `(<plan-id>, @<agent-name>)` is unique per dispatch. No agent overwrites another agent's entry; each agent appends a new entry and updates its own.

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

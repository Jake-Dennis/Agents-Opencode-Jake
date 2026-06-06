# Plan 009 design: per-agent safety primitives

## Context

Plan 009 adds three production-grade safety and cost-control primitives
to `opencode.json` for all 13 agents defined in `AGENT-ROLES.md`:
**`steps`** (cap on agentic iterations per task), **`permission.task`**
(deny-all to prevent subagent recursion), and **`compaction.prune`**
(opt into token savings on long sessions). All three are config-only
and additive — no prompt changes, no behavior change in the happy
path. The eight lifecycle phases from `AGENT-ROLES.md`
(Orchestration, Planning, Implementation, Review, Documentation,
Operations, Read-only search, Specialized) are the basis for sizing
`steps` per agent. The third primitive closes a soft gap in ADR-004's
design: the ADR names the conductor as the sole dispatcher (7 reserved
actions: commit, push, archive, manifest edit, `opencode.json` edit,
install scripts), but subagent-to-subagent dispatch is still possible
upstream via the `task` tool. `permission.task: {"*": "deny"}` enforces
that boundary in JSON rather than relying on prompt prose.

## `steps` matrix

| Agent | steps | Reasoning (cite AGENT-ROLES phase) |
|-------|-------|-----|
| conductor | 50 | Orchestration: dispatch + verify + commit is ~10–30 steps in normal use; 50 has headroom for plans with 4–5 layers plus post-dispatch review/commit. |
| planner | 30 | Planning: analysis-only; bounded by section count of the plan (Context, Tasks, Risks, Files). 30 forces concise plans; a sprawling plan is a sign it should be split. |
| architect | 30 | Planning: design-only; bounded by ADR/design-doc length (Components, Data Model, API Contracts, Tradeoffs). Mirrors planner. |
| builder | 100 | Implementation: heaviest worker (multi-file edits, dep install, test runs, debug cycles). 100 supports 2–3 retry loops on test failures within a single dispatch. |
| reviewer | 20 | Review: mechanical checklist; runs `verify-plan.py` then reads diffs of changed files. Should be a short, deterministic pass. |
| tester | 50 | Review: writes tests + runs them + iterates on failures. 50 supports one or two failure-rerun cycles. |
| docs | 30 | Documentation: reads code + writes markdown; bounded by file count. 30 is enough for a README plus a couple of API docs in one dispatch. |
| debugger | 40 | Operations: reproduce + isolate + fix + add regression test. 40 supports a binary-search "comment out half" loop without exhausting mid-diagnosis. |
| refactor | 50 | Implementation: multi-step refactor + run tests after each change + iterate. Symmetric with builder's per-step test pattern, but fewer files touched. |
| git | 10 | Operations: commit/push/PR is short (status, diff, add, commit, push, optional PR). 10 has headroom for a "verify the commit landed" loop. |
| explorer | 20 | Read-only search: grep/glob/Read/graphify query; bounded by the number of files examined. Read-only, so loops are not a runaway risk. |
| security | 40 | Specialized: read code + optional CVE lookup + write report. 40 supports a thorough audit without becoming a parallel `@builder`. |
| perf | 40 | Specialized: profile + identify + measure + fix. 40 supports the before/after measurement cycle. |

All values accept the plan's proposed defaults. No adjustments.

## `permission.task` policy

**Recommendation: `"task": {"*": "deny"}` on all 13 agents (uniform).**

The conductor is the sole dispatcher per ADR-004 — subagent invocation
of other subagents violates the dispatch architecture and creates
recursion risk. Per OpenCode semantics, "When set to deny, the subagent
is removed from the Task tool description entirely, so the model won't
attempt to invoke it." This is the load-bearing primitive: it turns the
conductor's prompt-level dispatch discipline into a JSON-enforced
boundary. Future plans may open specific edges (e.g., `builder → tester`
for self-verifying loops) by replacing `*` with a narrower pattern; the
safe default is deny-all.

Conductor and planner are `mode: primary`, so the `task` field is moot
for them — primaries are not invoked via the task tool from other
agents. Applying it uniformly is the no-surprise default: any agent
that later has its mode changed (e.g., to allow the planner to be used
as a subagent) inherits the deny policy automatically, with no audit
gap.

**String form vs object form (audit of `opencode.json`):** none of the
13 agents currently use the string form `"permission": "deny"`. All 12
non-conductor agents have an object-form `permission` block, and the
conductor has no `permission` block at all. The builder's job is
therefore simple: 12 agents need a new key added, 1 agent needs a fresh
block. No string-form conversion is needed. See the edge-cases section
below for the exact diff per agent.

## `compaction` block

**Recommendation:** `"compaction": {"auto": true, "prune": true}` at
the top level of `opencode.json`.

`auto: true` is the upstream default; making it explicit is
documentation-as-code — the next reader of `opencode.json` sees
"compaction is on" without having to consult the schema. `prune: true`
opts into token savings (upstream default is `false`): old tool outputs
are dropped during context compaction, which is the largest single
source of context bloat on long sessions.

We leave `tail_turns`, `preserve_recent_tokens`, and `reserved` at
upstream defaults — no project-specific need has surfaced to override
them. The plan-007 work-log already references the conductor's
auto-compaction behavior; making it explicit here is a no-op
behaviorally and a clarity win for the next maintainer.

## Edge cases the builder needs to know

- **String-form `"permission": "deny"`:** none found. Verified by
  reading every agent block in `opencode.json` (lines 34–151). No
  conversion needed.
- **Object-form `permission` (12 agents):** add `"task": {"*": "deny"}`
  as a new key. Do not touch existing `read`/`edit`/`bash` keys.
  - `git` (lines 114–119) is the most complex existing case:
    `{"bash": {"git *": "allow", "*": "deny"}}` must end up as
    `{"bash": {"git *": "allow", "*": "deny"}, "task": {"*": "deny"}}`
    — the bash key is preserved verbatim.
  - `security` and `refactor` have `bash: "ask"` — preserved as-is.
- **No `permission` block (1 agent):** `conductor` (lines 34–38). Add
  a fresh `"permission": {"task": {"*": "deny"}}` block.
- **Top-level `compaction`:** add a new top-level key. Suggested
  placement: between the `mcp` block (ends line 32) and the `agent`
  block (starts line 33), or after the `agent` block (ends line 152).
  The conductor's style is loose; pick one and be consistent with
  surrounding keys.
- **JSON validity:** the builder must run
  `python -c "import json; json.load(open('opencode.json')); print('valid')"`
  after the edit. The plan's verification step #1 covers this.

## Alternatives considered

**Per-agent `task` allow-lists** (e.g., `{"builder": "allow", "*": "deny"}`
on `tester`): rejected. ADR-004's 7 conductor-only reserved actions give
no concrete use case for subagent-to-subagent edges today, and an empty
allow-list is a future-work artifact. The deny-all default is the
no-surprise starting point; opening edges is a one-line change later
and is a separate decision per edge.

**Higher `steps` values** (e.g., `builder: 200`, `conductor: 100`):
rejected. The plan's values already give 2–3x headroom over typical
use; doubling them trades a small per-task safety margin
(runaway-loop protection) for a real cost risk on long sessions. If a
future plan needs more headroom, raise the cap then — the cost of
"I needed 110 and got capped at 100" is one retry, the cost of "ran
200 steps on a confused agent" is a token bill.

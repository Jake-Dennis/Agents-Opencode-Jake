# ADR-004: Explicit agent role boundaries via `AGENT-ROLES.md`

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Jake Dennis (conductor session), @docs (authoring)
- **Related:** `AGENT-ROLES.md` (this ADR's deliverable), `AGENTS.md`
  (project onboarding doc), `opencode.json` (agent registry, the
  enforced source for `permission` blocks), `.opencode/decisions/adr-001-json-only-agents.md`
  (single-source-of-truth rationale that this ADR builds on)

## Context and Problem Statement

The 13 agents in this project each carry a `description` and a
`prompt` in `opencode.json`, plus a `permission` block that constrains
which tools they may use. That is the **enforced** boundary: a
subagent that does not have `edit: "allow"` in its `permission`
block physically cannot write files, regardless of what its prompt
tells it to do. The `permission` blocks were set per-agent in the
JSON-only consolidation (ADR-001) and are tested by
`tests/test_schema.py` and exercised by the opencode CLI at every
`run --agent` invocation.

What `opencode.json` does **not** say is which agent **owns** which
phase of the workflow. The conductor is documented in `AGENTS.md` as
"the default primary agent for this project," and the other 12
agents are listed with one-line "When to use" entries. But nothing
in the repo spells out:

* Which lifecycle phase each agent belongs to (Orchestration,
  Planning, Implementation, Review, Documentation, Operations,
  Read-only search, Specialized).
* What each agent's **boundaries** are — i.e. the actions it is
  expected to take, the actions it is forbidden to take even if a
  human asks, and which actions are reserved for the conductor
  (committing, pushing, archiving plans, modifying the manifest,
  modifying `opencode.json`).
* How a new agent should be added to the project (register in
  `opencode.json`, document the role boundary in the table, run
  `verify-plan.py` to confirm the rest of the project still parses).

This is implicit in three places that drift: the conductor's
prompt, the per-agent prompts (which contain the boundaries in
prose), and the project onboarding doc (`AGENTS.md`). A reader
joining the project has to triangulate between the three to answer
"what is the tester's job, exactly, and what is it not allowed
to do?"

The risks of leaving this implicit:

* **Conductor drift.** Subagents that have `edit: "allow"` can
  technically archive a plan to `plans/completed/`, commit it, or
  push it. Nothing in the code prevents a subagent from doing the
  conductor's job if its prompt accidentally tells it to. The
  conductor's prompt ("step 9: Archive — move verified-complete
  plans to `.opencode/plans/completed/`") is the only thing
  keeping `@builder` from archiving its own work. This is a
  workflow stability risk, not a security one, but it is real.
* **Onboarding friction.** A new contributor has to read
  `opencode.json` (179 lines), `AGENTS.md` (108 lines), and the
  conductor's prompt to build a mental model of who owns what. The
  "read the source" approach is fine for maintainers; it is
  hostile to new contributors and to other agents (e.g. the
  conductor itself, which has to dispatch by name) that need a
  canonical role table to consult.
* **Drift between `permission` and `prompt`.** The `permission`
  block in `opencode.json` is enforced; the boundaries written in
  the per-agent `prompt` are not. A prompt edit can quietly
  contradict the `permission` block (e.g. telling `@security` to
  "fix the SQL injection" when it is `edit: "deny"`), and the
  conflict is invisible until a reviewer catches it. The
  permissions are checked by the opencode CLI; the prompts are
  not. A canonical table that names both is a forcing function
  for the two to stay in sync.
* **Inability to extend safely.** Adding a 14th agent today means
  "register in `opencode.json`, write a long prompt, hope the
  conductor picks the right one." A role table makes "register
  the agent, add a row to the table, document the boundary" a
  three-step checklist that any contributor can follow.

We need a single, project-root, markdown document that names each
agent, its lifecycle phase, its allowed actions, its forbidden
actions, and the conductor-owned actions it must not perform. The
document is a **reference**, not a replacement for
`opencode.json` — the JSON is still the enforced source for
`permission` blocks. The doc is the **comment** that
`opencode.json` should have had.

## Considered Options

1. **Write `AGENT-ROLES.md` as a table-based reference at the
   repo root** (chosen). A single markdown file with a roster
   table and a cross-cutting-boundaries section. Lives next to
   `AGENTS.md` and `opencode.json`, references both.
2. **Enforce role boundaries in code via expanded `permission`
   blocks in `opencode.json`.** Add per-agent `role: "..."`
   fields, or wrap the opencode CLI to refuse certain bash
   patterns by agent name. Tighter, but more invasive and harder
   to maintain.
3. **Keep roles implicit.** Status quo — the conductor's prompt,
   the per-agent prompts, and `AGENTS.md` describe the roles in
   prose. No canonical table.

## Decision Outcome

**Chosen option: 1 — `AGENT-ROLES.md` at the repo root.** A
markdown reference document that:

* Names each of the 13 agents.
* Assigns each agent to exactly one of the eight lifecycle
  phases: Orchestration, Planning, Implementation, Review,
  Documentation, Operations, Read-only search, Specialized.
* Lists the actions each agent is **expected** to take
  (the `Can` column — the conductor's delegation contract) and
  the actions each agent is **forbidden** to take even if a
  human or the conductor asks (the `Cannot` column — the
  per-agent `permission` block in prose).
* Documents the **cross-cutting** boundary: which actions are
  reserved for the conductor (committing, pushing, archiving
  plans, modifying the manifest, modifying `opencode.json`,
  running install scripts), and which actions are allowed to
  every agent (read the project, use graphify, dispatch other
  subagents via `@mention`).
* Documents the **extension contract**: adding a new agent is
  "register in `opencode.json`, document the role in the table,
  run `python scripts/verify-plan.py` to confirm nothing else
  broke."

The file is **`AGENT-ROLES.md`** at the repo root, sibling to
`AGENTS.md`. The naming follows the project's existing
uppercase-with-dashes convention for top-level docs
(`AGENTS.md`, `README.md`).

The document does **not** replace `opencode.json` — the JSON is
still the enforced source for `permission` blocks, the JSONC
merge helper, the test schema, and the opencode CLI's agent
registry. `AGENT-ROLES.md` is the **human-readable comment** that
describes the *intent* of those `permission` blocks. The
`verify-plan.py` script (mentioned in the reviewer's prompt as
the mandatory pre-review step) and the pre-commit hook both
still pass on a `AGENT-ROLES.md`-only change; the file is
additive, not load-bearing.

## Why a markdown table and not a machine-readable manifest

The natural objection is: "shouldn't this be a JSON file the
conductor can parse at runtime?" The answer is no, for three
reasons:

1. **The conductor already has the source of truth at hand.**
   `opencode.json` is loaded by opencode at session start. The
   `permission` blocks are already machine-readable. A
   `AGENT-ROLES.md` table that duplicates the same data in
   another format would violate ADR-001's single-source-of-truth
   principle, and the two files would drift.
2. **The role boundaries are not runtime data.** A subagent does
   not consult a role table to decide what to do — its own
   prompt already lists its boundaries, and the opencode CLI
   enforces the `permission` block. The role table is for
   *humans*: maintainers, new contributors, and the conductor
   when it has to pick which subagent to dispatch to. Markdown
   with a rendered table is the right surface for that audience.
3. **A `verify-plan.py` run can catch schema breakage, but it
   cannot catch a stale prose description.** If
   `AGENT-ROLES.md` and `opencode.json` disagree, the JSON wins
   (the opencode CLI is the enforcer) and the markdown is a
   bug. The doc is advisory; the JSON is authoritative. Making
   the doc machine-readable would create a false sense of two
   equal sources of truth.

The role boundaries in `AGENT-ROLES.md` are kept in sync with
`opencode.json` by review (the `@reviewer` agent reads both
before approving a plan that adds or changes an agent) and by
the "How to extend" section in `AGENT-ROLES.md` itself, which
tells the contributor to update **both** files in a single
change.

## Consequences

### Positive

* **One place to look up "who does X."** A new contributor
  reading `AGENT-ROLES.md` can answer "which agent writes
  tests?" ("`@tester`"), "which agent commits?" ("nobody except
  the conductor"), and "which agent is read-only?" ("`@planner`,
  `@architect`, `@reviewer`, `@security`, `@explorer`") without
  reading the per-agent prompts.
* **Forces `permission` blocks and prompts to agree.** The
  reviewer's pre-approval step (which the opencode CLI already
  enforces as `python scripts/verify-plan.py <plan-file>`) can
  be extended in a follow-up ADR to also diff
  `AGENT-ROLES.md` against `opencode.json` and reject on
  disagreement. The data is there; the enforcement hook is not
  (yet).
* **Self-documenting extension contract.** The "How to extend"
  section in `AGENT-ROLES.md` turns "add a 14th agent" into a
  three-step checklist: register in `opencode.json`, add a row to
  the table, run `verify-plan.py`. No hidden knowledge.
* **Conductor drift is now visible.** The cross-cutting
  boundaries section names the actions that only the conductor
  may take. A reviewer who sees `@builder` proposing a commit
  message can point at the doc and say "this is in the
  conductor-only column, dispatch `@git` or ask the conductor."
* **ADR-format record of the decision.** This ADR records the
  rationale (why a table, why markdown, why not in-code
  enforcement) so a future maintainer who finds the table
  redundant can read why it exists before deleting it.

### Negative

* **A second source of truth — by design.** `AGENT-ROLES.md` and
  `opencode.json` describe overlapping information. They are
  kept in sync by review, not by tooling. Drift is possible; the
  mitigation is that the JSON is authoritative and the
  `verify-plan.py` schema check catches any opencode-side break
  regardless of the doc.
* **Bigger surface for the conductor to maintain.** The
  conductor's prompt gains a new responsibility: when adding or
  changing an agent, update both `opencode.json` and
  `AGENT-ROLES.md`. The conductor's existing step 10
  ("Document — work-log, ADRs, project docs, graphify rationale")
  covers this — the doc is project documentation — but it is a
  new item the conductor has to remember to do.
* **The doc is opinionated.** The lifecycle phases
  (Orchestration, Planning, Implementation, Review,
  Documentation, Operations, Read-only search, Specialized) are
  a project-local taxonomy. A new contributor who comes from a
  different multi-agent framework may use different phase names
  (e.g. "Coordinator / Planner / Executor / Verifier" instead
  of our eight). The doc does not apologize for this; it
  documents the project's choice.
* **The 13-row table is static.** When a 14th agent is added,
  `AGENT-ROLES.md` must be updated by hand. There is no
  generator. A future improvement could write a small Python
  helper that reads `opencode.json` and emits a stub
  `AGENT-ROLES.md` row to be hand-edited, but that is out of
  scope for this ADR.
* **No enforcement of the cross-cutting boundaries in code.**
  The doc says "no subagent should commit, push, modify the
  manifest, modify `opencode.json`, archive plans." A subagent
  with `edit: "allow"` and `bash: "allow"` can technically do
  all of those; the doc relies on the subagent's prompt and the
  conductor's dispatching discipline to prevent it. The
  alternative (option 2 in Considered Options) would close this
  gap with code, at the cost of maintenance burden. The
  tradeoff is documented; a future ADR can revisit it if drift
  becomes a real problem.

### Mitigations

* **Drift between doc and JSON:** the reviewer's
  `verify-plan.py` step can be extended in a follow-up ADR
  to read both files and warn on `permission` ↔ role
  disagreements. Logged as an open question below.
* **Conductor forgetting to update the doc:** the
  `verify-plan.py` hook can be extended (same as above) to
  detect "agent registered in `opencode.json` but not in
  `AGENT-ROLES.md`" and reject the change. Out of scope for
  this ADR; the doc's "How to extend" section is the human-
  readable nudge.
* **The doc falling out of date as the project evolves:**
  the doc is in the same git repo as `opencode.json`; a PR
  that changes the JSON without changing the doc will be
  caught by `@reviewer` (which the conductor's workflow
  dispatches as step 7). The doc is a first-class artifact
  of the conductor's step 10.

## Confirmation

The decision is confirmed by:

* The file `AGENT-ROLES.md` exists at the repo root and lists
  all 13 agents, their modes (primary / all), their lifecycle
  phases, their `Can` / `Cannot` columns, and the
  cross-cutting boundaries.
* A grep across the file for the 13 agent names (`conductor`,
  `planner`, `builder`, `architect`, `reviewer`, `tester`,
  `docs`, `debugger`, `refactor`, `git`, `explorer`, `security`,
  `perf`) returns 13 hits — one per agent.
* A grep across the file for the seven conductor-only actions
  (`commit`, `push`, `archive`, `manifest`, `opencode.json`,
  `install`, `permission`) returns hits in the cross-cutting
  boundaries section.
* `python scripts/verify-plan.py` exits 0 on a no-op plan
  after the doc is added (the doc is markdown, so the script
  should not be affected — this is the regression check).
* The conductor's prompt is unchanged (the doc supplements the
  prompt; it does not replace it). The "How to extend" section
  is referenced from the conductor's step 10 by the reviewer
  on the next agent-addition PR.

## Alternatives Considered

1. **Expand `permission` blocks in `opencode.json` to express
   the role boundaries in code.** Add a `role` field per agent
   (`"role": "planner"`, `"role": "reviewer"`, etc.) and have
   the opencode CLI refuse certain bash patterns by role (e.g.
   a `planner` cannot `git commit`; a `git` agent cannot edit
   source files). Optionally wrap the opencode CLI with a
   pre-dispatch hook that re-checks the role boundary.
   *Rejected:* the opencode CLI's `permission` system already
   supports fine-grained per-tool and per-pattern rules. Adding
   a `role` layer on top of that is a parallel permission
   system. Maintaining two systems means twice the config to
   keep in sync, twice the tests to write, and no guarantee
   the two agree. The current `permission` blocks are
   sufficient for tool-level enforcement; the role layer adds
   *workflow* enforcement that is better expressed in prose
   and dispatch discipline than in code. ADR-001 already chose
   "JSON-only" for similar single-source-of-truth reasons.
   A future ADR can revisit if a real drift incident occurs.

2. **Keep roles implicit (status quo).** The conductor's
   prompt, the per-agent prompts, and `AGENTS.md` already
   describe the roles in prose. No canonical table.
   *Rejected:* this is the bug we are fixing. The implicit
   roles are spread across three files that drift; a new
   contributor has to triangulate to answer basic questions
   ("which agent writes tests?", "which agent commits?",
   "which agent is read-only?"). The conductor drift risk
   (a subagent with `edit: "allow"` archiving its own plan)
   is invisible without a canonical reference. Keeping the
   status quo means accepting those costs indefinitely.

3. **Embed the role table inside `AGENTS.md`.** Add a section
   to the existing onboarding doc instead of a new file.
   *Rejected:* `AGENTS.md` is a quick-start / onboarding
   doc; it lists the agents in a one-line "When to use"
   table. The role-boundary table is ~80 lines and would
   bloat the onboarding doc past its purpose. Splitting the
   two lets `AGENTS.md` stay scannable for new contributors
   and lets `AGENT-ROLES.md` be a deep reference for
   maintainers and the conductor's dispatch logic. `AGENTS.md`
   links to `AGENT-ROLES.md` for the full table.

4. **Use a per-agent `.md` file in `.opencode/agents/`** (one
   file per agent with role, can, cannot, owned by). *Rejected:*
   ADR-001 already chose JSON-only to eliminate the
   two-sources-of-truth merge bug (the `mode: subagent` in
   `.md` frontmatter silently demoting the `mode: primary` in
   JSON). Re-introducing per-agent `.md` files would walk that
   back. The single file `AGENT-ROLES.md` is the markdown
   equivalent — one file, one source of truth for the doc —
   and lives at the repo root rather than under `.opencode/`
   so it is visible to humans browsing the repo, not just
   to opencode scanning its config dir.

5. **Use a YAML file (e.g. `.opencode/roles.yaml`) instead of
   markdown.** *Rejected:* YAML is the wrong surface for the
   audience. The role table is for humans (maintainers,
   contributors, the conductor's dispatch logic), and a
   markdown table renders in every GitHub PR view, IDE
   preview, and terminal pager. YAML would require a
   parser, a renderer, or a GitHub-specific plugin. The
   project already uses markdown for `AGENTS.md`,
   `README.md`, `AGENT-ROLES.md`, ADRs, and plans; staying
   in markdown matches the project's existing doc style.

## Pros and Cons of the Options (re-listed for the record)

### Chosen: `AGENT-ROLES.md` table at the repo root

* **Good:** one place to look up "who does X"; forces
  `permission` and prompt to agree (advisory, not
  enforced); self-documenting extension contract;
  matches the project's existing markdown-on-disk style.
* **Good:** lives next to `AGENTS.md` and `opencode.json`,
  so a contributor reading any of the three finds the
  other two.
* **Bad:** second source of truth — `AGENT-ROLES.md` and
  `opencode.json` describe overlapping information and
  must be kept in sync by review.
* **Bad:** the cross-cutting boundaries (no subagent
  commits, etc.) are advisory, not enforced in code. A
  subagent with `edit: "allow"` can technically do all
  of the conductor-only actions.
* **Bad:** the 13-row table is static; a new agent means
  a hand edit. No generator.

### Alternative: expanded `permission` blocks in code

* **Good:** tighter — role boundaries are enforced by the
  opencode CLI, not by prompt prose.
* **Good:** no second source of truth; `opencode.json`
  is the only file.
* **Bad:** two parallel permission systems
  (tool-level + role-level) to maintain and test.
* **Bad:** the opencode CLI is upstream; we cannot add
  a `role` field to it. The wrapper approach is
  invasive and would have to track CLI changes.
* **Bad:** misses the human-audience problem the doc
  solves. A role table is for maintainers, not for the
  CLI.

### Alternative: keep roles implicit (status quo)

* **Good:** zero new code; zero new doc; zero new
  maintenance.
* **Good:** the conductor's prompt and the per-agent
  prompts already cover the boundaries in prose.
* **Bad:** implicit boundaries drift between the
  conductor's prompt, the per-agent prompts, and
  `AGENTS.md`.
* **Bad:** new contributors cannot answer "which agent
  does X?" without reading three files.
* **Bad:** conductor drift (a subagent doing the
  conductor's job) is invisible.

## References

* `AGENT-ROLES.md` — this ADR's deliverable, the role
  reference table at the repo root.
* `AGENTS.md` — the project onboarding doc; now links
  to `AGENT-ROLES.md` for the full role table.
* `opencode.json` — the 13-agent registry, the
  **enforced** source of truth for `permission` blocks.
  `AGENT-ROLES.md` is the human-readable comment for
  this file.
* `.opencode/decisions/adr-001-json-only-agents.md` —
  the prior decision (single source of truth in JSON)
  that this ADR builds on.
* `.opencode/decisions/adr-002-global-setup-merge-strategy.md`
  and `.opencode/decisions/adr-003-graphify-auto-refresh.md`
  — the two most recent ADRs; this ADR follows the same
  format.
* `scripts/verify-plan.py` — the pre-review and
  pre-commit gate mentioned in the conductor's
  workflow. A future ADR may extend this script to
  also diff `AGENT-ROLES.md` against `opencode.json`
  and warn on `permission` ↔ role disagreements;
  out of scope here.
* `AGENTS.md` "Workflow" section — the conductor's
  15-step workflow; step 10 ("Document") is where
  `AGENT-ROLES.md` updates land when an agent is
  added or changed.
* `~/.config/opencode/opencode.jsonc` — the
  user-scope opencode config that the
  `opencode_jsonc_merge.py` helper writes when
  `global-setup.bat` runs. Contains the same 13
  agents after install; the merge helper is
  `permission`-block-aware (per ADR-002).

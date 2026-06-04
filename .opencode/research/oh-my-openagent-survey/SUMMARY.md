# `oh-my-openagent` Survey — Synthesis for Adoption

**Surveyed repo:** https://github.com/code-yeongyu/oh-my-openagent (branch `dev`, snapshot 2026-06-05). The npm package is still published as `oh-my-opencode`; both names refer to the same project (mid-rename).

**Purpose of this doc:** Distill four 1-2 page light surveys into one decision-ready summary. Verdict target: should any idea from `oh-my-openagent` be adopted into **Agents-Opencode-Jake**?

**Project priorities of Agents-Opencode-Jake** (the lens for every verdict below):
1. **Single-model** — one provider/model, no routing layer.
2. **Auditability** — every state change is inspectable post-hoc.
3. **Plan-as-artifact** — implementation plans live as markdown files, not JSON blobs.
4. **ADRs** — architectural decisions recorded in `.opencode/decisions/adr-NNN-*.md`.
5. **Mechanical verify gates** — verification is programmatic, not prompt-driven.

---

## 1. TL;DR

- **All four surveyed ideas are weak fits for this project.** Three of them (team-mode, category-routing, notepads) explicitly encode a multi-agent/multi-model philosophy that is the opposite of Agents-Opencode-Jake's single-model stance. The fourth (boulder.json) overlaps with artifacts the project already maintains in markdown form.
- **The closest thing to a transferable idea is the "per-worktree, file-based orchestrator state" pattern itself** — but the project already does this with `.opencode/todo.md`, `.opencode/work-log.md`, and `.opencode/plans/plan-NNN-*.md`. The boulder.json *implementation* (a single JSON file with `works` map and timers) would be a regression toward opaque state, not a step forward.
- **Three of the four systems rely on prompt-instruction to enforce their contracts** (notepad appends, boulder resume, category fallback). This is the exact anti-pattern Agents-Opencode-Jake rejects via its "mechanical verify gates" priority.
- **Two of the four systems are mid-rename** (`.sisyphus/` → `.omo/`, and the boulder.json agent field uses names like `atlas`/`sisyphus` that the user's project doesn't share). Adopting them as-is would inherit cosmetic churn.
- **Recommendation: do not adopt any of the four.** A more productive use of time is to extract the *one* mechanism that does align — atomic file writes for `.opencode/todo.md` and a multi-work `works` map for parallel plans — as a small, markdown-native enhancement to the existing plan-as-artifact system. That's a separate design exercise and does not require copying boulder.json.

---

## 2. Per-area key findings

### 2.1 `boulder.json` — per-worktree orchestrator state ([boulder.md](./boulder.md))

A single JSON file at `<worktree>/.sisyphus/boulder.json` (or `.omo/` on newer code) that tracks the currently active plan markdown, a `works` map of past/active works, session IDs that have rolled the boulder, per-task timers, and worktree binding. Schema is v2 (additive on v1). Writes happen on explicit function calls (`createBoulderState`, `appendSessionId`, `upsertTaskSessionState`, `startTaskTimer`, `endTaskTimer`, `completeBoulder`); reads return `null` on any parse error and the system silently starts fresh. Resume is **not** automatic — the user must run `/start-work`, which detects an existing boulder and either auto-resumes (single work) or presents a list (multiple works).

The interesting design move is the **decoupling of plan progress from the JSON state**: progress is computed by parsing `- [x]` / `- [ ]` checkboxes in the plan markdown, not by storing counters in boulder.json. The JSON is a small index/timer, not a duplicate of the plan. The honest gaps (no atomic write, mid-rename path, prompt-driven vs programmatic edge cases) are real and the survey's own source code contradicts its own auto-generated `AGENTS.md` on the atomic-write claim.

### 2.2 `team_mode` — multi-agent mailbox orchestration ([team-mode.md](./team-mode.md))

A 12-tool feature (`team_create`, `team_delete`, `team_send_message`, `team_task_create`, `team_status`, etc.) that lets a "lead" agent spawn up to 8 member agents, each in its own opencode session, and coordinate them through a shared mailbox (per-member inbox directories under `~/.omo/runtime/{teamRunId}/inboxes/`). Members claim tasks from a shared task list, deliver messages via two paths (durable inbox file + best-effort live `promptAsync`), and shut down via a 3-step handshake (`shutdown_request` → `approve_shutdown` / `reject_shutdown`). Schema-enforced caps: 8 members max, 4 in flight at spawn time, 256 KB unread per inbox, 500 turns per member, 120-min wall clock per run. Optional tmux pane integration (`team_mode.tmux_visualization: true`) gives each member a visible TUI. Storage layout is well-defined: `~/.omo/teams/{name}/config.json` for declared specs, `~/.omo/runtime/{teamRunId}/` for runtime state.

The feature is **OFF by default**, opt-in via JSONC, restart required. The orchestration is heavyweight: 8 submodules in `src/features/team-mode/`, a per-team runtime state machine (`creating | active | shutdown_requested | deleting | deleted | failed | orphaned`), and a hardcoded agent-eligibility registry that hard-rejects 7 agents (Oracle, Librarian, Explore, etc.) from being team members. There is **no voting / consensus primitive in team-mode itself**; the repo has a separate `src/features/consensus/` that is unrelated.

### 2.3 Notepads — plan-scoped append-only memory ([notepads.md](./notepads.md))

Five markdown files per plan at `.sisyphus/notepads/{plan-name}/` (or `.omo/notepads/...` per recent code): `learnings.md`, `decisions.md`, `issues.md`, `verification.md`, `problems.md`. Sisyphus-Junior is the primary writer, told via its default delegation prompt to "ALWAYS APPEND — never overwrite or use Edit tool." Atlas reads `learnings.md` between tasks and passes a digest to the next subagent. There is **no size limit, no rotation, no truncation, no automated promotion to `AGENTS.md` or `CLAUDE.md`** — the maintainer's RFE #1397 gestures at this but it is unimplemented. The directory is gitignored by design and considered ephemeral / safe to drop.

The pattern is **prompt-instructed, not data-driven**. The "extract learnings → pass forward to next subagent" loop runs only because Atlas' prompt tells it to. A weaker Atlas model may skip the synthesis step and the next subagent starts blind. The directory is keyed by plan name, so cross-plan knowledge is never accumulated unless a human copies entries out. The repo has no equivalent of a "learnings/memories" file at the user-home level; notepad scope is strictly per-project, per-plan.

### 2.4 Category-based model routing ([category-routing.md](./category-routing.md))

When an agent delegates work via `task(category="…")`, it names a *semantic* label (`visual-engineering`, `ultrabrain`, `deep`, `artistry`, `quick`, `unspecified-low`, `unspecified-high`, `writing`) — not a model. The harness resolves the string to a `provider/model` via a 6-step pipeline (UI selection → user config → category default → user fallback → hardcoded fallback chain → system default). Each category has a hardcoded `FallbackEntry[]` chain that tries multiple providers in priority order until one is reachable. Categories also carry a **per-category prompt-append** — so swapping Claude for GPT in `deep` auto-loads the GPT-tuned deep prompt at the same time. Users can override per category in `oh-my-openagent.json` under `categories:`.

The "dangerous-override detection" is **documentation-only**: a doc table of "safe vs dangerous" model swaps exists, but there is no runtime check, no warning emit, no UI banner when a user configures a known-bad model for a known-bad category. The maintainer's stance is "docs are the warning; the user is responsible." The eight categories deliberately map onto 4 cost tiers; `quick`'s last chain entry is `gpt-5-nano` (deliberately ultra-cheap), and `unspecified-high` is the most expensive possible default (Claude Opus) for unrecognized categories.

---

## 3. Adoption candidates — verdicts

### 3.1 `boulder.json` — **Weak fit**

**Why it doesn't match the project:** Agents-Opencode-Jake already has three artifacts that collectively do what boulder.json does:

- `.opencode/plans/plan-NNN-title.md` — the plan, which is *also* the progress source (checkboxes).
- `.opencode/todo.md` — the persistent cross-session task checklist, written by the conductor.
- `.opencode/work-log.md` — append-only audit log of every work cycle.

These are **markdown, not JSON**, which fits the "plan-as-artifact" and "auditability" priorities. They are human-inspectable, diff-friendly, and require no schema migration. Replacing them with a JSON state file would *reduce* auditability (a JSON blob is harder to skim than a markdown list) and *add* an atomic-write requirement the project doesn't currently have.

**The one transferable idea:** the `works` map — a single file holding multiple active works, with a v1/v2 schema-mirroring pattern. This could be adopted *in markdown* by extending `.opencode/todo.md` to list multiple work streams under stable work IDs, but this is an enhancement to the existing artifact, not a copy of boulder.json.

**Caveats from the survey to be aware of even if you don't copy it:**
- No atomic write in current code → torn JSON → silent fresh-start on next read.
- No `state: "interrupted"` field despite the maintainer wanting one (issue #1131).
- Path mid-rename (`.sisyphus/` → `.omo/`) — a smell that the location isn't stable yet.
- The `boulder.json` schema tracks session IDs and runtime state, which the maintainer explicitly refuses to commit (issue #2853) because it pollutes git history.

**Effort to copy verbatim:** Medium. ~1k LOC of storage + helpers + tests. Would require rewriting for markdown.

### 3.2 `team_mode` — **Weak fit**

**Why it doesn't match the project:** This is the most explicit mismatch of the four. Team mode is a **multi-agent, multi-model** orchestration system: 8 concurrent members, 12 dedicated tools, a shared mailbox, a per-team runtime state machine, and a hardcoded agent-eligibility registry. The conductor in Agents-Opencode-Jake is **single-model** and dispatches to subagents via `@mention` and the `task` tool — there is no shared mailbox, no per-team tmux layout, and no per-team runtime state.

Specific philosophical mismatches:

- **Multi-agent at the runtime layer, not just the prompt layer.** The project's subagents are roles in a single conductor session; team mode's members are independent opencode sessions with their own message history, worktrees, and turn counters.
- **Hardcoded 8/4/256KB/500/120 caps** would need to be re-justified for a single-model project that has no provider-fallback story to defend against.
- **The `AGENT_ELIGIBILITY_REGISTRY` hard-rejects 7 agents** from being team members — a heavy opinion about which agents are "team-shaped" that doesn't apply here.
- **Opt-in, restart-required feature** with 12 new tools is a significant UX surface to add for no clear win.

**Verdict:** Skip entirely. The patterns that could be loosely applicable (agent-to-agent messaging, shared task list) are not load-bearing for the project. If multi-agent coordination becomes a need, design a markdown-native version from scratch.

### 3.3 Notepads — **Weak fit**

**Why it doesn't match the project:** The five-file notepad system (`learnings`, `decisions`, `issues`, `verification`, `problems`) maps almost one-to-one onto artifacts the project already maintains:

| Notepad file | Existing project equivalent |
|---|---|
| `decisions.md` | `.opencode/decisions/adr-NNN-*.md` (ADRs — but with stricter schema and git-tracked) |
| `issues.md` (friction log) | `.opencode/work-log.md` (append-only audit log) |
| `verification.md` | Plan-as-artifact includes verification steps; `@tester` and `@reviewer` produce test reports |
| `problems.md` (unresolved) | Unresolved items belong in plan markdown or in the work-log |
| `learnings.md` | (no direct equivalent — see below) |

The one notepad file with **no clean project analog** is `learnings.md`. But the notepad system's approach to it — **prompt-instructed append-only markdown with no automated promotion** — is the wrong shape. The project's "mechanical verify gates" priority rejects "the subagent decided to write it" as an enforcement mechanism. If cross-task learning matters, it should be promoted to a *committed* artifact (AGENTS.md update, ADR addition, or a new `.opencode/learnings/` directory) by a mechanical step, not left as ephemeral markdown at the bottom of a plan folder.

**Additional reasons it's a weak fit:**

- Path mid-rename (`.sisyphus/notepads/` → `.omo/notepads/`) — see risk callouts.
- No size limit, no rotation — a multi-day plan could append to `learnings.md` indefinitely.
- The RFE to automate promotion to AGENTS.md is unimplemented (issue #1397) — knowledge is dead-end data.
- The "no `learnings.json`" gap that the survey flags in §7 of boulder.md is a real omission in `oh-my-openagent` itself, not a reason to copy their workaround.

**Verdict:** Skip. The project already has stricter, more durable versions of 4 of the 5 notepad files. For the 5th (`learnings`), design a promotion step from plan/work-log to committed docs, not a parallel ephemeral store.

### 3.4 Category-based model routing — **Weak fit**

**Why it doesn't match the project:** The category-routing system exists *only* to abstract over multiple providers and models. The project is **single-model** by design (the top-level `provider.opencode.model` in `opencode.json` is set once and inherited by all agents). There is no provider-fallback requirement, no model-swap story, and no multi-model cost concern.

Specific philosophical mismatches:

- **8 categories × 6-step pipeline × per-category prompt-append × fallback chains** is a lot of machinery to maintain for a project that does not delegate across models.
- **The "dangerous override" detection is docs-only** — the maintainer explicitly refuses to enforce safety checks at runtime. The project's "mechanical verify gates" priority would reject this stance.
- **Category names like `visual-engineering`, `ultrabrain`, `artistry` carry cost-tier semantics** (`ultrabrain` → `gpt-5.5 xhigh`, `quick` → `gpt-5.4-mini`) that have no meaning when there is only one model.
- **The `requiresProvider` hard gate** (Hephaestus cannot activate without GPT access) is a multi-provider safety mechanism that the project doesn't need — its single model is always present or the project is broken anyway.

**Verdict:** Skip entirely. None of the abstraction is load-bearing for a single-model project. If a future need arises to switch providers, a one-line `opencode.json` change beats a 6-step pipeline.

---

## 4. Risk callouts

These are the surprising or concerning things surfaced by the four surveys, worth knowing about even if you don't adopt any of the ideas.

1. **Path mid-rename in flight.** Both `boulder.json` and notepads are mid-migration from `.sisyphus/` to `.omo/`. The docs still show `.sisyphus/`, the recent code (commit `f313eb1`) shows `.omo/`, and the auto-generated `AGENTS.md` for boulder-state shows `.omo/` while the actual `storage.ts` still writes to `.sisyphus/`. Any project adopting these patterns would inherit the churn.

2. **boulder.json `AGENTS.md` is out of sync with the code on `dev`.** The auto-generated doc claims atomic-write + file-lock; the actual `writeBoulderState` in `storage.ts` uses plain `writeFileSync`. This is a concrete instance of the "auto-generated docs are aspirational" failure mode — worth noting if you ever consider generating AGENTS.md for this project.

3. **No atomic write means silent fresh-start on torn JSON.** A process kill mid-write produces a corrupt `boulder.json`; the next read returns `null` and the system silently starts a new work. There is no backup, no recovery. This is exactly the kind of failure mode the project's "mechanical verify gates" priority would refuse to ship.

4. **Notepads are prompt-driven, not programmatically enforced.** The "ALWAYS APPEND — never overwrite" rule lives in the subagent's prompt. A weak/fast model for the executor can skip the append entirely, and the system has no detection for "the notepad was not written this cycle." The `notepad-write-guard` hook (commit `f313eb1`) prevents overwrites but does not enforce appends.

5. **Notepad knowledge is dead-end data.** RFE #1397 (RFC), issue #1364 (Session Debrief), and PR #4382 (durable notepad) all gesture at closing the loop, but **as of the surveyed snapshot no automated promotion to `AGENTS.md` / `CLAUDE.md` exists**. Cross-plan knowledge accumulation does not happen.

6. **team-mode has no consensus / voting primitive despite the doc title's vibe.** The 5-step lifecycle is "spawn → delegate → claim → shutdown → retire" — all CRUD, no quorum or merge-conflict resolution. The repo has `src/features/consensus/` but it is independent of team-mode.

7. **team-mode's `AGENT_ELIGIBILITY_REGISTRY` hard-rejects 7 agents** (`oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus`) from being team members. This is a heavy opinion about agent shape that doesn't apply to a project whose subagents are roles in a single conductor session.

8. **category-routing "dangerous overrides" are documentation-only.** The maintainer's stance is "the docs are the warning; the user is responsible." There is no `dangerous: true` flag, no warning emit, no UI banner. If a project copied this pattern, the decision *not* to enforce is baked into the design.

9. **category-routing "available models" set is sometimes empty on first run** — the pipeline then falls back to a connected-providers cache. This is a warm-up tax; a first-call latency spike is possible. Not relevant for a single-model project, but worth noting if you ever look at the pattern.

10. **boulder.json uses agent names (`atlas`, `sisyphus`) the user's project doesn't share.** The `agent` field in the schema is a freeform string. Copying the schema would mean either renaming your agents to match (bad) or carrying an empty/unused field (cosmetic debt).

11. **boulder.json schema is mid-evolution.** v1 is still on disk and still accepted; v2 is additive on top. Readers can't rely on `schema_version: 2` being present. Migrations are inline. A project adopting this would have to commit to the schema-mirroring pattern from day one.

---

## 5. Open questions

Gaps the four light surveys explicitly could not close, plus questions the user should consider before any future revisit.

1. **Are any of the four patterns meaningful when stripped of multi-model assumptions?** E.g. is there a single-model, single-conductor version of team-mode that doesn't carry the 8-member / 4-in-flight / 256KB-inbox / tmux-pane baggage? The surveys don't answer this because the source code is built around the multi-agent assumption.

2. **Does `oh-my-openagent` have a plan-as-artifact pattern that survives without boulder.json?** The plan markdown in `.sisyphus/plans/{name}.md` is the progress source, but the surveys don't characterize how plans are *created* (Prometheus is mentioned as the planner; the surveys note it is "READ-ONLY" but can create markdown in `.omo/`). A deeper read of `src/features/prometheus/` or the equivalent planning agent would tell us whether the planning discipline is transferable.

3. **What is the actual error rate of notepad appends under a "weaker" executor model?** Issue #2897 (cited in §6 of notepads.md) hints that prompt-driven synthesis can fail silently in parallel delegation. How often does it fail in practice? Without empirical data, the "prompt-instructed writes" anti-pattern can't be quantified.

4. **Is there a future where Agents-Opencode-Jake legitimately needs multi-model?** If a user is paying for a single API key, no. If a user has multiple keys and wants a cost-optimized routing layer, the category-routing pattern becomes relevant — but the project's current single-model stance would need to be explicitly reversed in an ADR first.

5. **Does the `works` map in boulder.json v2 actually solve a real problem in this project?** The project has only ever had one active plan at a time (per the workflow in AGENTS.md). The `works` map is a generalization the surveys note is "rationale for the `works` map" (issue #1774) but the surveys don't characterize how often users actually run multiple works in parallel. If never, the generalization is over-engineering.

6. **The survey of `category-routing.md` notes the orchestration doc lists `quick-rust`, `quick-zig`, `git` as "user-facing orchestration names" but these are absent from `CATEGORY_MODEL_REQUIREMENTS`.** The survey author flags this as an honest gap they could not close in a web-only survey. A local clone + grep would resolve it. Not relevant for adoption (single-model) but worth knowing for accuracy.

7. **`max_member_turns: 500` enforcement site is unverified** (team-mode.md §8). Not relevant for adoption but a reminder that the surveys are honest about what they could not confirm.

8. **boulder-state/ralph-loop handshake for `task_sessions` reuse** (boulder.md §8) was not fully traced. The "same subagent session is reused across iterations for the same top-level task to preserve context" feature lives in `ralph-loop/`, not in `boulder-state/`, and the resume path between them is uncharacterized. Not relevant for adoption but a reminder that the surveys are 1-2 page snapshots, not full reads.

---

## 6. Summary recommendation

**Do not adopt any of the four ideas verbatim.** The project's priorities (single-model, auditability, plan-as-artifact, ADRs, mechanical verify gates) are the structural opposite of the surveyed project's priorities (multi-model, prompt-instructed, JSON state, multi-agent runtime).

The single most productive follow-up — and a genuine improvement — is to take the **one transferable mechanism** (the multi-work `works` map from boulder.json v2) and re-implement it in **markdown**, as an extension to `.opencode/todo.md` and the existing plan-as-artifact system. That is a small, design-first exercise, not a copy. It would let the conductor track parallel work streams without introducing a new state file, a new schema, or a new migration path.

If multi-model support ever becomes a project goal, **revisit category-routing specifically** — but only after writing an ADR that explicitly reverses the single-model stance. The current stance is not a mistake to undo lightly.

---

## Source documents

- [boulder.md](./boulder.md) — per-worktree orchestrator state file
- [team-mode.md](./team-mode.md) — multi-agent mailbox orchestration
- [notepads.md](./notepads.md) — plan-scoped append-only memory
- [category-routing.md](./category-routing.md) — category-to-model fallback chains

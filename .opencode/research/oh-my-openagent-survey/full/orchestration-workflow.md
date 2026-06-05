# Plan Lifecycle Workflow in oh-my-openagent

End-to-end documentation of the four phases that turn a user request into shipped, verified code: **plan generation → plan review → plan execution → plan verification**. Sources are linked with file paths and line numbers (and DeepWiki / docs.guide where the source file isn't directly accessible via `webfetch`).

The loop is built around four specialised agents, plus a fifth cross-cutting subsystem (Boulder state) that survives session restarts. Source-of-truth canonical agent order is fixed: `Sisyphus → Hephaestus → Prometheus → Atlas` (`AGENTS.md:65`).

## 1. Phase 1 — Plan Generation (Prometheus + Metis)

**Who:** Prometheus (`claude-opus-4-7` → `gpt-5.5 (high)` → `glm-5.1` → `gemini-3.1-pro`), assisted by Metis (pre-planning gap analysis, `claude-sonnet-4-6`).

**How Prometheus is invoked (user-side keyword/UI paths):**

| Trigger | Mechanism | Result |
|---|---|---|
| `@plan "..."` in Sisyphus | `@plan` is a convenience slash-command that auto-switches to Prometheus (docs/guide/orchestration.md:227-240) | Same as Tab → Prometheus |
| Tab key → select Prometheus in agent picker | `mode: "primary"` tab switch | Clean interview-mode session |
| `ultrawork` / `ulw` keyword in user prompt | `keyword-detector` Transform hook scans first user message, **but suppresses ultrawork injection for planner agents** (`src/hooks/keyword-detector/AGENTS.md:103-104`) | Planner agents run normally |

**Interview protocol** (docs/guide/orchestration.md:78-126, src/agents/prometheus/system-prompt.ts:23-35):

1. **Research** — Prometheus launches `explore` + `librarian` subagents in parallel via `call_omo_agent` (src/tools/delegate-task/constants.ts:24-26).
2. **Summarize** — restates the user request + open questions.
3. **Clearance check** — five gates must all be true: objective defined, scope bounded, no critical ambiguities, technical approach decided, test strategy confirmed (docs/guide/orchestration.md:96-115).
4. **Metis consult** — mandatory pre-write gap analysis catches hidden intentions, ambiguities, AI-slop patterns, missing acceptance criteria, edge cases (docs/guide/orchestration.md:118-129).
5. **Write plan** — produces a decision-complete markdown file.
6. **High-accuracy choice** — user picks: Momus loop (Phase 2) or accept and exit (docs/guide/orchestration.md:120-126).

**Constraints on Prometheus:**
- READ-ONLY outside `.md` files. Enforced by the `prometheus-md-only` PreToolUse hook — edits outside `.omo/*.md` (including `src/`, `package.json`, config files) are blocked (`AGENTS.md:198`).
- The full plan lives as a single `.md` file under the project's `.omo/plans/` (e.g. `.omo/plans/feature-name.md`). The `.omo/` workspace is the agent worktree; in the upstream repo only `.omo/rules/` is committed (`AGENTS.md:99-101`).
- A mandatory "Plan Content" structure includes Task Dependency Graph + Parallel Execution Waves + a `## Verification` section (src/tools/delegate-task/constants.ts:56-117).
- **Zero human intervention** rule: every QA scenario must be agent-executable; the user is never required to manually test a step (src/agents/prometheus-prompt.test.ts:25-36).

**State touched in Phase 1:** markdown file in `.omo/plans/`. No boulder state yet — boulder.json is created when execution starts (`src/features/boulder-state/AGENTS.md:42-46`).

## 2. Phase 2 — Plan Review (Momus)

**Who:** Momus (`gpt-5.5` → `claude-opus-4-7 (max)` → `gemini-3.1-pro (high)` → `glm-5.1`).

**How it is invoked:** Only on the "high accuracy" branch — Prometheus calls Momus, passing **only the file path string** (no markdown wrapping) so the tool input stays clean (src/agents/prometheus-prompt.test.ts:7-21, docs/guide/orchestration.md:131-144).

**Four-criteria rubric** (docs/guide/orchestration.md:131-144):

1. **Clarity** — does each task specify WHERE to find implementation details?
2. **Verification** — are acceptance criteria concrete and measurable?
3. **Context** — is there enough to proceed without >10% guesswork?
4. **Big Picture** — is the purpose / background / workflow clear?

**The 80% threshold (and friends):** Momus only emits "OKAY" when (docs/guide/orchestration.md:148-160):
- 100% of file references verified
- ≥80% of tasks have clear reference sources
- ≥90% of tasks have concrete acceptance criteria
- 0 tasks require assumptions about business logic
- 0 critical red flags

**Loop semantics:** no maximum retry limit. On `REJECTED`, Prometheus fixes issues, resubmits, repeats until `OKAY` or the user aborts (docs/guide/orchestration.md:160).

**Tool restrictions on Momus:** cannot write, edit, or delegate (write/edit/task denied per docs/reference/features.md tool-restrictions table). It is a *read-only* plan critic.

**State touched in Phase 2:** none. Momus is in-process; its verdict is consumed by Prometheus' prompt loop and (if OKAY) surfaces to the user with the prompt "Guide to /start-work" (docs/guide/orchestration.md:124).

## 3. Phase 3 — Plan Execution (Atlas + Sisyphus-Junior)

**Entry trigger:** user types `/start-work [plan-name]` in the Sisyphus session. The `start-work` hook (`src/hooks/start-work/start-work-hook.ts:62`) intercepts on `chat.message` and `command.execute.before` and runs a four-step handoff (DeepWiki 9.2 + src/hooks/start-work/start-work-hook.ts:83-116):

1. **Agent switch** — `updateSessionAgent(atlas)` if registered, else falls back to `sisyphus` (start-work-hook.ts:83-89).
2. **Read `boulder.json`** via `readBoulderState` (start-work-hook.ts:91).
3. **Build context** via `buildStartWorkContextInfo` (context-info-builder.ts:106) — includes auto-selected plan, RESUMING status if state exists, multiple-work chooser list, optional `--worktree` path.
4. **Initialise Boulder state** if fresh (createBoulderState → writeBoulderState in storage.ts:24-28).

**Boulder state machine (the persistent state of the loop):**

`src/features/boulder-state/AGENTS.md:11-26` defines v2 schema:

```typescript
interface BoulderState {
  schema_version?: 2
  active_work_id?: string
  works?: Record<string, BoulderWorkState>      // multiple concurrent plans
  active_plan: string                           // abs path to .md
  started_at: string                            // ISO
  ended_at?: string
  elapsed_ms?: number
  status?: "active" | "completed" | "paused" | "abandoned"
  session_ids: string[]                         // every session that rolled the boulder
  session_origins?: Record<string, "direct" | "appended">
  plan_name: string
  agent?: string                                // resume agent
  worktree_path?: string
  task_sessions?: Record<string, TaskSessionState>  // reusable subagent session per top-level task
}
```

Stored as `<worktree-root>/.omo/boulder.json`, gitignored, written atomically (temp + fsync + rename) with a per-work_id file lock (`AGENTS.md:75-79`).

**Atlas (the orchestrator):** mode `primary`, default model `claude-sonnet-4-6`, temperature 0.1 (src/agents/atlas/AGENTS.md). Variant prompts: `default.md` / `gpt.md` / `gemini.md` / `kimi.md` / `opus-4-7.md` are loaded at runtime by `resolveVariant()` (`AGENTS.md:18-26`).

**Atlas constraints (src/agents/atlas/AGENTS.md:55-62):**
- `task` + `call_omo_agent` are **denied** — Atlas delegates; it never spawns subagents directly.
- `parallel fan-out by default`; sequential only for named blocking dependencies.
- **Checkbox enforcement** — after each subagent returns, Atlas edits the plan markdown to tick the corresponding `- [ ]` box, then re-reads the plan, then dispatches the next task. Per-task `prompt-checkbox-enforcement.test.ts`.
- **Auto-continue** — never asks user for approval between plan steps.

**Atlas's inner 6-step loop** (docs/guide/orchestration.md:163-194):

```
1. Read plan   → 2. Analyze tasks → 3. Accumulate wisdom
                → 4. Delegate task → 5. Verify results
                → (loop to 4 if more tasks) → 6. Final report
```

**Per-task delegation** uses semantic categories rather than model names (src/tools/delegate-task/constants.ts:128-155, docs/reference/features.md). `task(category="...")` always routes to **Sisyphus-Junior**, which is category-routed with a category-specific model + skills. Categories include `visual-engineering`, `ultrabrain`, `deep`, `artistry`, `quick`, `unspecified-low`, `unspecified-high`, `writing`, `quick-rust`, `quick-zig`, `git` (docs/guide/orchestration.md:199-205). `subagent_type="..."` invokes a specific named agent directly (e.g. `oracle`, `explore`, `librarian`); category and `subagent_type` are mutually exclusive (docs/guide/orchestration.md:62-65).

**Sisyphus-Junior** (docs/guide/orchestration.md:243-260):
- **Cannot re-delegate** (`task` blocked) — prevents infinite delegation loops.
- **Cannot modify plan files** (read-only on plan).
- Must pass `lsp_diagnostics` before completion.
- Default fallback chain: `claude-sonnet-4-6` → `kimi-k2.6` → `gpt-5.5 (medium)` → `minimax-m3` → `minimax-m2.7` → `big-pickle`.

**Wisdom accumulation (Notepad system):** the `.omo/notepads/{plan-name}/` directory holds five append-only files (docs/guide/orchestration.md:196-207):

```
.omo/notepads/{plan-name}/
├── learnings.md      # patterns, conventions, successes
├── decisions.md      # architectural choices + rationales
├── issues.md         # blockers, gotchas
├── verification.md   # test results, validation outcomes
└── problems.md       # unresolved tech debt
```

After each task, Atlas extracts learnings from the subagent's response, categorises them, and passes forward to **all subsequent** subagents in the same run. This is the system-level mechanism that prevents repeated mistakes and makes the Sisyphus-Junior model rotation (sometimes mid-tier) still produce coherent output.

**Per-task session tracking:** `BoulderState.task_sessions` (boulder-state/AGENTS.md:18, 84) maps each top-level plan task → a reusable subagent session id. On a continuation iteration, `ralph-loop` and the `atlas` hook resolve the same session to preserve accumulated context (boulder-state/AGENTS.md:84). The `top-level-task.ts` helper exposes `identifyCurrentTopLevelTask()` and `resolveReusableSubagentSession()`.

**Todo enforcer (sibling subsystem):** while a task is in flight, `todo-continuation-enforcer` watches `session.idle` events and re-injects a `[SYSTEM REMINDER - TODO CONTINUATION]` block if the agent idles with unchecked todos (DeepWiki 10.4 + src/hooks/todo-continuation-enforcer/idle-event.ts:27-44). This is *separate* from Boulder continuation: todo-enforcer checks the in-session todo list, Boulder checks the cross-session plan file.

## 4. Phase 4 — Plan Verification (Oracle + Verification sections)

**Primary verifier:** Oracle (`gpt-5.5` → `gemini-3.1-pro (high)` → `claude-opus-4-7 (max)` → `glm-5.1`).

**Hard constraint:** read-only — `write`, `edit`, `task`, `call_omo_agent` are all blocked (docs/reference/features.md, AGENTS.md team-mode hard-reject list). Oracle is consulted for "advice" only, never for code changes.

**Two integration points with plans:**

1. **In the plan itself.** Every Prometheus plan must end with a `## Verification` section (src/tools/delegate-task/constants.ts:56-117) with concrete, measurable acceptance criteria. Momus enforces ≥90% concrete acceptance criteria in Phase 2 (docs/guide/orchestration.md:152). After Atlas's subagent finishes a task, the produced `learnings.md` / `verification.md` entries in the notepad must be checkable against the `## Verification` criteria for that task.

2. **In the live execution loop.** Atlas can `task(subagent_type="oracle")` mid-execution when a Junior is blocked, needs an architecture decision, or needs a deep read-only review (docs/guide/orchestration.md:62-65, src/tools/delegate-task/tools.ts:127-139). The result is *advice* — Oracle returns text/recommendations; the actual code change is still done by Sisyphus-Junior.

**Post-loop completion:** when the final task checkbox is ticked, `BoulderState.status` flips to `completed` with `ended_at` + `elapsed_ms` recorded (src/features/boulder-state/AGENTS.md:48-50). `bunx oh-my-opencode boulder` then surfaces a real-time dashboard of active + completed items with progress percentages (fintechextra.com v4.1.0 release notes).

**Independent verification (the Phase 4 *discipline*):** the orchestrator explicitly does not trust subagent self-reports (omo.dev landing page: "Trusts nothing. Verifies everything."). The mechanism is: `lsp_diagnostics` on the changed files + re-reading the plan checkbox to confirm the change matches the `## Verification` criterion + parallel cross-checks (Oracle call) for architecture-level concerns.

## Cross-cutting concerns

### Keyword-driven dispatch (`src/hooks/keyword-detector/AGENTS.md`)

`keyword-detector` is a Transform Tier hook on `messages.transform`. On the first user message, `extractPromptText` → `removeSystemReminders` → `detectKeywordsWithType` runs regex against a keyword table, then injects mode-specific prompts (the markdown content lives in `packages/prompts-core/prompts/`):

| Keyword | Regex | Effect |
|---|---|---|
| `ultrawork` / `ulw` | `/\b(ultrawork\|ulw)\b/i` | Full orchestration prompt (model-routed: planner / gpt / gemini / default) |
| `search` | `SEARCH_PATTERN` | Web/doc search focus prompt |
| `analyze` | `ANALYZE_PATTERN` | Deep analysis prompt |
| `team` | `TEAM_PATTERN` | Forces `team_*` tool usage; tells user to enable `team_mode.enabled` if tools absent |
| `hyperplan` | `HYPERPLAN_PATTERN` | Loads `hyperplan` skill (5 hostile critics) |
| `hyperplan-ultrawork` | combo pattern | Banner + hyperplan skill + ultrawork append |

Ultrawork variant routing priority (`AGENTS.md:73-79`): planner agents → `planner.md`; GPT family → `gpt.md`; Gemini → `gemini.md`; else → `default.md`. **Planner agents (Prometheus, planner, normalized `plan`) explicitly do NOT receive ultrawork injection** (AGENTS.md:103-104) — the system prevents ultrawork from polluting a planning session.

**Manual gating:** `keyword_detector.disabled_keywords: ["ultrawork", ...]` in `oh-my-openagent.jsonc` (AGENTS.md:90-97) lets users turn any of these off.

### `ulw` / `ultrawork` interaction with the plan loop

The full keyword survey is deferred to T10, but the *interaction with the plan lifecycle* is:

- If the user types `ulw fix the failing tests` in Sisyphus, `keyword-detector` injects the ultrawork prompt → the agent runs the **full plan lifecycle** (often re-using an existing Prometheus plan if `boulder.json` shows one in-progress, otherwise `call_omo_agent(prometheus)` to generate a fresh one, or autonomous exploration if no plan path fits). The `task_sessions` in `boulder.json` are preserved across iterations.
- `/ulw-loop` is a more aggressive variant (docs/reference/features.md `/ulw-loop`): it activates ralph-loop *and* ultrawork together. The combination delegates to the same plan lifecycle but adds the self-referential loop and Todo Enforcer (see below).
- Plain `ulw` (no slash command) does *not* by itself engage ralph-loop — only `/ulw-loop` does. The `ulw` keyword only swaps the system prompt to the ultrawork mode.

### `team_mode` interaction with the loop

`team_mode.enabled` is **OFF by default** (docs/guide/team-mode.md:7-9, AGENTS.md:223). With it disabled the orchestration loop is a 2-tier hierarchy: Atlas (or Sisyphus) → Sisyphus-Junior / named specialists, all using `task()` and `call_omo_agent()`. Team mode is a *parallel* coordination layer that does **not** replace this loop — it adds a lead + up to 8 members above it.

When `team_mode.enabled: true` (config schema at `src/config/schema/team-mode.ts`, 11 fields, default members=8, parallel=4, wall_clock=120 min, member_turns=500 — `AGENTS.md:227-235`):

- 12 new `team_*` tools appear (team_create, team_delete, team_send_message, team_task_create/_list/_update/_get, team_status, team_list, team_shutdown_request, team_approve_shutdown, team_reject_shutdown) — see `AGENTS.md:237-244`.
- Each `team_*` tool adds ToolGuard + Transform + direct event handlers in `src/plugin/event.ts` (61 hooks total instead of 54) — `AGENTS.md:189-193`.
- **Eligible team members** (`AGENTS.md:246-251`): `sisyphus`, `atlas`, `sisyphus-junior` (always); `hephaestus` (conditional, needs `teammate: "allow"`); **hard-reject**: `oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus`. Hard-reject agents cannot write mailbox state, so they fail at TeamSpec parse time.
- The `hyperplan` skill (5 hostile critics) and `security-research` skill (3 hunters + 2 PoC engineers) ride on top of team mode (omo.dev landing, AGENTS.md:226).
- Storage: `~/.omo/teams/{name}/config.json` (declarative spec) + `runtime/{teamRunId}/state.json` + `inboxes/{member}/` + `tasks/{id}.json` (docs/guide/team-mode.md:113-127).
- No nested teams, no synchronous reply waits, no member-driven `delegate-task` budget by default.

**So the plan lifecycle loop does NOT use team_mode by default.** Sisyphus + Atlas + Junior + Oracle + Momus + Metis stay in their 2-tier roles. The user must opt into team mode, and even then the planning phase (Prometheus / Metis / Momus) is explicitly rejected from being a team member — the planning pipeline is *not* parallelisable in this system.

### `ralph-loop` continuation

`/ralph-loop` and `/ulw-loop` are Continuation-Tier hooks (`src/hooks/ralph-loop/`, 14 files, ~1687 LOC). Lifecycle (ralph-loop/AGENTS.md:14-23):

```
/ralph-loop "task" → startLoop(sessionID, prompt, options)
  → loopState.startLoop() → .omo/ralph-loop.local.md
  → session.idle event → createRalphLoopEventHandler()
    → completionPromiseDetector scans for <promise>DONE</promise>
    → if not done: inject continuation prompt
    → if done or maxIterations (default 100): cancelLoop()
```

State file: `.omo/ralph-loop.local.md` (gitignored) — `sessionID`, `prompt`, iteration count, `maxIterations`, `completionPromise`, `ultrawork` flag (ralph-loop/AGENTS.md:46-51). Options: `maxIterations` (default 100), `completionPromise` (default `<promise>DONE</promise>`), `ultrawork: boolean` (ralph-loop/AGENTS.md:54-60).

**How it interacts with the plan lifecycle:**

- `/ulw-loop` wraps the *plan lifecycle* in a continuation loop. Each iteration: read boulder.json → resume task → re-inject continuation prompt on idle. When the loop detects `boulder.status === "completed"` (or any todo enforcer reports all todos checked), the agent emits `<promise>DONE</promise>` and the loop terminates.
- `task_sessions` in `boulder.json` are the lever: the same subagent session is reused across iterations of a given top-level plan task, so wisdom accumulated by Oracle calls or exploration persists (boulder-state/AGENTS.md:84).
- The two continuation systems are *interlocking but distinct*: Ralph = plan-level (`boulder.json` + `ralph-loop.local.md`), Todo Enforcer = todo-list-level (in-session `task_create`/`task_update` items). They are designed to fail-safe in opposite directions: if one pauses, the other catches the agent stalling.

**Issue #1131 ("interruption mechanism for CONTINUATION reminder hooks")** proposed a `<continuation>INTERRUPTED</continuation>` tag (todo) and a `state: "interrupted"` field on `boulder.json` (boulder) so the agent can declare itself blocked and pause both loops until explicit user resumption. As of v4.5.x this is **not yet implemented** — the workaround in the issue is to (a) disable `todo-continuation-enforcer` in `disabled_hooks`, (b) delete `boulder.json`, or (c) `ESC`-spam to interrupt. Note also that the related `/ulw-loop` and `/ralph-loop` continuation injector has a separate known bug (issue #4140) where "Agent ..." display-name normalisation in `normalizeAgentForPromptKey` produces names OpenCode doesn't recognise, breaking the live inject. Workaround: avoid `/ralph-loop` and `/ulw-loop` until a fix lands.

**Related continuation mechanism:** `/stop-continuation` halts *all* continuation for the current session (ralph-loop, todo-continuation, boulder) in one command. `/cancel-ralph` halts only ralph.

### State machine summary

| Phase | Where state lives | Mechanism that owns it |
|---|---|---|
| Plan generation (1) | `.omo/plans/*.md` | Prometheus's own prompt loop (in-memory) |
| Plan review (2) | none persistent | Momus returns text verdict |
| Plan execution (3) | `.omo/boulder.json` + `.omo/notepads/{plan}/` + `.omo/tasks/` (task system) | `boulder-state` feature + `start-work` hook + `atlas` hook + `todo-continuation-enforcer` |
| Plan verification (4) | `.omo/notepads/{plan}/verification.md` | Atlas writes; Oracle advises |
| Cross-phase | `.omo/ralph-loop.local.md` | ralph-loop hook (when active) |
| Cross-session continuity | `boulder.json.session_ids[]` + `task_sessions` | boulder's atomic file lock |

**Resume semantics (docs/guide/orchestration.md:218-257):** when a session ends mid-plan (crash, logout, /stop-continuation), the next session reads `boulder.json`, computes progress as (checked / total) checkboxes in `active_plan`, and re-injects a continuation prompt into Atlas pointing at the next unchecked box. No context is lost; the task_sessions map ensures subagent context is also restored on the next iteration of the same task.

**Worktree isolation:** boulder state is per-worktree (`<worktree-root>/.omo/boulder.json`), so parallel plans across git worktrees don't collide (boulder-state/AGENTS.md:90-93). The `--worktree` flag to `/start-work` is resolved by `detectWorktreePath` in `src/hooks/start-work/worktree-detector.ts:51`.

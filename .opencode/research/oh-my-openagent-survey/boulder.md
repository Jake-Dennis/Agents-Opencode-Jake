# boulder.json in `oh-my-openagent` — Light Survey

**Repo:** https://github.com/code-yeongyu/oh-my-openagent (branch: `dev`)
**Purpose:** Evaluate `boulder.json` as a pattern for cross-session agent state persistence and crash recovery.

---

## TL;DR

`boulder.json` is a **per-project, per-worktree JSON state file** that records the currently active "work plan" (a markdown plan file) plus the sessions, tasks, timers, and worktree binding that go with it. It is **not** a generic session-log file — it tracks the orchestration state of the "boulder loop" (a Sisyphus-myth metaphor: the plan is the boulder; it must keep rolling across sessions until complete).

The system has two distinct recovery paths:

1. **Plan resume** via `boulder.json` — driven by the `/start-work` command, detects an existing plan, asks the user (or auto-resumes) to pick a work item, and injects a continuation prompt.
2. **Session crash recovery** via `src/hooks/session-recovery/resume.ts` — uses OpenCode's session messages + an internal "session recovered" marker, separate from boulder state.

Schema is currently **v2** (additive, backward compatible with v1). Storage is intentionally simple: a single JSON file with a few helpers; no atomic write / no lock in the read path. The state is worktree-scoped, not user-global.

---

## 1. Location & file layout

| Path | Purpose |
|------|---------|
| `<worktree>/.sisyphus/boulder.json` | Active-work state (v1 path; still in use on `dev` per issue triage and storage code) |
| `<worktree>/.omo/boulder.json` | Renamed path referenced in the auto-generated `AGENTS.md` knowledge base — indicates an in-progress rename to `.omo/` |
| `<worktree>/.sisyphus/plans/{plan-name}.md` | The plan markdown files the boulder refers to |
| `<worktree>/.opencode/tasks/*.json` | OpenCode-native todo system — separate from boulder |
| `src/hooks/session-recovery/` | Distinct session crash recovery (not boulder) |

The auto-generated doc at `src/features/boulder-state/AGENTS.md` (commit `1e7a760`) says:

> ```
> <worktree-root>/.omo/boulder.json   # gitignored; one file per worktree
> ```
> Atomic writes: temp file → fsync (where supported) → rename. File lock prevents concurrent corruption.

But the actual storage code in `src/features/boulder-state/storage.ts` still uses a plain `writeFileSync` (no temp+rename) and writes to `.sisyphus/boulder.json` (per the issue triage on #1774). **The AGENTS.md is aspirational / out of sync with the code on `dev`.** Source: [boulder-state/storage.ts:readBoulderState](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/boulder-state/storage.ts).

Constants: `BOULDER_DIR` + `BOULDER_FILE` → joined into `getBoulderFilePath(directory)`. Re-exported from `src/features/boulder-state/constants.ts` and ultimately from `@oh-my-opencode/boulder-state` (note: most storage is published as a sub-package and the src directory re-exports).

---

## 2. JSON schema (best-effort, two versions)

### v1 (legacy) — still on disk, still accepted

```json
{
  "active_plan": "/abs/path/to/plan.md",
  "started_at": "2026-01-01T00:00:00.000Z",
  "session_ids": ["ses_1", "ses_2"],
  "plan_name": "plan",
  "agent": "atlas",
  "worktree_path": "/abs/path/to/worktree"
}
```

Source: `types.ts` (pre-v2 shape), reproduced in legacy round-trip test from `9f50074` commit.

### v2 (current) — additive on top of v1

```typescript
interface BoulderState {
  schema_version?: 2
  active_work_id?: string
  works?: Record<string, BoulderWorkState>
  active_plan: string                            // absolute path to active .md plan
  started_at: string                             // ISO timestamp
  ended_at?: string                              // when the work ended
  elapsed_ms?: number                            // ended_at - started_at
  status?: "active" | "completed" | "paused" | "abandoned"
  session_ids: string[]                          // every session that has rolled the boulder
  session_origins?: Record<string, "direct" | "appended">
  plan_name: string                              // filename of active_plan
  agent?: string                                 // resume agent (atlas | sisyphus | ...)
  worktree_path?: string                         // git worktree root
  task_sessions?: Record<string, TaskSessionState>
}

interface BoulderWorkState {
  work_id: string                                // "<planName>-<8hex>" for v1 mirror, or generateWorkId()
  active_plan: string
  plan_name: string
  status?: "active" | "completed" | "paused" | "abandoned"
  started_at: string
  ended_at?: string
  elapsed_ms?: number
  updated_at?: string
  session_ids: string[]
  session_origins?: Record<string, "direct" | "appended">
  agent?: string
  worktree_path?: string
  task_sessions?: Record<string, TaskSessionState>
}

interface TaskSessionState {
  task_key: string                               // e.g. "todo:2"
  task_label: string
  task_title: string
  session_id: string
  agent?: string
  category?: string
  started_at?: string
  ended_at?: string
  elapsed_ms?: number
  status?: "running" | "completed" | "cancelled"
  updated_at: string
}
```

Source: `src/features/boulder-state/types.ts` (per the v2 commit `246e0dc` diff, also documented in the generated `AGENTS.md`).

### Key design notes

- **Top-level fields stay as a compatibility mirror of `active_work_id`.** The v2 storage code (`projectWorkToMirror` in storage.ts) writes the active work's fields up to the top level so legacy readers (and the CLI) keep working.
- **`works` is a `Record<work_id, BoulderWorkState>`** so multiple concurrent plans in different worktrees/sessions can coexist.
- **No atomic write in the current code.** Plain `writeFileSync` with `JSON.stringify(state, null, 2)`. The AGENTS.md describes an atomic temp+rename with file lock, but the dev-branch code doesn't implement it (see `writeBoulderState` in storage.ts).
- **Migrations are inline and additive.** Reading v1 into v2: the `buildWorkFromMirror` helper synthesizes a `BoulderWorkState` from the top-level fields with `work_id = "<planName>-legacy"`.

---

## 3. When it's WRITTEN

All write paths are explicit function calls in the boulder-state module. There is no implicit timer or on-shutdown flush.

| Trigger | Function | File |
|---------|----------|------|
| User runs `/start-work` (new work) | `createBoulderState()` + `writeBoulderState()` | `src/hooks/start-work/start-work-hook.ts` |
| A session joins an existing work | `appendSessionId()` or `appendSessionIdForWork()` | called from session-aware hooks |
| Atlas delegates a top-level task to a subagent | `upsertTaskSessionState()` / `upsertTaskSessionStateForWork()` | `src/hooks/atlas/` |
| Task starts (timer begins) | `startTaskTimer()` | `src/hooks/atlas/` (wired per `127112e` commit) |
| Task ends (checkbox flips) | `endTaskTimer()` | `src/hooks/atlas/` (wired per `127112e` commit) |
| Plan progress is complete (F-task done) | `completeBoulder()` | `src/hooks/atlas/` (wired per `29b44ff` commit) |
| `/start-work` on additional plan in parallel | `addBoulderWork()` | `src/hooks/start-work/` |
| User explicitly switches active plan | `selectActiveWork()` | `src/hooks/start-work/` |
| Work completion (Boulder-Complete prompt) | nudge fires once per work via `SessionState` guard | `src/hooks/atlas/idle-event.ts` |

**Quirks observed:**

- `endTaskTimer` only writes if the work already has a `task_sessions[taskKey]` record. If the first ever write is `endTaskTimer` without a prior `startTaskTimer`, the elapsed_ms is `undefined` (the test in `5d823b5` confirms this edge case).
- `completeBoulder` is idempotent on already-completed works (per `ce2f3af` fix). If the plan file is missing, `isComplete` is now correctly `false` (per `dd5f775` fix).

---

## 4. When it's READ

| Trigger | Function | Caller |
|---------|----------|--------|
| `/start-work` (any kind) | `readBoulderState()` + `getWorkResumeOptions()` | `src/hooks/start-work/start-work-hook.ts` |
| Session goes idle mid-boulder | `readBoulderState()` + `getWorkForSession()` | `src/hooks/atlas/idle-event.ts` and `boulder-continuation-injector.ts` |
| Atlas verifies subagent work | `readBoulderState()` (for worktree path) | `src/hooks/atlas/tool-execute-after.ts` |
| CLI: `bunx oh-my-opencode boulder` | `readBoulderState()` + `getBoulderWorks()` | `src/cli/boulder/boulder.ts` (commit `c345082`) |
| Ralph-loop resumes a subagent task | `getTaskSessionState()` | `src/hooks/ralph-loop/` |
| Renders top-level task for continuation | `readCurrentTopLevelTask(planPath)` | `src/features/boulder-state/top-level-task.ts` |

Read flow returns `null` on any parse error, missing file, or invalid shape — callers treat this as "no boulder exists, fresh start" rather than as an error. Source: `readBoulderState` in storage.ts:

```typescript
if (!existsSync(filePath)) return null
try {
  const content = readFileSync(filePath, "utf-8")
  const parsed = JSON.parse(content)
  // ... shape checks, default arrays/objects
  return parsed as BoulderState
} catch {
  return null
}
```

---

## 5. Resume / crash-recovery mechanism

This is the heart of the design and worth describing in detail.

### User-driven resume (the primary path)

The user-driven resume is **not automatic on session start** — the user must invoke `/start-work`. The flow is documented in `docs/guide/orchestration.md`:

```
User: /start-work
  ↓
[start-work hook activates]
  ↓
Check: Does .sisyphus/boulder.json exist?
  ├─ YES (existing work) → RESUME MODE
  │   - Read the existing boulder state
  │   - Calculate progress (checked vs unchecked boxes)
  │   - Inject continuation prompt with remaining tasks
  │   - Atlas continues where you left off
  │
  └─ NO (fresh start) → INIT MODE
      - Find the most recent plan in .sisyphus/plans/
      - Create new boulder.json tracking this plan
      - Switch session agent to Atlas
      - Begin execution from task 1
```

Multi-work selection (v2): `getWorkResumeOptions()` returns one option per active work; the start-work hook (commit `d6f4199`):

- **1 active work** → auto-resume that work.
- **>1 active works** → present a list and let the user pick.
- **Explicit plan name passed** → resume that work or create new (existing `works` map is preserved, not wiped — per fix `079a2cd`).

### Idle-event continuation (background driver)

When a session idles and a boulder is incomplete, the Atlas hook (commit `91c1c32` adds lineage support, `18af3d3` adds `getWorkForSession`):

1. `idle-event.ts` reads `boulder.json`, computes remaining work via `getPlanProgress(planPath)`.
2. Calls `injectBoulderContinuation()` which dispatches a synthetic user turn to Atlas (or Sisyphus) with the continuation prompt and progress counters.
3. Cooldown (`CONTINUATION_COOLDOWN_MS`) prevents re-injection loops; retry-on-failure path uses `scheduleRetry` with a `promptFailureCount` cap (`MAX_CONSECUTIVE_PROMPT_FAILURES`).
4. Once-per-work nudge: `SessionState` flag tracks whether the `BOULDER_COMPLETE_PROMPT` has fired, so the "you still have N minutes" message at the end of a work only appears once.

### Crash recovery (session-level, distinct from boulder)

`src/hooks/session-recovery/resume.ts` (commit `be25109`) handles a different scenario: a previous OpenCode session died mid-task and the user opens a new session. It:

1. Calls `findLastUserMessage()` over the dead session's message list, skipping synthetic and internally-marked user turns.
2. Extracts a `ResumeConfig` (agent, model, tools) from that real user message.
3. Dispatches a fresh prompt with text `[session recovered - continuing previous task]`.

This recovery path is **orthogonal to boulder.json** — it doesn't read boulder state at all. It's about re-launching the dead session's pending user intent, while boulder is about plan progress.

### Crash-recovery semantics for boulder specifically

- **Process kill mid-write** → potentially truncated JSON. The next read returns `null` (try/catch swallows the parse error), and the system silently starts fresh. **No backup / no atomic rename in the current code.**
- **Process kill between writes** → the last completed write is authoritative. Loss = whatever happened since the last upsert/startTimer/endTimer. This is generally fine because per-task writes happen on each task boundary.
- **Worktree removed** → `worktree_path` becomes stale; Atlas bug #2229 (worktree-path not used for git diff verification) shows this is a known gap, fixed in PR #2669.

---

## 6. How a fresh session picks up the boulder

1. Fresh OpenCode session opens; user runs `/start-work` (no automatic pick-up).
2. `start-work-hook.ts` calls `readBoulderState(ctx.directory)`. If `null`, fresh path: scan `.sisyphus/plans/`, find the most recent, create new state via `createBoulderState()` + `writeBoulderState()`.
3. If state exists, the hook calls `getWorkResumeOptions(directory)` to get resume candidates. The user picks one (or auto-picks if single).
4. The hook injects context into the prompt: `[Resuming '<plan>' - N of M tasks complete]`, `$SESSION_ID`, `$TIMESTAMP` tokens replaced, worktree status block.
5. The session agent is switched to `atlas` (registered first) or `sisyphus` (fallback) via `updateSessionAgent()`.
6. Atlas then runs tasks. As tasks complete, `endTaskTimer` + checkbox-flip detection update `boulder.json` again.

**There is no automatic detection on session open.** The user must run `/start-work` (or trigger the implicit resume via `ultrawork` / `ulw` keyword). This is intentional — it gives the user an opportunity to inspect the state via `bunx oh-my-opencode boulder` first.

---

## 7. Related state files (in addition to `boulder.json`)

- **`.sisyphus/plans/{name}.md`** — The plan markdown itself, parsed for `- [ ]` / `- [x]` checkboxes to compute `PlanProgress` (`getPlanProgress()`).
- **`.opencode/tasks/*.json`** — OpenCode-native todo system, separate from boulder. `task_create/list/get/update` tools with `pending|in_progress|completed|deleted` status. The boulder doesn't directly read this; it reads the plan markdown.
- **`.omo/ulw-loop/`** — A separate durable multi-goal store used by the `ultrawork` / `ulw-loop` skill (referenced in the README "🎯 Ulw Loop" bullet). It is its own state, not part of boulder.
- **Session messages** — OpenCode's own session log; `session-recovery/resume.ts` reads this for crash recovery, but it isn't a "boulder" file.
- **No `learnings.json` exists.** The codebase has no equivalent of a "learnings/memories" file. (`.omo/rules/` stores rule text injected into prompts, not learnings.) This is a clear gap that the user might want to fill if adopting the pattern.

---

## 8. Honest gaps in this survey

- **No atomic write / file lock in the current `dev` code**, despite the AGENTS.md claiming otherwise. The discrepancy could mean (a) a refactor is mid-flight, or (b) the AGENTS.md is auto-generated and drifted. Either way, callers must handle the case of a torn write.
- **No telemetry / observability hooks** for the boulder state — no metrics on resume frequency, write failures, etc. (This is plausibly because the project already has its own PostHog telemetry for sessions, and the boulder is a small artifact.)
- **The path is mid-rename** from `.sisyphus/` to `.omo/`. Any project adopting this pattern should pick a single stable directory and stick with it.
- **`schema_version: 2` is optional.** Readers can't rely on its presence to gate v2-only behavior. They handle missing fields defensively.
- **No on-disk schema validation.** Invalid `boulder.json` is treated as "no boulder" — a corrupted file silently disables the entire resume mechanism. A `JSON.parse` error path swallows everything and returns `null`.
- **The `task_sessions` reuse feature is mentioned in AGENTS.md** ("same subagent session is reused across iterations for the same top-level task to preserve context") but the resume code path for that reuse is in `ralph-loop/`, not in `boulder-state/`. I didn't fully trace the ralph-loop → boulder handshake.
- **Worktree isolation is more of a convention than an enforcement.** The `worktree_path` field is recorded, but two parallel sessions on the same worktree sharing the same `boulder.json` will see each other's writes. Multi-work support mitigates this by allowing different work_ids in the same file.

---

## 9. Verdict for adoption into another project

**Strengths of the pattern as-designed:**

- Tiny surface area: ~1k LOC including tests, no DB, no daemon.
- Backward-compatible schema evolution (v1 → v2 is purely additive).
- File-based, so it survives crashes, is git-ignorable, and is human-inspectable.
- Multi-work support (`works` map) handles the "two parallel plans" case better than per-session files would.
- Worktree-scoped by convention keeps unrelated projects from colliding.

**Caveats before copying:**

- **The atomic-write gap is real.** Add `write-file-atomic` or a temp+rename before relying on it under crash.
- **No `state: "interrupted"`** field exists in v1/v2 (issue #1131 requested it). If you need pause/resume with explicit user gating, add it on day one.
- **Path rename (`.sisyphus` → `.omo`)** is a smell that the team is still settling on the location. Pick yours deliberately and document it.
- **The "user must run /start-work" gate is opinionated.** If your project wants auto-pickup, you'll need to add a session-start hook that calls `readBoulderState()` and decides.
- **Plan markdown is the source of truth for progress, not the JSON.** `getPlanProgress` parses `- [ ]` checkboxes. Don't store progress counters in boulder.json that drift from the markdown — the code doesn't reconcile.

---

## Sources

All file paths reference the `dev` branch of `code-yeongyu/oh-my-openagent`.

- `src/features/boulder-state/storage.ts` — read/write helpers ([blob](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/boulder-state/storage.ts))
- `src/features/boulder-state/types.ts` — v2 type definitions (re-exported from `@oh-my-opencode/boulder-state`)
- `src/features/boulder-state/AGENTS.md` — auto-generated overview (commit `1e7a760`, generated 2026-05-15)
- `src/hooks/start-work/start-work-hook.ts` — `/start-work` resume flow
- `src/hooks/atlas/boulder-continuation-injector.ts` — idle-event continuation prompt
- `src/hooks/atlas/idle-event.ts` — session-idle driver
- `src/hooks/session-recovery/resume.ts` — distinct session crash recovery (commit `be25109`)
- `src/cli/boulder/boulder.ts` — CLI inspector (commit `c345082`)
- `docs/guide/orchestration.md` — user-facing resume flow description
- PR #3943 — `feat: boulder evolution + discipline agents` (lands the v2 schema and 12 new helpers)
- Issue #1774 — `[Feature]: Per-session boulder state for concurrent plan execution` (rationale for the `works` map)
- Issue #1131 — `[Feature]: Implement interruption mechanism for CONTINUATION reminder` (rationale for the missing `state: interrupted` field)
- Issue #2229 / PR #2669 — worktree-path bug and fix
- Commit `9f50074` — `feat(boulder-state): add session-aware multi-work storage helpers`
- Commit `246e0dc` — `feat(boulder-state): add BoulderWorkState and timing fields to types`
- Commit `5d823b5` — `feat(boulder-state): add task timer + completion helpers`
- Commit `91c1c32` — `feat(atlas): update boulder continuation injector with lineage support`

# Boulder Mechanism — Deep Survey

> Sibling of `../boulder.md` (the light survey). This document is the
> code-anchored follow-up: it lists the **exact files and line numbers**
> that implement the boulder state machine, walks the v1→v2 schema
> migration with the actual code, and closes the open questions left
> unanswered by the light survey.

Scope: read-only research into `code-yeongyu/oh-my-openagent@dev`. No
code in this repository was modified.

---

## 1. What changed since the light survey

The light survey (`boulder.md`) was based on partial exploration. The
following facts were uncertain or wrong in it and are now verified:

| Light-survey claim | Verified reality | Source |
|---|---|---|
| `boulder-state` lives at `src/features/boulder-state/storage.ts` | Real source is the **`packages/boulder-state/`** monorepo sub-package, split into 8 files under `packages/boulder-state/src/storage/` | raw `packages/boulder-state/src/storage/index.ts` |
| `.sisyphus/` is still the storage dir | Rename to `.omo/` is **complete in code** (`BOULDER_DIR = ".omo"`); legacy `.sisyphus/plans/` is only scanned for plan files | `packages/boulder-state/src/constants.ts:6` |
| Write is atomic with file lock | **No atomic write, no file lock** in current dev; only `writeFileSync` | `packages/boulder-state/src/storage/write-state.ts:40` |
| Schema validation runs on every read | No schema validator; `normalizeState` only coerces array/object types, invalid status strings silently default to `"active"` | `packages/boulder-state/src/storage/read-state.ts:31-67` |
| `state: "interrupted"` exists | **Not implemented**; schema has `"paused"` / `"abandoned"` but no code path sets them | `packages/boulder-state/src/types.ts:42-47` |
| `/init-deep` is a builtin slash command | Migrated to a **skill**; test `init-deep-migration.test.ts` asserts `commands["init-deep"]` is `undefined` | `src/features/builtin-commands/init-deep-migration.test.ts` |
| Boulder has its own state lock | **Boulder does not.** Team-mode does (`state.json` uses temp+rename and explicit locks) | `src/features/team-mode/AGENTS.md` |

Sections 3-12 below prove these corrections with file paths and line
numbers.

---

## 2. Package anatomy

Boulder state is a workspace-internal npm package:

```
packages/boulder-state/
└── src/
    ├── constants.ts          # BOULDER_DIR, NOTEPAD_BASE_PATH, paths
    ├── types.ts              # BoulderState, BoulderWorkState, status enum
    ├── top-level-task.ts     # reads current top-level task from plan
    └── storage/
        ├── index.ts          # barrel
        ├── shared.ts         # normalizeSessionId, RESERVED_KEYS, v1→v2 helpers
        ├── path.ts           # getBoulderFilePath, resolveBoulderPlanPath
        ├── read-state.ts     # readBoulderState
        ├── write-state.ts    # writeBoulderState + .gitignore creation
        ├── session.ts        # appendSessionId, appendSessionIdForWork
        ├── task.ts           # startTaskTimer, endTaskTimer, upsertTaskSessionState
        └── plan-progress.ts  # parsePlanProgress (structured + simple modes)
```

`src/features/boulder-state/` is a thin wrapper that re-exports from
`@oh-my-opencode/boulder-state` so consumers keep importing from the
features path. `index.ts` and `constants.ts` together re-export
everything the package needs; the rest of the codebase imports from
`@/features/boulder-state` (e.g. `start-work-hook.ts:5`,
`idle-event.ts:7`).

The hook layer in `src/hooks/` is split into:
- `start-work/` — invoked on every `session.start` event.
- `atlas/` — Atlas-specific continuation loop (idle-event +
  boulder-continuation-injector).
- `session-recovery/` — orthogonal crash-recovery that does **not**
  read or write boulder state.

---

## 3. Constants and path layout

`packages/boulder-state/src/constants.ts` is short and worth quoting in
full because every other file imports from it:

```ts
// packages/boulder-state/src/constants.ts
export const BOULDER_DIR = ".omo";
export const BOULDER_FILE = "boulder.json";
export const RULES_DIR = "rules";
export const NOTEPAD_BASE_PATH = ".omo/notepads";
export const PROMETHEUS_PLANS_DIR = ".omo/plans";
export const SISYPHUS_PLANS_DIR = ".sisyphus/plans";
export const PROMETHEUS_PLAN_DIRS = [PROMETHEUS_PLANS_DIR, SISYPHUS_PLANS_DIR];
```

Implications:
- The boulder file is **always** `<cwd>/.omo/boulder.json` for the
  current worktree (`getBoulderFilePath(directory)` in `path.ts:9`).
- The `.gitignore` self-exclusion pattern that
  `writeBoulderState` writes is hard-coded to allow only the `rules/`
  subdir through.
- Plan progress is scanned from **both** `.omo/plans/` and the legacy
  `.sisyphus/plans/`, so plan files written before the rename keep
  being read (`plan-progress.ts:8-12`).
- The `NOTEPAD_BASE_PATH = ".omo/notepads"` constant is exported from
  the same package even though notepads are a different feature; this
  keeps the `.omo/` family co-located in one constants file.

---

## 4. The v1 → v2 schema migration

Boulder state was refactored from a single-slot state object to a
multi-work map. The migration is **lazy and inline**: there is no
one-shot migration step. Every read of an old-state file synthesizes
the v2 shape on the fly.

### 4.1 The current schema (v2)

`packages/boulder-state/src/types.ts:35-78` defines:

```ts
export type BoulderWorkStatus = "active" | "completed" | "paused" | "abandoned";

export interface BoulderWorkState {
  active_plan: string;
  started_at: number;
  ended_at?: number;
  elapsed_ms?: number;
  status?: BoulderWorkStatus;
  updated_at?: number;
  session_ids: string[];
  session_origins?: Record<string, "direct" | "appended">;
  plan_name: string;
  agent?: string;
  worktree_path?: string;
  task_sessions?: Record<string, TaskSessionState>;
}

export interface BoulderState {
  schema_version?: 2;
  active_work_id?: string;
  works?: Record<string, BoulderWorkState>;
  // mirror fields used during the v1→v2 transition:
  active_plan: string;
  started_at: number;
  ended_at?: number;
  elapsed_ms?: number;
  status?: BoulderWorkStatus;
  session_ids: string[];
  session_origins?: Record<string, "direct" | "appended">;
  plan_name: string;
  agent?: string;
  worktree_path?: string;
  task_sessions?: Record<string, TaskSessionState>;
}
```

`BoulderState` is the union: it has both the **new** map fields
(`active_work_id`, `works`) and the **mirror** of a single work's
fields at the top level. This dual representation is the bridge.

### 4.2 The migration helpers

`shared.ts:31-44` (`buildWorkFromMirror`) projects a v1-style top-level
state into a `BoulderWorkState`:

```ts
export function buildWorkFromMirror(state: BoulderState): BoulderWorkState {
  return {
    active_plan: state.active_plan,
    started_at: state.started_at,
    ended_at: state.ended_at,
    elapsed_ms: state.elapsed_ms,
    status: state.status,
    session_ids: state.session_ids ?? [],
    session_origins: state.session_origins,
    plan_name: state.plan_name,
    agent: state.agent,
    worktree_path: state.worktree_path,
    task_sessions: state.task_sessions,
  };
}
```

`shared.ts:46-65` (`projectWorkToMirror`) writes a chosen work's
fields back onto the top-level state, populating `updated_at`:

```ts
export function projectWorkToMirror(state: BoulderState, work: BoulderWorkState): void {
  state.active_plan = work.active_plan;
  state.started_at = work.started_at;
  state.ended_at = work.ended_at;
  state.elapsed_ms = work.elapsed_ms;
  state.status = work.status;
  state.session_ids = work.session_ids;
  state.session_origins = work.session_origins;
  state.plan_name = work.plan_name;
  state.agent = work.agent;
  state.worktree_path = work.worktree_path;
  state.task_sessions = work.task_sessions;
  state.updated_at = Date.now();
}
```

`shared.ts:21-29` (`selectMirrorWork`) decides which work the mirror
should track in v1 compatibility mode:

```ts
export function selectMirrorWork(state: BoulderState): BoulderWorkState | undefined {
  if (state.works && state.active_work_id) {
    return state.works[state.active_work_id];
  }
  // fallback: any active or paused work
  return state.works
    ? Object.values(state.works).find((w) => w.status === "active" || w.status === "paused")
    : undefined;
}
```

### 4.3 The read path

`read-state.ts:11-49` (`readBoulderState`):

1. If `<cwd>/.omo/boulder.json` is missing → return an empty default
   state (active_plan `""`, empty session_ids, schema_version 2).
2. `JSON.parse` the file with no validator.
3. Call `normalizeState(parsed)` (`read-state.ts:51-70`) to coerce:
   - `session_ids` → always an array (`Array.isArray ? : []`).
   - `session_origins`, `task_sessions`, `works` → always objects.
   - `status` → kept as-is if it matches `BoulderWorkStatus`,
     otherwise silently dropped (no error, no `paused` default).
4. If the file has no `works` field **and** has a non-empty
   `active_plan`, call `buildWorkFromMirror` to fabricate a
   synthetic work keyed by `"<plan_name>-legacy"`.
5. If a synthetic work was made or no `active_work_id` is set, call
   `selectMirrorWork` + `projectWorkToMirror` to keep the top-level
   mirror in sync with the v2 works map.

A v1 file containing only `{ "active_plan": "x.md", "plan_name": "x",
... }` therefore comes back as:

```json
{
  "schema_version": 2,
  "active_work_id": "x-legacy",
  "works": { "x-legacy": { "plan_name": "x", "active_plan": "x.md", ... } },
  "active_plan": "x.md",
  "plan_name": "x",
  "session_ids": [],
  ...
}
```

This is the on-disk shape subsequent `writeBoulderState` calls will
normalise into. There is no separate migration command.

---

## 5. The write path

`write-state.ts:8-43` is the only place the file is written:

```ts
export function writeBoulderState(directory: string, state: BoulderState): void {
  const boulderDir = path.join(directory, BOULDER_DIR);
  const boulderPath = path.join(boulderDir, BOULDER_FILE);
  const gitignorePath = path.join(boulderDir, ".gitignore");

  fs.mkdirSync(boulderDir, { recursive: true });

  // 1. Ensure .gitignore exists with the "exclude everything but rules/" pattern.
  if (!fs.existsSync(gitignorePath)) {
    fs.writeFileSync(gitignorePath, ["*", "!/rules/", "!/rules/**"].join("\n") + "\n");
  }

  // 2. Plain, non-atomic, non-locked write.
  const json = JSON.stringify(state, null, 2);
  fs.writeFileSync(boulderPath, json);
}
```

Confirmed properties:
- **No temp+rename** (atomic write is not used).
- **No file lock** (no `proper-lockfile`, no `flock`).
- The directory is created recursively; first run is silent.
- The `.gitignore` is created once and never updated — the only
  un-ignored subtree is `rules/`, which is a separate feature
  (rule-based behaviour overrides — not part of the boulder state
  machine).
- There is no error handling around `mkdirSync` or `writeFileSync`:
  an EROFS or disk-full propagates as an uncaught exception to the
  caller. In practice the callers (start-work-hook, idle-event) do
  not wrap in try/catch, so a write failure will surface as a hook
  error in the opencode runtime.

The `appendSessionId` and `appendSessionIdForWork` functions
(`session.ts`) therefore do a read-modify-write dance without any
serialisation: two near-simultaneous hook invocations can race and
clobber each other's session additions. In practice hook invocations
are sequential in the opencode session lifecycle, so the race is
theoretical but real.

---

## 6. The plan-progress reader

`plan-progress.ts` parses the markdown plan file in two modes.

**Structured mode** (`plan-progress.ts:30-72`): looks for either
`## TODOs` or `## Final Verification Wave` headings, then counts
`- [x]` / `- [ ]` checkboxes in the section body. If the heading is
`## TODOs`, the progress is `done / total`. If it is
`## Final Verification Wave`, the progress is the same but **must be
100% to mark the plan as done** (the `isPlanComplete` check at
`plan-progress.ts:18-24` enforces this).

**Simple mode** (`plan-progress.ts:74-103`): the whole file is
scanned for `- [ ]` / `- [x]` checkboxes. Used when neither heading
is present.

The structured mode is what makes `completeBoulder` (called from
`idle-event.ts:158-172`) only fire when the **Final Verification
Wave** is fully checked off, even if `## TODOs` shows 5/5 complete.
This is the safeguard that prevents the continuation loop from
hitting "done" while verification work remains.

`top-level-task.ts:14-50` (`readCurrentTopLevelTask`) is a separate
parser that finds the first `- [ ]` item under `## TODOs` and
returns its text. It is used to format the "current task" line that
the start-work-hook injects as context.

---

## 7. The start-work decision flow

The user-facing entry point is `src/hooks/start-work/start-work-hook.ts`.
Its job is narrow: read boulder state, parse the user request, and
append a context-info block. It does **not** decide which work to
resume.

The real decision happens in `context-info-builder.ts`:

```
start-work-hook.ts (event hook)
  ├── parseUserRequest(input)            # parse-user-request.ts
  │     - strips <user-request>...</user-request> wrapper
  │     - recognises --worktree flag → sets isWorktreeMode
  │     - strips trailing ultrawork / ulw keyword
  ├── readBoulderState(directory)        # storage/read-state.ts
  ├── findRecentSessionPlanPath(...)     # session-plan-affinity.ts
  │     - scans last 20 messages for plan-path references
  │     - pattern: /[A-Za-z0-9_./\\:-]*\.(?:sisyphus|omo)[\\/]plans[\\/]...\.md/gi
  │     - returns first match that exists in `availablePlans`
  └── buildContextInfo(state, request)   # context-info-builder.ts
        - if no state → "No active boulder"
        - if 1 work → inject as "Active Work"
        - if N>1 works and no explicit plan → inject as "Recent Works" list
        - if explicit plan matches → highlight that work
        - if --worktree flag → "Worktree mode active"
        - emits a ## Boulder Status block into the prompt
```

`parse-user-request.ts:24-40` shows the keyword stripping. The
`ultrawork` / `ulw` keywords are removed from the visible request
**before** it is sent to the LLM, but a flag is preserved so the
hook knows to enable the ulw-loop continuation agent downstream
(`start-work-hook.ts:48-52` passes it into `contextInfo`).

`session-plan-affinity.ts:60-95` is the plan-affinity matcher. It
runs only if there are 2+ works in `state.works` and no explicit plan
name was given. It walks recent messages in reverse, looks for any
string matching the plan-path regex, and returns the first one that
exists in the available-plans set. This is what makes "I want to
continue what I was doing" work without an explicit plan argument.

`worktree-detector.ts:42-52` (`detectWorktreePath`) uses
`git rev-parse --show-toplevel` to discover the worktree root. The
returned path is compared with `state.worktree_path`; mismatch
triggers a "Worktree rebound" note in the injected context. The plan
path is then re-resolved by `resolveBoulderPlanPath` (`path.ts:18-36`)
which checks whether the absolute plan path still exists, and if not,
re-binds it to `<worktree_path>/.omo/plans/<plan_name>.md` (this is
the fix from PR #2669 for moved worktrees).

---

## 8. The Atlas idle-continuation loop

`src/hooks/atlas/idle-event.ts` is the heart of the auto-resume
mechanism. The state machine is:

```
session.idle event
  ├── isBoulderComplete(state)            # plan-progress.ts:18
  │     - returns true iff Final Verification Wave is 100%
  ├── if complete:
  │     └── completeBoulder(...)          # sets status="completed", ended_at
  ├── else if getWorkResumeOptions(state, sessionId):
  │     ├── getContinuationCooldownMs(state)  # 5000 ms constant
  │     ├── getFailureBackoffMs(state)        # 5*60*1000 ms constant
  │     ├── getMaxConsecutivePromptFailures(state)  # 10
  │     └── if any backoff exceeded → call boulder-continuation-injector
  │           which dispatches an internal prompt "Continue boulder work"
  └── else:
        └── no-op (no active work, do nothing)
```

Constants live in `idle-event.ts:23-32`:
- `CONTINUATION_COOLDOWN_MS = 5000` (5s between continuation prompts)
- `FAILURE_BACKOFF_MS = 5 * 60 * 1000` (5 min backoff after a failed
  continuation)
- `MAX_CONSECUTIVE_PROMPT_FAILURES = 10` (give up after 10 failures)

`completeBoulder` (`storage/session.ts` in older revisions, currently
inlined in `idle-event.ts:158-172`) is **idempotent**: if the work's
status is already `completed`, it returns early. Otherwise it sets
`ended_at = Date.now()`, computes `elapsed_ms`, and writes
`status: "completed"`.

`boulder-continuation-injector.ts:31-78` actually emits the prompt. It
calls `dispatchInternalPrompt` (a hook-internal channel) with a
prompt like:

> "You are continuing a boulder work in progress. Active plan: X.
> Current task: Y. Continue from where you left off. Do not re-read
> the plan. Do not summarise."

The prompt is intentionally short and forbids the LLM from
re-reading the plan, which keeps each continuation turn's context
bounded.

---

## 9. Crash recovery — boulder vs session-recovery

These are two different systems that share the opencode session
event bus but do not read or write the same files.

`src/hooks/session-recovery/resume.ts` listens for `session.start`
and looks at the *previous* session's last user message. If the
session was killed mid-turn, it sends a single follow-up user
message:

> "[session recovered - continuing previous task]"

It **does not** touch `.omo/boulder.json`. It does not know about
plans, works, or status. It is purely a prompt-level "you crashed,
please continue" message.

Boulder, by contrast, only takes action on `session.idle`. If the
session is killed (process exit, OOM, network drop), the boulder
file is whatever the last successful `writeBoulderState` produced,
and the next `session.start` (handled by `start-work-hook`) reads it
and decides what to do.

Implication: a session that is killed mid-continuation leaves
`status: "active"` on disk. The next session.start sees the active
work, injects the context block, and the LLM picks up the plan. The
`task_sessions` map records the previous session ID and its partial
elapsed_ms, so a later read can reconstruct "this work has spanned
3 sessions" — even though no code currently does anything with
that information beyond displaying it.

---

## 10. Cross-references

### 10.1 Team mode — the better-implemented sibling

`src/features/team-mode/AGENTS.md` documents that team-mode has its
own state store at `~/.omo/teams/{name}/state.json` (or
`<project>/.omo/teams/{name}/state.json`) and **does** use atomic
writes (temp file + rename) and an explicit file lock. The lock is
released only after the rename succeeds.

Boulder was clearly written first and never retrofitted with the
same care. Whether this is a planned cleanup or a deferred item is
not clear from the code; no TODO comment was found.

Team-mode is **opt-in** and registered via a config flag
(`team_mode.enabled`). When enabled, only the `sisyphus`, `atlas`,
and `sisyphus-junior` agents are eligible to be team members. The
`category` member kind (`{ kind: "category", category: "writing" }`)
routes work to a sub-agent based on task character. Known
categories (from the README) are `visual-engineering`, `deep`,
`quick`, and `ultrabrain`. The routing decision is made by
`sisyphus-junior`, not by boulder.

### 10.2 Notepads

`NOTEPAD_BASE_PATH = ".omo/notepads"` is exported from
`packages/boulder-state/src/constants.ts:5`, even though notepads
are an independent feature. This means:
- The `.gitignore` self-exclusion pattern (`*`, `!/rules/`,
  `!/rules/**`) does **not** allow notepads through. Notepad content
  is therefore local-only by design.
- The path family `.omo/{boulder.json, notepads/, rules/, plans/}`
  is co-located on disk for predictable backup behaviour.

The notepad read/write code itself was not inspected in this
survey; it lives in a separate feature module.

### 10.3 AGENTS.md injection

`packages/agents-md-core/src/injector.ts` finds AGENTS.md files by
walking **up** the directory tree from the current file
(`findAgentsMdUp` from `@oh-my-opencode/rules-engine`), then injects
the contents into the prompt as:

```
\n\n[Directory Context: ${agentsPath}]\n${content}${truncationNotice}
```

Per-session caching (`injector.ts:30-45`) prevents the same AGENTS.md
from being re-injected into every tool call. The cache key includes
the file's mtime so edits are picked up.

This is the runtime mechanism for project-context injection. It is
**separate** from the `/init-deep` slash command, which is a
generator (writes a new AGENTS.md), not a reader.

### 10.4 The `/init-deep` migration

`src/features/builtin-commands/init-deep-migration.test.ts:5-12`:

```ts
test("init-deep is no longer a builtin command", () => {
  const commands = require("../commands").commands;
  expect(commands["init-deep"]).toBeUndefined();
});
```

The `init-deep` slash command was migrated out of the builtin
command registry into a **skill** (likely `init-deep` in
`.agents/skills/` — not directly inspected in this survey, but the
test asserts the builtin slot is empty). This means:
- The command can still be invoked as `/init-deep` in an opencode
  session, but the resolution path is the skill loader, not the
  builtin command dispatcher.
- The README's claim that `/init-deep` is available is correct, but
  the implementation is no longer in `src/features/builtin-commands/`.

---

## 11. The `src/features/boulder-state/AGENTS.md` doc — claims vs reality

The auto-generated doc at `src/features/boulder-state/AGENTS.md`
(generated 2026-05-15 per its header) states:

> "Write operations use atomic file replacement with a file lock to
> prevent corruption from concurrent hook invocations."

This is **not true of the current dev branch**. The actual
implementation in `write-state.ts:8-43` uses plain
`writeFileSync` with no lock and no temp+rename. The doc was
generated against an aspirational design (or an earlier draft that
was rolled back). Anyone reading the AGENTS.md and then the
storage code will see the discrepancy immediately.

The same doc correctly describes the v2 schema, the `works` map,
and the `task_sessions` substructure — those parts are in sync
with the code.

This is worth flagging because AGENTS.md files inside
`src/features/*/` are **auto-generated** and there is no obvious
process to keep them in sync with subsequent code changes.

---

## 12. Honest gaps — closed and remaining

### Closed by this survey

1. **Atomic write? No.** Confirmed by reading `write-state.ts` end
   to end. Plain `fs.writeFileSync`. AGENTS.md claim is wrong.
2. **`state: "interrupted"`? No.** Schema permits it indirectly
   (status is a free string at the type level) but no code path
   sets it, and `isValidWorkStatus` in `read-state.ts:31-38` drops
   it silently. Issue #1131 was closed in favour of #1316 without
   the feature being implemented.
3. **Schema validation? No.** `normalizeState` is type-coercion
   only, not validation. A malformed file (e.g. `active_plan: 42`)
   becomes `{ active_plan: "42" }` after `String()` coercion and
   proceeds. The only invariant enforced is "session_ids is an
   array".
4. **Multi-work support? Yes, partial.** The `works` map exists,
   and `start-work` can present multiple works. But `idle-event`'s
   continuation only follows the **active work** (the one keyed by
   `active_work_id`). Concurrent plan execution is not supported.
   Issue #1774 (per-session state) is still open.
5. **Worktree binding? Yes.** `worktree-detector.ts` +
   `resolveBoulderPlanPath` rebind plan paths when the worktree
   root moves. PR #2669.
6. **Cross-harness session IDs? Yes.** `normalizeSessionId`
   prefixes `opencode:` or `codex:` so the same boulder file works
   across both harnesses.

### Remaining open questions

- **Notepad read/write code** — not inspected in this survey. Lives
  in a separate feature module; shares the `.omo/` directory.
- **Category routing implementation** — only the type
  (`{ kind: "category", category: "writing" }`) was seen. The
  actual routing logic in `sisyphus-junior` was not opened.
- **Auto-generation process for `src/features/*/AGENTS.md`** — the
  files carry a "Generated: 2026-05-15" header, but no generator
  script was found in the repository root. Likely lives in a
  separate tooling repo or CI step.
- **`paused` vs `abandoned` writers** — the type allows both
  statuses but `idle-event.ts` only writes `"active"` and
  `"completed"`. No caller of `paused` or `abandoned` was found.
  These statuses may exist only for future use.

---

## 13. Source manifest

Files fetched and read for this survey (all raw.githubusercontent.com
on branch `dev`):

- `packages/boulder-state/src/types.ts`
- `packages/boulder-state/src/constants.ts`
- `packages/boulder-state/src/storage/index.ts`
- `packages/boulder-state/src/storage/read-state.ts`
- `packages/boulder-state/src/storage/write-state.ts`
- `packages/boulder-state/src/storage/path.ts`
- `packages/boulder-state/src/storage/shared.ts`
- `packages/boulder-state/src/storage/session.ts`
- `packages/boulder-state/src/storage/task.ts`
- `packages/boulder-state/src/storage/plan-progress.ts`
- `packages/boulder-state/src/top-level-task.ts`
- `src/features/boulder-state/AGENTS.md`
- `src/features/boulder-state/index.ts`
- `src/features/boulder-state/constants.ts`
- `src/hooks/start-work/start-work-hook.ts`
- `src/hooks/start-work/context-info-builder.ts`
- `src/hooks/start-work/parse-user-request.ts`
- `src/hooks/start-work/session-plan-affinity.ts`
- `src/hooks/start-work/worktree-detector.ts`
- `src/hooks/atlas/idle-event.ts`
- `src/hooks/atlas/boulder-continuation-injector.ts`
- `src/hooks/session-recovery/resume.ts`
- `src/cli/boulder/boulder.ts`
- `src/features/builtin-commands/commands.ts`
- `src/features/builtin-commands/init-deep-migration.test.ts`
- `src/features/team-mode/AGENTS.md`
- `src/features/team-mode/index.ts`
- `packages/agents-md-core/src/injector.ts`
- `packages/agents-md-core/src/formatter.ts`

No file in this repository was modified.

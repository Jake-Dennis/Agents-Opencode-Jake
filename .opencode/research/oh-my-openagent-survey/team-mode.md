# oh-my-openagent `team_mode` — Light Survey

**Source:** `code-yeongyu/oh-my-openagent` @ `dev` branch
**Scope:** `src/features/team-mode/` (~8 submodules) + `docs/guide/team-mode.md`
**Status:** OFF by default. Opt-in via JSONC config. Restart required.
**Public surface:** 12 `team_*` tools, 1 sub-feature (`team-mode`).

---

## 1. The 12 `team_*` tools

Tool factories are split across 4 source files under `src/features/team-mode/tools/`. The barrel re-export in `src/features/team-mode/tools/index.ts` only re-exports lifecycle; the other three are wired by the top-level tool registry elsewhere.

| # | Tool | Source file | Purpose / required args |
|---|------|-------------|-------------------------|
| 1 | `team_create` | `tools/lifecycle.ts` (`createTeamCreateTool`) | Spawn a team. Args: `{ teamName? \| inline_spec?, leadSessionId? }` (exactly one of `teamName` / `inline_spec`). Inline spec is an object or JSON string. |
| 2 | `team_delete` | `tools/lifecycle.ts` (`createTeamDeleteTool`) | Tear down. Args: `{ teamRunId, force? }`. Lead-only unless `force=true` on `orphaned`/`deleting`. |
| 3 | `team_shutdown_request` | `tools/lifecycle.ts` (`createTeamShutdownRequestTool`) | Lead asks one member to wrap up. Args: `{ teamRunId, targetMemberName }`. |
| 4 | `team_approve_shutdown` | `tools/lifecycle.ts` (`createTeamApproveShutdownTool`) | Member or lead acks. Args: `{ teamRunId, memberName }`. |
| 5 | `team_reject_shutdown` | `tools/lifecycle.ts` (`createTeamRejectShutdownTool`) | Reject. Args: `{ teamRunId, memberName, reason }`. |
| 6 | `team_send_message` | `tools/messaging.ts` (`createTeamSendMessageTool`) | Mailbox send. Args: `{ teamRunId, to, body, kind?: "message"\|"announcement", correlationId?, summary?, references?[] }`. `to: "*"` is lead-only broadcast. Shutdown kinds are rejected — must use lifecycle tools. |
| 7 | `team_task_create` | `tools/tasks.ts` (`createTeamTaskCreateTool`) | Shared task list. Args: `{ teamRunId, subject, description, blockedBy?[] }`. |
| 8 | `team_task_list` | `tools/tasks.ts` (`createTeamTaskListTool`) | Args: `{ teamRunId, status?, owner? }`. |
| 9 | `team_task_update` | `tools/tasks.ts` (`createTeamTaskUpdateTool`) | Args: `{ teamRunId, taskId, status, owner? }`. `status: "claimed"` routes through `claimTask` (sets owner + claimedAt). |
| 10 | `team_task_get` | `tools/tasks.ts` (`createTeamTaskGetTool`) | Args: `{ teamRunId, taskId }`. |
| 11 | `team_status` | `tools/query.ts` (`createTeamStatusTool`) | Aggregate runtime view. Args: `{ teamRunId }`. Backed by `aggregateStatus` in `team-runtime/status.ts`. |
| 12 | `team_list` | `tools/query.ts` (`createTeamListTool`) | Declared + active teams. Args: `{ scope?: "user"\|"project"\|"all" }`. |

Return shape is uniform: every tool returns a JSON-stringified object (e.g. `{ teamRunId, ... }`, `{ task, ... }`, `{ messageId, deliveredTo }`).

---

## 2. Shared mailbox shape

**Wire format** is the `Message` Zod schema (`src/features/team-mode/types.ts:65-76`):

```ts
export const MessageSchema = z.object({
  version: z.literal(1),
  messageId: z.string().uuid(),
  from: z.string(),
  to: z.string(),                 // member name or "*" (broadcast)
  kind: z.enum(MESSAGE_KINDS),    // see below
  body: z.string().max(32 * 1024),// hard cap, separate from message_payload_max_bytes
  summary: z.string().optional(),
  references: z.array(TeamReferenceSchema).optional(),  // [{ path, description? }]
  timestamp: z.number().int().positive(),
  correlationId: z.string().uuid().optional(),
  color: z.string().optional(),
})
```

`MESSAGE_KINDS` (`types.ts:3-9`): `message | shutdown_request | shutdown_approved | shutdown_rejected | announcement`. The `team_send_message` tool only emits `message` or `announcement`; the other three are reserved for lifecycle tools (`messaging.ts:208-210`).

**On-disk transport** is per-member inbox directories under `~/.omo/runtime/{teamRunId}/inboxes/{member}/`. Two file types (`team-mailbox/send.ts:121-129`):

- `{messageId}.json` — committed, unread message.
- `.delivering-{messageId}.json` — live-delivery reservation; renamed to `processed/` on success, released back on failure, reclaimed on team resume (10-min TTL).

**Delivery algorithm** (`send.ts:104-137`): for each recipient, take a per-inbox file lock, sum current unread bytes + serialized payload bytes; reject with `RecipientBackpressureError` if it would exceed `recipient_unread_max_bytes` (default 256 KB). Then `atomicWrite` the file. `getUnreadSizeBytes` deliberately includes `.delivering-*.json` in its tally so the reservation is debited from the budget.

**Two delivery paths** for `team_send_message` (`messaging.ts:55-58` + `messaging.ts:230-244`):

1. **Inbox (durable).** Always executed first via `sendMessage`. Survives crashes.
2. **Live (best-effort).** `deliverLive` calls `client.session.promptAsync(...)` against the recipient's opencode session when the recipient is `idle` and has no pending injected messages. On any failure it falls back to the inbox — the doc states "fire-and-forget".

**Broadcast semantics:** `to: "*"` is **lead-only**; the send tool throws `BroadcastNotPermittedError` (`messaging.ts:217-219`, `send.ts:32-34`).

---

## 3. Member lifecycle (spawn → work → vote → retire)

The doc's 5-step list maps to:

1. **Spawn.** `team_create` resolves a `TeamSpec` (named file or `inline_spec`), validates, then calls `createTeamRun` in `team-runtime/create.ts:89-186`. The runtime state is created with `status: "creating"`, then the member loop spawns background tasks via `bgMgr.launch({ ... agent, parentSessionId, teamRunId, ... })`. Each spawned member gets a fresh opencode session registered in `team-session-registry`. Status transitions to `"active"` once all members resolve (`create.ts:184`).
2. **Delegate.** Lead uses `team_send_message` (broadcast) and `team_task_create` to assign work. Task lifecycle: `pending → claimed → in_progress → completed | deleted` (`TASK_STATUSES`, `types.ts:13`).
3. **Claim + execute.** Members call `team_task_update` with `status: "claimed"` (handled specially via `claimTask` which records owner + `claimedAt` in `types.ts:65-75`). Members report back via `team_send_message` directed at the lead.
4. **Shutdown handshake.** Lead calls `team_shutdown_request`; member responds with `team_approve_shutdown` or `team_reject_shutdown` (must give a `reason`). `ShutdownRequest` records `requestedAt`, optional `approvedAt` / `rejectedAt` / `rejectedReason` (`types.ts:107-115`).
5. **Retire.** `team_delete` is **lead-only and refuses active members** unless `force=true` on `orphaned` or stuck `deleting` states (`lifecycle.ts:189-198`). It calls `deleteTeam` which cancels background tasks, removes worktrees, and tears down the tmux layout (see §6).

Runtime `RUNTIME_STATUSES` (`types.ts:15-23`): `creating | active | shutdown_requested | deleting | deleted | failed | orphaned`. This is what `team_status` aggregates.

There is **no vote / consensus primitive** in `team-mode` itself. The repo does have a separate `src/features/consensus/` and `src/tools/consensus/` (visible in the tree listing), but they are independent of team mode.

---

## 4. The 8-members / 4-in-flight limits

Two distinct caps, enforced at different layers.

**8 members max — schema-level, fail-fast.**

`types.ts:49`:

```ts
members: z.array(MemberSchema).min(1).max(8),
```

Parsed by `TeamSpecSchema`; a 9th member throws at `team_create` time. Default `maxMembers: 8` is also stored in `RuntimeBoundsSchema` (`types.ts:98-104`) but the Zod constraint is what actually rejects.

**4 in flight — runtime worker pool, not strict concurrency.**

`team-runtime/create.ts:104`:

```ts
const workerCount = Math.min(config.max_parallel_members, spec.members.length)
```

Implementation: a `Promise.all` of `workerCount` async loops, each atomically pulling `nextMemberIndex++` until the members array is exhausted (`create.ts:106-150`). For an 8-member team with default `max_parallel_members: 4`, the first 4 launches run in parallel, and the next 4 begin as soon as the previous worker frees up (not when a member goes idle — it's launch-time parallelism, not steady-state concurrency). `createMemberWorktree` and `resolveMember` happen inside the worker; failure of any worker marks `failure` and short-circuits remaining iterations. A wall-clock deadline of `max_wall_clock_minutes` (default 120 min) bounds the whole spawn loop (`create.ts:103-107`).

**Other runtime bounds** (`types.ts:98-104`, all in `RuntimeBoundsSchema`):

- `maxMembers`: 8
- `maxParallelMembers`: 4
- `maxMessagesPerRun`: 10 000
- `maxWallClockMinutes`: 120
- `maxMemberTurns`: 500

**Eligible agents** are gated by `AGENT_ELIGIBILITY_REGISTRY` (`types.ts:108-156`):

- **Eligible:** `sisyphus`, `atlas`, `sisyphus-junior`
- **Conditional:** `hephaestus` (requires `teammate: "allow"` in tool-config)
- **Hard-reject:** `oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus` (all read-only or restricted to plan-mode — they cannot write mailbox files)

Hard-reject agents throw at parse time (`types.ts:168-176`). The doc explicitly says use `delegate-task` for those.

---

## 5. How a user enables `team_mode`

**Config location** (per the doc, "Enable" section):

- User scope: `~/.config/opencode/oh-my-openagent.jsonc`
- Project scope: `.opencode/oh-my-openagent.jsonc`

Minimal config:

```jsonc
{
  "team_mode": {
    "enabled": true,
    "max_parallel_members": 4,
    "max_members": 8,
    "tmux_visualization": false
  }
}
```

**Full schema** lives under `src/config/schema/team-mode` (per `send.ts:4` import). All 11 fields enumerated in the doc: `enabled`, `tmux_visualization`, `max_parallel_members`, `max_members`, `max_messages_per_run`, `max_wall_clock_minutes`, `max_member_turns`, `base_dir` (default `~/.omo`), `message_payload_max_bytes` (default 32768), `recipient_unread_max_bytes` (default 262144), `mailbox_poll_interval_ms` (default 3000).

**Team specs** (declarations) live at `~/.omo/teams/{name}/config.json` (user) or `<project>/.omo/teams/{name}/config.json` (project). When both define the same name, project wins. Alternatively, `team_create` accepts an `inline_spec` to skip the file entirely.

**Restart required.** The 12 tools are registered into the tool registry at plugin init; on startup the plugin logs the resolved `team_mode` state and the team tool count. `bunx oh-my-opencode doctor` includes a `team-mode` diagnostic (tmux/git availability, declared count, active runtime dirs).

No environment variable toggle was found in source.

---

## 6. tmux pane integration

Optional, gated by `team_mode.tmux_visualization: true`. Implementation lives in `src/features/team-layout-tmux/` (separate submodule within `team-mode/`).

- Each member gets a dedicated tmux pane attached to that member's opencode session via `opencode attach`. Pane runs the full interactive TUI.
- Panes start in the member's worktree if `worktreePath` is set, otherwise the repo root.
- `team_delete` closes panes and tears down the team layout.
- Per-member shutdown closes just that pane and rebalances.
- Failures are isolated — a missing `tmux` binary never blocks team creation; the panes simply don't appear.

`createTeamLayout` is called from `create.ts:181` as part of spawn finalization. A separate `activate-team-layout.ts` in `team-runtime/` is the entrypoint. Cross-references: `team-runtime/activate-team-layout.ts`, `team-layout-tmux/sweep-stale-team-sessions.ts` (called from `create.ts:99` to GC stale pane state).

**Note:** there is also a `src/features/tmux-subagent/` (general-purpose tmux subagent manager, used during spawn) — distinct from the per-team layout module.

---

## 7. Storage layout

Reproduced from the doc's "Storage layout" section; matches the in-code path helpers (`team-registry/paths.ts`, `team-state-store/store.ts`):

```
~/.omo/
├── teams/{name}/config.json                      # declared specs
├── .highwatermark                                # parity marker for runtime state
└── runtime/{teamRunId}/
    ├── state.json                                # durable runtime state (RuntimeStateSchema)
    ├── inboxes/{member}/{uuid}.json              # mailbox (atomic per-message files)
    ├── inboxes/{member}/.delivering-{uuid}.json  # transient live-delivery reservation
    ├── inboxes/{member}/processed/               # acked messages
    └── tasks/{id}.json                           # shared task list
```

`listUnreadMessages` (in the poller) ignores dotfile entries, so the reservation never double-injects via the fallback poll.

---

## 8. Honest gaps

- **No deep-read of `team-tasklist/`, `team-state-store/`, `team-registry/loader.ts`, `team-worktree/`, or `team-runtime/shutdown.ts`.** The doc plus the touched files give a complete surface picture, but the internal state-machine transitions in `shutdown.ts` and task-list write semantics were not directly inspected. Behavior described in §3 is the doc's claim, cross-referenced against schema and the lifecycle tool's arg validation; not verified by reading the `deleteTeam` and `requestShutdownOfMember` implementations.
- **The exact list of 12 tool names** was reconstructed from 4 source files (`lifecycle.ts` re-exports 5 via `tools/index.ts`; `messaging.ts`, `tasks.ts`, `query.ts` each define their own factories). I did not find a single barrel that exports all 12 — the top-level tool registry (`create-tools.ts`) was not fetched, so the wiring path into opencode's tool registry is inferred.
- **No env var** for enabling `team_mode` was found in the surveyed code; the doc only documents the JSONC path. If a flag exists, it would be in `plugin-config.ts` or a CLI loader, neither of which was opened.
- **`max_member_turns: 500`** is listed in `RuntimeBoundsSchema` defaults but the enforcement site was not located in the surveyed files. Likely a background-task config in `create.ts` or `bgMgr.launch(...)`, but unverified.
- **No "vote" / consensus mechanism** in team-mode itself. The repo has `src/features/consensus/`, which is unrelated.

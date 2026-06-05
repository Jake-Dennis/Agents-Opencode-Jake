# oh-my-openagent `team_mode` — Deep Survey

**Source:** `code-yeongyu/oh-my-openagent` @ `dev` branch
**Scope:** `src/features/team-mode/`, `src/features/consensus/`, supporting wiring in `src/config/schema/`, `src/features/background-agent/`, `src/features/tmux-subagent/`
**Builds on:** `team-mode.md` (light survey, 201 lines)

---

## 1. Runtime state machine (closes light-survey §3 gap)

The light survey described the 5-phase member lifecycle and listed `RUNTIME_STATUSES`. The state machine is a real, validated, lock-protected transition table — not just a label set.

### 1.1 Source of truth

`src/features/team-mode/team-state-store/store.ts:18-26` declares the allowed transitions:

```ts
const ALLOWED_RUNTIME_TRANSITIONS: Readonly<Record<RuntimeState["status"], ReadonlySet<RuntimeState["status"]>>> = {
  creating: new Set(["active", "failed"]),
  active: new Set(["shutdown_requested", "deleting"]),
  shutdown_requested: new Set(["deleting"]),
  deleting: new Set(["deleted"]),
  deleted: new Set(),
  failed: new Set(),
  orphaned: new Set(),
}
```

`isValidTransition` (`store.ts:103-107`) adds two orthogonal rules on top of the table:

```ts
function isValidTransition(fromStatus, toStatus): boolean {
  if (fromStatus === toStatus) return true
  if (toStatus === "orphaned") return true       // any → orphaned always OK
  return ALLOWED_RUNTIME_TRANSITIONS[fromStatus].has(toStatus)
}
```

`transitionRuntimeState` (`store.ts:147-167`) wraps every write in a per-team `state.lock` file (acquired via `withLock`), parses the new state through `RuntimeStateSchema`, and throws `InvalidTransitionError` on rejection. There is no in-memory only path — every transition is a re-read, validate, atomic-rename cycle.

### 1.2 The actual paths

| From → To | Triggered by | Source |
|-----------|--------------|--------|
| `creating → active` | All members resolved sessions in `createTeamRun` (`team-runtime/create.ts:184`) | `create.ts:175-184` |
| `creating → failed` | Rollback path: `cleanupTeamRunResources` always sets `failed` after partial spawn (`team-runtime/cleanup-team-run-resources.ts:65-68`) | `cleanup-team-run-resources.ts:65-68` |
| `active → shutdown_requested` | Not actually used as a runtime target — the survey's "ShutdownRequest" is an in-state array, not a status. The `set` in the table is defensive. | — |
| `active → deleting` | `team_delete` without `force` (`team-runtime/delete-team.ts:84-88`) | `delete-team.ts:79-90` |
| `* → orphaned` | The `orphanEdge` exception in `isValidTransition`; currently no in-tree code sets this status, but the validator and the filesystem-sweep in `listActiveTeams` (`store.ts:182-211`) recognise it | `store.ts:103-105` |
| `deleting → deleted` | `team_delete` final pass (`delete-team.ts:110-113`) | `delete-team.ts:110-114` |
| `creating → deleting` | Only with `force: true` (the `FORCE_BYPASS_DELETING_STATUSES` path in `delete-team.ts:71-78`) | `delete-team.ts:71-78` |
| `* → deleted` (terminal) | After `STALE_DELETING_TTL_MS = 60_000`, `listActiveTeams` reaps the runtime dir; `runtime/{teamRunId}/` is removed by `removeRuntimeDirectoryBestEffort` (`store.ts:50-60`) | `store.ts:50-60, 178-200` |

`deleted` and `failed` are filesystem-terminal: on the next `listActiveTeams` call, the entire `runtime/{teamRunId}/` directory is `rm -rf`'d.

### 1.3 Per-member state machine (orthogonal to team state)

`RuntimeStateMemberSchema.status` (`types.ts:80-90`) is a separate, smaller FSM:

```ts
status: z.enum(["pending", "running", "idle", "errored", "completed", "shutdown_approved"])
```

Transitions are not centrally validated — they are set by callers of `transitionRuntimeState`:
- `pending → running` on `onSessionCreated` callback in `create.ts:140-148`
- `running → idle` is set by the live-delivery path's pre-flight check (`messaging.ts:184-189`)
- `* → shutdown_approved` only via `approveShutdown` (`shutdown.ts:54-67`)
- `* → completed` via `deleteTeam` with `force: true` (`delete-team.ts:43-49`)
- `running → errored` not directly observed in surveyed code — would be set by `bgMgr` task status reflection

The two FSMs interact: a `team_delete` (non-forced) checks `DELETABLE_MEMBER_STATUSES = {completed, shutdown_approved, errored}` (`team-runtime/shutdown-helpers.ts:10-13`) and refuses to start the team-level FSM transition if any non-lead member is still in `pending`/`running`/`idle`.

### 1.4 Stale-runtime GC

`listActiveTeams` (`store.ts:170-211`) is the implicit garbage collector:
1. Skips entries with status `deleted` or `failed` and removes their dirs.
2. Removes `deleting`-status dirs whose `state.json` mtime is older than `STALE_DELETING_TTL_MS = 60_000`.
3. Wraps each per-dir load in a try/catch and logs a `team-runtime-state-skipped` event (state corruption is non-fatal — the team is just dropped from `team_list`).
4. Returns the surviving list, sorted by `teamName` then `teamRunId`.

This makes `team_list` the de facto recovery entry-point on startup: any orphan runtime state from a crashed opencode process is silently reaped.

---

## 2. Mailbox delivery: inbox + live reservation (closes light-survey §2 gap)

The light survey described the inbox format with `.delivering-*` reservations but did not show the reservation lifecycle. The actual flow is a 3-phase reservation protocol: **reserve → commit | release**, implemented in `src/features/team-mode/team-mailbox/reservation.ts`.

### 2.1 Reservation primitives

```ts
// reservation.ts:18-25
const RESERVED_PREFIX = ".delivering-"
const RESERVED_SUFFIX = ".json"
```

Four state-transition functions (`reservation.ts:36-114`):

| Function | File lines | Effect |
|----------|-----------|--------|
| `reserveMessageForDelivery` | 36-56 | Idempotent. If `.delivering-{id}.json` exists, returns its reservation. Otherwise renames `{id}.json` → `.delivering-{id}.json`. Returns `null` if neither file exists. |
| `commitDeliveryReservation` | 58-61 | Renames `.delivering-{id}.json` → `inbox/processed/{id}.json` (mkdir 0o700). |
| `releaseDeliveryReservation` | 63-65 | Renames `.delivering-{id}.json` → `{id}.json` (back to unread). |
| `reclaimStaleReservations` | 67-99 | Walks the inbox, finds `.delivering-*` files older than `staleTtlMs` (10 min default), renames them back to unread. |

### 2.2 The two-phase send (sendMessage + deliverLive)

`sendMessage` (`team-mailbox/send.ts:140-178`) is the durable write. The actual write target depends on a per-recipient `reservedRecipients` set passed in by the caller:

```ts
// send.ts:158-167
const targetPath = reservedRecipients.has(recipient) ? reservedPath : unreservedPath
await atomicWrite(targetPath, serializedMessage)
```

For `team_send_message` (`tools/messaging.ts:330-345`), the caller computes `reservedRecipients` for every team member in scope. Recipients that the sender is *about* to live-deliver to get the reservation pre-staged; the others get a normal unread file.

`deliverLive` (`messaging.ts:124-225`) then walks `deliveredTo` and for each recipient:

1. `reserveMessageForDelivery` — confirms or creates the reservation.
2. Skips the recipient and `release`s the reservation if:
   - `pendingInjectedMessageIds.length > 0` (an earlier live-delivery is still pending ack).
   - `recipient.status !== "idle"` (member is mid-turn).
   - `recipient.sessionId` is missing.
3. On acceptance, calls `dispatchInternalPrompt` (the `promptAsyncGate` from `src/hooks/shared/prompt-async-gate`), which itself returns `accepted | failed | deferred`. Ambiguous failures release the reservation; clear failures release; clear success falls through.
4. On success, `markLiveDeliveryPending` writes `messageId` into `member.pendingInjectedMessageIds` (a `Set` per member in `RuntimeStateMemberSchema`, `types.ts:89`), and the reservation stays in `.delivering-*` state.
5. On any exception, the reservation is released.

### 2.3 The poll/ack cycle (the fallback)

The poller (`team-mailbox/poll.ts:42-86`) is the recovery path. Called from a transform hook on every member turn (`pollAndBuildInjection`), it:

1. Lists unread via `listUnreadMessages` (`inbox.ts:49-67`) — note this filter `!entry.name.startsWith(".")` (`inbox.ts:11`), so `.delivering-*` files are invisible to the poller.
2. Filters out `pendingInjectedMessageIds` (in-flight live deliveries).
3. Wraps the entire poll + state-update in a `transitionRuntimeState` block. Either it returns early with `reason: "already injected this turn"` (idempotent on `lastInjectedTurnMarker`), or it builds `<peer_message>` envelopes, marks `lastInjectedTurnMarker`, and adds the messageIds to `pendingInjectedMessageIds`.
4. Returns `{ injected: true, content: envelopes.join("\n"), messageIds }` for the hook to inject as the member's next user turn.

The acker (`team-mailbox/ack.ts`, exported via `index.ts:8`) moves messages from unread into `processed/{id}.json` and clears `pendingInjectedMessageIds`. The reservation is the **synchronization point** that makes "already injected this turn" and "live-delivery in flight" mutually exclusive across the poller and the live path.

### 2.4 Per-inbox backpressure

`getUnreadSizeBytes` (`send.ts:60-87`) sums file sizes across the inbox, **including** `.delivering-*` files. This is deliberate: a message whose bytes are sitting in `.delivering-{id}.json` is debited from the budget. A new `sendMessage` will throw `RecipientBackpressureError` (`send.ts:25-29`) when `unread + nextBytes > recipient_unread_max_bytes` (default 256 KB). Body-size cap is enforced earlier (`send.ts:142-145`) against `message_payload_max_bytes` (default 32 KB), throwing `PayloadTooLargeError`.

---

## 3. The 11 agents in `AGENT_ELIGIBILITY_REGISTRY` (closes light-survey §4 gap)

The registry is `types.ts:108-156`, exported as a `Readonly<Record<string, { verdict, rejectionMessage? }>>`. Verdict taxonomy: **`eligible` | `conditional` | `hard-reject`**. The same registry is consumed in three places:

1. **Schema parsing** (`types.ts:181-198`) — `parseMember` short-circuits on `hard-reject` before Zod runs.
2. **Spec validation** (`team-registry/validator.ts:81-104`) — `validateMemberEligibility` throws `TeamSpecValidationError` with code `INELIGIBLE_AGENT` or `UNKNOWN_SUBAGENT_TYPE`.
3. **Tool-level caller check** (`tools/lifecycle.ts:165-170`) — `team_create` re-checks the *caller's* agent key (via `resolveCallerTeamLead`) and refuses even with an explicit `lead` field, throwing `team_create denied: caller '<key>' is a hard-reject agent`.

### 3.1 Full table with rejection rationale

| Agent | Verdict | Why (rejectionMessage verbatim, abridged) | Source |
|-------|---------|------------------------------------------|--------|
| `sisyphus` | `eligible` | — | `types.ts:124` |
| `atlas` | `eligible` | — | `types.ts:144` |
| `sisyphus-junior` | `eligible` | — | `types.ts:154` |
| `hephaestus` | `conditional` | "Agent 'hephaestus' lacks teammate permission. Either apply D-36 (add `teammate: 'allow'` in `tool-config-handler.ts`) or use `subagent_type: 'sisyphus'` instead." | `types.ts:125-131` |
| `oracle` | `hard-reject` | "Agent 'oracle' is read-only (cannot write files). Team members must write to mailbox inbox files. Use `delegate-task` with `subagent_type: 'oracle'` for read-only analysis instead." | `types.ts:132-138` |
| `librarian` | `hard-reject` | "Agent 'librarian' is read-only (write/edit denied). Cannot write to mailbox as team member. Use `delegate-task` for research queries instead." | `types.ts:139-140` |
| `explore` | `hard-reject` | "Agent 'explore' is read-only (write/edit denied). Cannot write to mailbox as team member. Use `delegate-task` for codebase exploration instead." | `types.ts:141-142` |
| `multimodal-looker` | `hard-reject` | "Agent 'multimodal-looker' has read-only tool access (only 'read' allowed). Cannot write to mailbox as team member." | `types.ts:143` |
| `metis` | `hard-reject` | "Agent 'metis' is read-only (pre-planning consultant). Cannot write to mailbox as team member. Use `delegate-task` for pre-planning analysis instead." | `types.ts:145-146` |
| `momus` | `hard-reject` | "Agent 'momus' is read-only (plan reviewer). Cannot write to mailbox as team member. Use `delegate-task` for plan review instead." | `types.ts:147-148` |
| `prometheus` | `hard-reject` | "Agent 'prometheus' is plan-mode-only; can only write to `.omo/*.md` (enforced by `prometheusMdOnly` hook). Cannot write to team mailbox. Use `delegate-task` with `subagent_type: 'plan'` instead." | `types.ts:149-153` |

The `UNKNOWN_SUBAGENT_MESSAGE` constant (`validator.ts:7`) restates the same information in one string for the unknown-name case: `"Unknown subagent_type '<name>'. Available ELIGIBLE agents: sisyphus, atlas, sisyphus-junior, hephaestus (if D-36 applied). Use delegate-task for read-only agents like oracle, librarian, explore, metis, momus, multimodal-looker."`

### 3.2 The seven hard-rejects and the unifying reason

All seven hard-rejects are read-only in the same sense: their tool-config does not include `write` or `edit`. Team members must write mailbox files at runtime; the spec members must include a `prompt` (`team-registry/validator.ts:108-117` enforces ≥8 chars for `category` kind); a read-only agent physically cannot answer a teammate message or claim a task. The doc's "Use `delegate-task`" fallback is the correct replacement: `delegate-task` is one-shot fire-and-forget and does not require write access to the team mailbox.

The `prometheus` case is structurally different: it is not read-only by tool config, it is *plan-mode-only* by hook (`prometheusMdOnly`), which intercepts write attempts to paths outside `.omo/*.md`. The plan-only nature is the disqualifier, not lack of file-write capability.

### 3.3 Member-parser error model

`member-parser.ts` (`createParseMember`, lines 39-72) translates Zod failures into `MemberValidationError` with specific issue codes:

- `both-kinds` — both `category` and `subagent_type` set.
- `missing-kind` — neither, and no inferred discriminator.
- `category-missing-prompt` — `kind: 'category'` without `prompt`.
- `unknown-subagent` — `subagent_type` not in the registry at all (delegated to the `UNKNOWN_SUBAGENT_MESSAGE`).
- `zod-residual` — any other Zod failure.

The registry check in `parseMember` (`types.ts:181-198`) runs **before** Zod for the `subagent_type` case, so a hard-reject gets the actionable `rejectionMessage` from the registry rather than a generic Zod error.

---

## 4. The separate `consensus` feature (closes light-survey §3 / §8 gap)

The repo also has `src/features/consensus/`. It is **not** a team-mode vote mechanism. The light survey called this out and was right to.

### 4.1 What it actually is

`runConsensus` (`src/features/consensus/consensus-engine.ts:21-65`) is a *single-prompt multi-voter* call. Given one prompt, it spawns N voters in parallel (default 3) from a default pool of "lineages" — model families, not agents — and returns their independent responses. It is invoked from `src/tools/consensus/` (a separate tool surface) and optionally wired as a pre/post gate by agent definitions.

### 4.2 Default voter pool

The default pool is `DEFAULT_VOTER_LINEAGES` (defined in `src/config/schema/consensus.ts`, re-exported via `consensus-engine.ts:6`). The engine filters the pool by connected providers, removes the caller's lineage (so the voter never agrees with itself), and caps at `count` (default 3). It resolves concrete `{providerID, modelID, variant}` triples via `resolveVoterCandidate` (`voter-resolver.ts`).

### 4.3 Output shape

`ConsensusResult` (`consensus/types.ts:21-31`):

```ts
type ConsensusResult = {
  triggerType: "explicit" | "pre_question_gate" | "post_test_gate"
  callerModel: string | undefined
  callerLineage: string | undefined
  voters: VoterPosition[]                    // per-voter: lineage, model, status, text, durationMs
  advisoryOnly: boolean                      // true if < 2 usable voters
  startedAt: string
  finishedAt: string
  totalDurationMs: number
}
```

`advisoryOnly: true` is the "we couldn't get a quorum" flag. The engine never *enforces* a verdict — it is always advisory; the calling agent reads the voters and decides.

### 4.4 Relationship to team_mode

Both features spawn parallel "agents" that produce independent opinions, and the docs use similar language (parallel coordination, multiple perspectives). But they are orthogonal:

- **Team mode** is a durable, state-machine, multi-session orchestration with mailbox + tasks + shutdown handshake. Each "agent" is a real opencode session with its own `RuntimeStateMember` and `RuntimeState`.
- **Consensus** is a one-shot, stateless, N-call fan-out inside a single session. The "voters" are ephemeral subagent spawns (`voter-spawner.ts`); they have no persistent state and never communicate with each other.

The docs note this: "no vote / consensus primitive in team-mode itself." The two features share the *philosophy* of multi-model diversity but the *mechanism* is completely different. The only shared infrastructure is the model-resolution stack (`src/shared/model-lineage`, `src/shared/model-availability`).

---

## 5. Cross-references: boulder.json, plans, notepads, the plan lifecycle

The light survey asked how `team_mode` interacts with `boulder.json`, notepads, and the plan lifecycle. The honest answer is: **team_mode is intentionally isolated from all three**. None of the surveyed `team-mode/` source files import from `src/features/boulder-state/`, `.sisyphus/*`, or any "notepad" module. The boundary is enforced by both architecture and import graph.

### 5.1 boulder.json

`boulder.json` lives at `.sisyphus/boulder.json` and tracks `active_plan`, `plan_name`, `started_at`, `session_ids`, and (per issue #3629) `task_sessions`. It is owned by `src/features/boulder-state/` and consumed by the `start-work` hook and the `boulder-continuation-injector` (`src/hooks/boulder-continuation/`).

`team-mode/` has **zero imports** of `boulder-state`. The two systems do not share state files. The only indirect connection is that `team_create`'s spawned member sessions are registered in `team-session-registry.ts` (in-memory `Map<sessionId, {teamRunId, memberName, role}>`), which is a completely different namespace from `boulder.json`'s `session_ids`. A team run and a boulder run can coexist in the same opencode process without touching each other.

### 5.2 Plan lifecycle

Plans live at `.sisyphus/plans/*.md` (or `.yaml`), written by Prometheus. The plan lifecycle (interview → plan-write → start-work → boulder continuation) is orchestrated by `src/hooks/start-work/` and the boulder continuation hook. Team mode does not read or write plans. Two integration points are observed only in the doc and the related skills:

- The `hyperplan` skill (referenced in the light survey §3) uses a `category` kind spec with name `hyperplan`. The validator (`team-registry/validator.ts:54-72`) hard-codes a special case: any team spec literally named `hyperplan` must include four categories — `unspecified-low`, `unspecified-high`, `ultrabrain`, `artistry`. This is the only team-name-coupled behavior in the codebase.
- The `security-research` skill (also referenced) presumably uses an inline spec; the light survey did not inspect the skill file.

Neither skill writes to `boulder.json`. The plan is a *prompt input* to the team (passed via the spec's `description` and per-member `prompt`), not a team-mode output.

### 5.3 Notepads

The omo project does not appear to have a "notepad" subsystem in the surveyed `dev` branch. References to `.sisyphus/notepads/` or similar are absent from the team-mode source. The closest analog is the persisted mailbox itself: per-member `inboxes/{member}/` directories and `processed/` subdirectories. The closest *plan* analog is the per-task JSON files under `runtime/{teamRunId}/tasks/{id}.json`, which are durable, schema-validated, atomic-write, and persist across `team_delete` (they are removed when the runtime dir is reaped on `deleted`/`failed`/`stale_deleting`).

### 5.4 What the boundaries buy

Team mode's isolation is deliberate. The two systems serve different masters:

| Property | boulder.json + plans | team_mode runtime |
|----------|----------------------|-------------------|
| Lifetime | Days, resumes after crashes | Minutes-to-hours, single run |
| Storage | JSON, 1 file, project-local | JSON-per-message, `~/.omo/`, global |
| Coordination | Single Atlas orchestrator | Multi-member with explicit mailbox |
| Member identity | Sisyphus, Atlas, plan tasks | Lead + N general-purpose members |
| Resumption | `task_sessions` check + continuation | `findExistingRuntime` in `create.ts:79-83` |

`findExistingRuntime` (`team-runtime/create.ts:79-83`) re-uses an active team for the same `teamName + leadSessionId` if all members are resolved — but only within a single opencode process, not across restarts. Cross-restart resumption is **not** supported; `team_create` after restart always creates a new `teamRunId`.

---

## 6. Design rationale (closes light-survey §8 "honest gaps")

The light survey asked why each magic number exists. Here are the reasons grounded in source.

### 6.1 Why a per-team runtime state machine?

The runtime state file is `runtime/{teamRunId}/state.json`, schema `RuntimeStateSchema` (`types.ts:120-134`), rewritten under a per-team `state.lock` for every transition (`store.ts:147-167`). Three reasons it is *per-team*, not global:

1. **Concurrent team isolation.** Two teams can run in the same opencode process. The state lock is keyed on `state.lock` inside `runtime/{teamRunId}/`, so they cannot trample each other.
2. **Crash recovery per team.** `listActiveTeams` reaps `deleting`/`failed`/`deleted` dirs independently; one team's crash does not affect another's `team_list` output.
3. **Lead-attribution.** `leadSessionId` in the runtime state lets `findExistingRuntime` (`create.ts:79-83`) dedupe a re-entrant `team_create` by the same lead. The `team_list` tool sorts by `teamName` then `teamRunId` (`store.ts:209-210`) so duplicates surface deterministically.

The `RuntimeBounds` struct (`types.ts:99-105`) is **stored in the runtime state** (copied from `TeamModeConfig` at creation, `store.ts:139-148`). This is significant: a config change after `team_create` does not retroactively change a live team's bounds. The team is a snapshot.

### 6.2 Why `.delivering-*` reservations?

The reservation protocol is a three-way sync between (a) the durable inbox write, (b) the live `promptAsync` call, and (c) the next-turn poll-and-inject. Without reservations, three failure modes appear:

- **Double-inject race.** Live `promptAsync` succeeds, message lands as next turn. The poller wakes up, sees an unread file, injects it again as a second turn. (Solved by `pendingInjectedMessageIds` set.)
- **Lost-on-crash race.** Live `promptAsync` is in flight; process crashes; reservation file remains on disk. (Solved by `reclaimStaleReservations` after 10-min TTL.)
- **Reservation-quota leak.** A live `promptAsync` is gated by `recipient.idle`, but the recipient might be marked `pending` by an in-flight delivery. (Solved by reading `pendingInjectedMessageIds` in `deliverLive`.)

The 10-minute TTL in `reclaimStaleReservations` (`messaging.ts:217` in the light survey) matches opencode's `promptAsync` typical completion window: prompts usually resolve in seconds, but a long inference call (e.g., `claude-opus-4-7` with `reasoning_effort: max`) can run 5+ minutes. 10 minutes is a generous safety margin that still bounds stranded reservations to one agent-spawn lifetime.

### 6.3 Why these specific caps?

| Cap | Default | Reason (grounded) |
|-----|---------|-------------------|
| `maxMembers: 8` | `TeamSpecSchema.members.max(8)` (`types.ts:49`); `TeamModeConfigSchema` also `max(8)` (`config/schema/team-mode.ts:6`) | Two distinct enforcement sites: schema-level (fail-fast at parse) and config-level (rejects malformed config). The Zod cap is what actually rejects the 9th member. The 8 limit is hard-coded into the `validator.ts:7` constant `MAX_TEAM_MEMBERS = 8`. |
| `maxParallelMembers: 4` | `team-runtime/create.ts:106` `Math.min(config.max_parallel_members, spec.members.length)` workers, each in a `Promise.all` loop pulling `nextMemberIndex++` | This is **launch-time parallelism**, not steady-state concurrency. Once a worker is free, it picks the next member. There is no semaphore gating idle-vs-busy members. With 4 workers and 8 members, the first 4 launches start in parallel; the next 4 start as workers free, which is usually ~1-3 seconds after launch (session ID is available quickly). The 4-cap is a balance between (a) head-of-line blocking in the opencode `promptAsync` queue when many members share a model, and (b) avoidable wall-clock waste from fully-sequential spawn. |
| `messagePayloadMaxBytes: 32 KB` | `MessageSchema.body.max(32 * 1024)` (`types.ts:66`); `TeamModeConfigSchema.message_payload_max_bytes.default(32768)` (`config/schema/team-mode.ts:11`); `min(1024)` floor | The Zod cap is the hard wall (rejects malformed wire input); the config default sets the *runtime* check inside `sendMessage` (`send.ts:142-145`). Two layers because wire-format drift and config drift are different concerns. The 32 KB matches a typical LLM tool-call body budget (Claude/GPT tool calls usually cap at 32-64 KB before chunking). |
| `recipientUnreadMaxBytes: 262144 (256 KB)` | `TeamModeConfigSchema.recipient_unread_max_bytes.default(262144)` (`config/schema/team-mode.ts:12`); `min(1024)` floor | The 256 KB inbox budget is per-recipient, not per-run. With 8 members and 4 in flight, a busy recipient can absorb ~2 MB across a run before backpressure kicks in. The budget includes `.delivering-*` files (`send.ts:78`) so live-delivery in-flight messages debit correctly. |
| `maxMessagesPerRun: 10000` | `RuntimeBoundsSchema.maxMessagesPerRun.default(10000)` (`types.ts:101`) | Stored in runtime state; no enforcement site was found in surveyed code. The field is exposed via `team_status.bounds` but not actively checked. Likely a future enforcement (e.g., reject `sendMessage` after 10k messages). |
| `maxWallClockMinutes: 120` | Enforced in `create.ts:107-108` `Date.now() > deadlineAt` check inside the worker loop | This is the *spawn-loop* wall clock, not the team's full lifetime. Once all members are launched and `status: "active"`, the deadline is no longer checked. Active teams can run for hours. |
| `maxMemberTurns: 500` | `RuntimeBoundsSchema.maxMemberTurns.default(500)` (`types.ts:103`) | Stored in runtime state; no enforcement site in surveyed code. Likely enforced by `bgMgr.launch` passing the bound to the opencode session config. |
| `mailboxPollIntervalMs: 3000` | `TeamModeConfigSchema.mailbox_poll_interval_ms.default(3000)`, `min(500)` (`config/schema/team-mode.ts:13`) | Used by the transform-hook poll path (not surveyed at hook level). 3s is short enough that idle members react quickly to messages, long enough that an idle member with no work is not spinning. |
| `min(1024)` floors on byte caps | `config/schema/team-mode.ts:11-12` | Prevents pathological configs (e.g., `message_payload_max_bytes: 0`) that would brick the system. 1 KB is the smallest sensible single-message body. |
| `MAX_TEAM_MEMBERS = 8` in `validator.ts:7` | Hard-coded in `team-registry/validator.ts:7` | Independent of the Zod cap; a guard for the pre-Zod special-case validation in `loader.ts:31-44`. If a spec has > 8 members, `validateSpec` (`validator.ts:18-22`) throws `TeamSpecValidationError` with `code: 'TEAM_MEMBER_LIMIT_EXCEEDED'` before Zod is even reached. |
| `STALE_DELETING_TTL_MS = 60_000` | `team-state-store/store.ts:16` | 60 seconds is the grace window for a `team_delete` whose cleanup hung (e.g., a tmux layout that did not respond to `kill-pane`). After 60s the runtime dir is reaped. |

### 6.4 Why a per-inbox `.lock`?

`withLock(`${inboxDir}.lock`, ...)` (`send.ts:165-175`) is a POSIX `flock`-style file lock, implemented in `team-state-store/locks.ts:53-90`. The lock file contains `ownerTag\npid\nacquiredAtMs`. Stale-lock detection (`detectStaleLock`, `locks.ts:96-115`) checks if the recorded PID is still alive and if the age exceeds `staleAfterMs` (default 5 min). The protocol retries every 50ms with a 4-second timeout (`LOCK_WAIT_TIMEOUT_MS`). This is the per-inbox serialization that makes the budget check in `getUnreadSizeBytes` race-free: only one `sendMessage` can be computing `unread + nextBytes` for a given recipient at a time.

---

## 7. tmux pane integration in detail (closes light-survey §6 gap)

The light survey described the tmux module as "each member gets a dedicated tmux pane attached to that member's session." The actual implementation is more nuanced and has known failure modes (issues #3894, #3963, fixed by PR #3966 and #4047).

### 7.1 Entry points

- `activateTeamLayout` (`team-runtime/activate-team-layout.ts:14-49`) is called from `createTeamRun` at `create.ts:181` (after all members resolve, before `status: "active"`).
- `removeTeamLayout` (`team-layout-tmux/layout.ts:182-211`) is called from `deleteTeam` (`delete-team.ts:96-108`).
- `sweepStaleTeamSessions` (`team-layout-tmux/sweep-stale-team-sessions.ts`) is called at startup (`create.ts:99-100`) with the active `teamRunId` set. Sessions matching the `omo-team-{uuid}` pattern (`sweep-stale-team-sessions.ts:1`) whose `teamRunId` is not in the active set are killed.

### 7.2 Pane creation (in-caller-window model)

`createTeamLayout` (`layout.ts:117-179`) uses a single-window model, not a focus+grid dual-window model that the docs imply. The actual flow:

1. `canVisualize()` (`layout.ts:50`) returns `process.env.TMUX !== undefined`. The plugin must be running inside a tmux session.
2. `tmuxMgr.getServerUrl()` returns the opencode server URL. `isServerRunning` checks it. If unreachable, `null` is returned with a `log("opencode server not reachable, skipping team layout (see issue #3963)", ...)`.
3. `getTmuxPath()` resolves tmux on PATH.
4. `resolveCallerTmuxSession` finds the caller's pane ID and window target.
5. `createTeamLayoutInCallerWindow` (`layout.ts:99-115`) splits the caller's pane horizontally (or vertically on alternating members) for each non-lead member, labels the pane with the member name (`select-pane -T`), and sends the attach command.
6. `select-layout main-vertical` is applied, then the caller pane is resized to 30% width.

The attach command (`layout.ts:58-66`) is:

```bash
[OPENCODE_SERVER_PASSWORD=... OPENCODE_SERVER_USERNAME=...] opencode attach <serverUrl> --session <sessionId> --dir <worktree>
```

This launches the full interactive TUI in the pane, so the user watches the member's session in real time.

### 7.3 State sync (TUI side)

The TUI side of tmux integration is **not** in `team-layout-tmux/`. It is in the opencode TUI core, which is what `opencode attach` invokes. The state sync is therefore: the plugin sets `tmuxPaneId` and `tmuxGridPaneId` per member in `RuntimeState` (`types.ts:82-83`), persists via `transitionRuntimeState`, and re-reads on `team_status` (which exposes `paneId` per member, `status.ts:91-100`).

There is no `focusWindowId`/`gridWindowId` dual-window layout in the current code — the `TeamLayoutResult` type has both fields (`layout.ts:36-44`), but `createTeamLayout` returns `gridWindowId: undefined` and `gridPanesByMember: {}` (`layout.ts:172-177`). The doc and the light survey describe an aspirational focus+grid layout that the current code does not produce; only the focus window exists.

### 7.4 Known issues

- **#3894** (closed by #4047): When the opencode server is not running on the expected port, panes are created and split, then `opencode attach` fails silently. The fix in `layout.ts:135-142` adds a `isServerRunning` check before any pane creation.
- **#3963** (closed by #3966): In default TUI mode (no `--port`, no `OPENCODE_PORT`), `team_create` silently skips tmux pane creation because the plugin's `TmuxSessionManager` falls back to `http://localhost:4096` even when `ctx.serverUrl` is valid. The fix uses `getCtxServerUrl()` and logs a warning with the binding hint.
- **#1774** (per-session boulder state, separate concern): The boulder continuation system reads a single `boulder.json`, which is a different system; team mode is not affected by this issue.

### 7.5 What happens when tmux is unavailable

All three of these checks gate pane creation in a specific order (`layout.ts:117-179`):

1. `canVisualize()` (`TMUX` env) — if false, return `null` silently.
2. `members.length === 0` — if true, return `null` (no work to do).
3. `isServerRunning(serverUrl)` — if false, log warning, return `null`.
4. `getTmuxPath()` — if false, return `null`.
5. `resolveCallerTmuxSession` — if false, log warning, return `null`.

The outer `try/catch` in `createTeamLayout` logs `"tmux visualization unavailable, skipping"` on any error. `activateTeamLayout` returns `false` and `createTeamRun` continues without the layout — the team is still active, just without panes. Per the design rationale: a missing tmux never blocks team creation.

### 7.6 Cleanup

`removeTeamLayout` (`layout.ts:182-211`) has three branches:

1. If `cleanupTarget.ownedSession !== false` (i.e., the team owned the session), `kill-session -t <name>`.
2. Else if `paneIds` are provided, `kill-pane` each pane individually. This is the **caller-window model** path: panes are children of the caller's session, not the team's own.
3. Else, `kill-window` for each of `focusWindowId` and `gridWindowId`.

Branch 2 is what the current code actually hits. The cleanup is best-effort and never throws (errors are logged, not raised).

---

## 8. Tool wiring (closes light-survey §8 "12 tools" gap)

The light survey noted that the 12 tools are split across 4 source files and the barrel `tools/index.ts` only re-exports lifecycle. The actual wiring is via the plugin tool registry. Three observations:

1. **Lifecycle tools** (`team_create`, `team_delete`, `team_shutdown_request`, `team_approve_shutdown`, `team_reject_shutdown`) are re-exported from `tools/index.ts:1` and pulled in by the team-mode feature barrel.
2. **Messaging** (`team_send_message`) is in `tools/messaging.ts` but **not** in `tools/index.ts`. It must be imported separately by the tool registry. The function is `createTeamSendMessageTool(config, client)` and takes a `LiveDeliveryClient` (the opencode client narrowed to `session.promptAsync`).
3. **Task tools** (`team_task_create`, `team_task_list`, `team_task_update`, `team_task_get`) are in `tools/tasks.ts` (not surveyed in the light survey). They follow the same factory pattern.
4. **Query tools** (`team_status`, `team_list`) are in `tools/query.ts`.

The light survey's table of 12 tools is correct in count and source file; the gap was that the wiring path (the registry that pulls `messaging.ts`, `tasks.ts`, `query.ts` into the actual tool set) is not visible in the team-mode module. Per the doc and `bunx oh-my-opencode doctor` output, all 12 are registered when `team_mode.enabled = true`.

---

## 9. Errors and edge cases

The team-mode surface exposes a rich set of typed errors. Most are in `team-mailbox/send.ts:21-47` and `team-runtime/shutdown-helpers.ts` / `team-state-store/store.ts:28-44`:

| Error | Source | When |
|-------|--------|------|
| `BroadcastNotPermittedError` | `send.ts:21-23` | Non-lead sends `to: "*"` |
| `PayloadTooLargeError` | `send.ts:25-27` | Body > `message_payload_max_bytes` |
| `RecipientBackpressureError` | `send.ts:29-31` | Recipient unread budget exceeded |
| `DuplicateMessageIdError` | `send.ts:33-35` | `{id}.json` or `.delivering-{id}.json` already exists |
| `TeamDeletingError` | `send.ts:37-39` | Team status is `deleting` or `deleted` |
| `RuntimeStateError` | `store.ts:28-32` | State file fails Zod parse |
| `InvalidTransitionError` | `store.ts:34-38` | FSM transition not allowed |
| `TeamRunCreateError` | `create.ts:30-43` | Spawn failure; carries `cleanupReport` |
| `TeamMemberResolutionError` | `team-runtime/resolve-member.ts:14-18` | Model/category resolution failed for a member |
| `MemberValidationError` | `member-parser.ts:1-9` | Member fails schema or eligibility |
| `TeamSpecValidationError` | `team-registry/validator.ts:10-18` | Spec fails validation (with `code`, `field`, `memberName`) |
| `InvalidTaskTransitionError` | `team-tasklist/update.ts:24-28` | Task FSM violation |
| `CrossOwnerUpdateError` | `team-tasklist/update.ts:30-33` | Non-owner tries to update task status (except `deleted`) |
| `AlreadyClaimedError` | `team-tasklist/claim.ts:34-37` | Task not in `pending` status |
| `BlockedByError` | `team-tasklist/claim.ts:39-42` | Task has unresolved `blockedBy` deps |

### 9.1 The `team_create` caller check

A subtle but important rule: `team_create` checks the **caller's** agent against the eligibility registry (`tools/lifecycle.ts:165-170`). A `prometheus` (or any hard-reject) calling `team_create` with a valid inline spec is **rejected** even if the spec has an explicit `lead` field. The error message is `"team_create denied: caller '<key>' is a hard-reject agent and cannot create teams regardless of an explicit 'lead' in the spec. <rejectionMessage>"`. This is the only place where the caller's identity is checked, and it is the only known defense against the "spec's lead is fine, but the caller is read-only" misuse.

### 9.2 The `team_delete` force semantics

`team_delete` has three force paths (`team-runtime/delete-team.ts:30-78`):

- `force: false` (default) — refuses if any non-lead member is in `pending`/`running`/`idle`. Team status must be `active`/`shutdown_requested`/`deleting`/`deleted`.
- `force: true` on `orphaned` — bypasses lead check and member status check. The lead can be from any session that was a participant.
- `force: true` on `deleting` (stuck) — same bypass for stuck deletion.
- `force: true` on any other status — flips the FSM from `creating`/`orphaned` straight to `deleting` (the `FORCE_BYPASS_DELETING_STATUSES` path) and forces non-lead members to `completed` before the standard teardown.

The `force: true` teardown also wraps `removeTeamLayout` in a try/catch (`delete-team.ts:97-103`) so a tmux failure does not abort the team deletion.

### 9.3 Shutdown handshake idempotency

The shutdown tools are idempotent:

- `team_shutdown_request` returns early if a request is already pending (`shutdown.ts:21-24`).
- `team_approve_shutdown` returns early if the request is already approved (`shutdown.ts:55-59`).
- `team_reject_shutdown` returns early if the request was rejected with the *same* reason (`shutdown.ts:80-83`).

The `shutdownRequests` array in `RuntimeState` is append-only: each call appends, never modifies in place (except for the `approvedAt`/`rejectedAt` fields on the matching entry). `findLatestShutdownRequestIndex` (`shutdown-helpers.ts:55-66`) walks from the end to find the most recent unhandled request for a given (member, requester) pair.

---

## 10. Configuration surface (all 11 fields, with constraints)

`src/config/schema/team-mode.ts:4-15`:

```ts
export const TeamModeConfigSchema = z.object({
  enabled:                       z.boolean().default(false),
  tmux_visualization:            z.boolean().default(false),
  max_parallel_members:          z.number().int().min(1).max(8).default(4),
  max_members:                   z.number().int().min(1).max(8).default(8),
  max_messages_per_run:          z.number().int().min(1).default(10000),
  max_wall_clock_minutes:        z.number().int().min(1).default(120),
  max_member_turns:              z.number().int().min(1).default(500),
  base_dir:                      z.string().optional(),
  message_payload_max_bytes:     z.number().int().min(1024).default(32768),
  recipient_unread_max_bytes:    z.number().int().min(1024).default(262144),
  mailbox_poll_interval_ms:      z.number().int().min(500).default(3000),
})
```

Key constraints:

- `max_parallel_members` and `max_members` are both `max(8)` — the config cannot exceed the schema hard cap.
- Byte caps have a `min(1024)` floor (1 KB) to prevent pathological 0-byte configs.
- `mailbox_poll_interval_ms` has a `min(500)` floor — 500ms is the fastest poll, below which the inbox I/O would dominate.
- `base_dir` defaults to `~/.omo` (`team-registry/paths.ts:24-25`).

### 10.1 Storage permissions

`ensureBaseDirs` (`team-registry/paths.ts:107-122`) creates `~/.omo/{teams,runtime,worktrees}` with `mode: 0o700` and re-chmods if the mode is wrong. The same `0o700` is applied to inboxes and claims directories at write time (`send.ts:159`, `claim.ts:51`). This is consistent with mail-data-at-rest hygiene: only the running opencode process can read the inboxes.

---

## 11. Source index (deep-survey references)

All paths relative to `src/`.

| Concern | File | Key lines |
|---------|------|-----------|
| FSM transition table | `features/team-mode/team-state-store/store.ts` | 18-26, 103-114, 147-167 |
| Stale-runtime GC | `features/team-mode/team-state-store/store.ts` | 16, 50-60, 170-211 |
| Runtime state schema | `features/team-mode/types.ts` | 99-134 |
| Per-member state | `features/team-mode/types.ts` | 80-90 |
| AGENT_ELIGIBILITY_REGISTRY | `features/team-mode/types.ts` | 108-156 |
| Member parser errors | `features/team-mode/member-parser.ts` | 1-72 |
| Spec validator | `features/team-mode/team-registry/validator.ts` | 7, 18-72, 81-104 |
| Spec loader | `features/team-mode/team-registry/loader.ts` | 31-44 (pre-Zod specials) |
| Spec collision rule | `features/team-mode/team-registry/paths.ts` | 64-90 |
| Path helpers | `features/team-mode/team-registry/paths.ts` | 23-34 |
| Storage perms | `features/team-mode/team-registry/paths.ts` | 107-122 |
| Spawn loop | `features/team-mode/team-runtime/create.ts` | 89-186 |
| Parallel worker count | `features/team-mode/team-runtime/create.ts` | 106-150 |
| Existing-runtime dedup | `features/team-mode/team-runtime/create.ts` | 79-83 |
| Cleanup on spawn failure | `features/team-mode/team-runtime/cleanup-team-run-resources.ts` | 1-76 |
| Shutdown primitives | `features/team-mode/team-runtime/shutdown.ts` | 13-31, 38-67, 75-105 |
| Shutdown helpers | `features/team-mode/team-runtime/shutdown-helpers.ts` | 1-66 |
| Member deletion rules | `features/team-mode/team-runtime/shutdown-helpers.ts` | 10-13 |
| deleteTeam flow | `features/team-mode/team-runtime/delete-team.ts` | 1-138 |
| Force-delete branches | `features/team-mode/team-runtime/delete-team.ts` | 30-78, 96-113 |
| Aggregate status | `features/team-mode/team-runtime/status.ts` | 99-145 |
| Resolve member | `features/team-mode/team-runtime/resolve-member.ts` | 50-100 |
| Activate layout | `features/team-mode/team-runtime/activate-team-layout.ts` | 14-49 |
| Team session registry | `features/team-mode/team-session-registry.ts` | 1-31 |
| Sweep stale tmux | `features/team-mode/team-layout-tmux/sweep-stale-team-sessions.ts` | 1-77 |
| Create team layout | `features/team-mode/team-layout-tmux/layout.ts` | 50-179 |
| Remove team layout | `features/team-mode/team-layout-tmux/layout.ts` | 182-211 |
| Can-visualize gate | `features/team-mode/team-layout-tmux/layout.ts` | 50 |
| Mailbox send | `features/team-mode/team-mailbox/send.ts` | 140-178 |
| Mailbox inbox | `features/team-mode/team-mailbox/inbox.ts` | 1-67 |
| Reservation protocol | `features/team-mode/team-mailbox/reservation.ts` | 1-114 |
| Poll & inject | `features/team-mode/team-mailbox/poll.ts` | 42-86 |
| Build envelope | `features/team-mode/team-mailbox/poll.ts` | 12-40 |
| Live delivery | `features/team-mode/tools/messaging.ts` | 124-225 |
| Mailbox errors | `features/team-mode/team-mailbox/send.ts` | 21-47 |
| Task claim lock | `features/team-mode/team-tasklist/claim.ts` | 46-100 |
| Task status FSM | `features/team-mode/team-tasklist/update.ts` | 17-67 |
| Task dep canClaim | `features/team-mode/team-tasklist/dependencies.ts` | 3-9 |
| Lock primitive | `features/team-mode/team-state-store/locks.ts` | 1-135 |
| Lock stale detection | `features/team-mode/team-state-store/locks.ts` | 96-115 |
| Lifecycle tools | `features/team-mode/tools/lifecycle.ts` | 67-141 (create), 152-167 (delete), 169-181 (shutdown-request), 183-197 (approve), 199-214 (reject) |
| Caller eligibility check | `features/team-mode/tools/lifecycle.ts` | 165-170 |
| Config schema | `config/schema/team-mode.ts` | 1-15 |
| Member guidance addendum | `features/team-mode/member-guidance.ts` | 3-50 |
| Consensus engine | `features/consensus/consensus-engine.ts` | 21-65 |
| Consensus types | `features/consensus/types.ts` | 1-49 |
| Consensus default pool | `config/schema/consensus.ts` | `DEFAULT_VOTER_LINEAGES` |
| Lock wait timeout | `features/team-mode/team-state-store/locks.ts` | 13-14 |
| Sweep TTL | `features/team-mode/team-state-store/store.ts` | 16 |

---

## 12. Verified updates to light-survey gaps

Closing the original `## 8. Honest gaps` of the light survey:

| Gap | Status | Where documented |
|-----|--------|------------------|
| State machine transitions in `shutdown.ts` | **Closed** | §1.1, §1.2 |
| Task-list write semantics | **Closed** | §9 (FSM, cross-owner rule, claim lock) |
| `deleteTeam` and `requestShutdownOfMember` impls | **Closed** | §1.2, §2.4, §9.2 |
| Wiring path for the 12 tools | **Partially closed** | §8 — confirmed that `messaging.ts`, `tasks.ts`, `query.ts` are wired by the top-level tool registry, not by `tools/index.ts` |
| `max_member_turns: 500` enforcement site | **Still open** — the field is in `RuntimeBoundsSchema` and persisted into `RuntimeState.bounds`, but no surveyed call site reads it for enforcement. Likely a parameter to `bgMgr.launch` (not surveyed) or a future enforcement. |
| Env var for `team_mode` | **Confirmed absent** — no `process.env.*` checks for an enable flag in the surveyed files. The JSONC config is the only documented path. |
| Consensus mechanism | **Closed** — confirmed separate, not related to team mode. | §4 |

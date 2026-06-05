# Notepads System in oh-my-openagent — Deep Survey

**Snapshot:** `code-yeongyu/oh-my-openagent` @ `dev`, 2026-06-05.
**Companion:** [`../notepads.md`](../notepads.md) (light survey, 161 lines).
**Scope:** close the light survey's honest-gaps, document the `notepad-write-guard` hook in source, cross-reference boulder.json / team_mode / plan lifecycle, and explain the design rationale for the 5-file / append-only / per-plan choices.

The light survey correctly identified the public surface but had to mark seven items as "could not be verified without a clone." All seven are now closed with webfetched source. Two new artifacts not in the light survey: (a) the **`sisyphus-junior-notepad` hook** (the actual mechanism that injects the prompt) and (b) a **separate `.omo/evidence/` directory** with `task-N-*.txt` files used by the package-layering-refactor plan (commit `44f057d`) — these are not "notepads" but they live alongside them and are produced by the same ultrawork workflow.

---

## 1. Closing the honest-gaps

### 1.1 The actual prompt text that drives append behavior — found

The light survey stated "the write is prompt-instructed, not programmatically enforced" and could not show the prompt. The canonical source is the exported `NOTEPAD_DIRECTIVE` constant in `src/hooks/sisyphus-junior-notepad/constants.ts` on `dev` (verified by webfetch). Verbatim:

```ts
export const HOOK_NAME = "sisyphus-junior-notepad"

export const NOTEPAD_DIRECTIVE = `
<Work_Context>
## Notepad Location (for recording learnings)
NOTEPAD PATH: .omo/notepads/{plan-name}/
- learnings.md: Record patterns, conventions, successful approaches
- issues.md: Record problems, blockers, gotchas encountered
- decisions.md: Record architectural choices and rationales
- problems.md: Record unresolved issues, technical debt

You SHOULD append findings to notepad files after completing work.
IMPORTANT: Always APPEND to notepad files - never overwrite or use Edit tool.

## Plan Location (subagent: READ ONLY)
PLAN PATH: .omo/plans/{plan-name}.md

SUBAGENT PLAN RESTRICTION (applies to YOU, the delegated worker — NOT to the Orchestrator):
- You may READ the plan to understand your assigned tasks
- You may READ checkbox items to know what to work on
- You MUST NOT edit the plan file or mark checkboxes — that is the Orchestrator's job
- The Orchestrator (Atlas) updates checkboxes after verifying your completed work
</Work_Context>
`
```

**Closure of gap #1 from the light survey (§6.1):** the directive is **4 files, not 5**. `verification.md` is conspicuously absent from the worker directive even though `docs/guide/orchestration.md` lists 5 files and the boulder chat artifacts reference verification. The asymmetry is intentional — verification is the *orchestrator's* job (it runs `lsp_diagnostics`, `bun test`, etc. and writes the result). The worker is told what it could/should log (learnings, issues, decisions, problems), not what it verified.

> See §6 below for a more detailed cross-check against the older #1150 prompt.

### 1.2 The injection mechanism — found

The directive is prepended to a subagent's prompt by a `tool.execute.before` hook on the `task` tool. Source `src/hooks/sisyphus-junior-notepad/hook.ts` (webfetched, line numbers from the file):

```ts
export function createSisyphusJuniorNotepadHook(ctx: PluginInput) {
  return {
    "tool.execute.before": async (
      input: { tool: string; sessionID: string; callID: string },
      output: { args: Record<string, unknown>; message?: string }
    ): Promise<void> => {
      // 1. Check if tool is task
      if (input.tool !== "task") { return }
      // 2. Check if caller is Atlas (orchestrator)
      if (!(await isCallerOrchestrator(input.sessionID, ctx.client))) { return }
      // 3. Get prompt from output.args
      const prompt = output.args.prompt as string | undefined
      if (!prompt) { return }
      // 4. Check for double injection
      if (prompt.includes(SYSTEM_DIRECTIVE_PREFIX)) { return }
      // 5. Prepend directive
      replaceToolArgs(output, { prompt: NOTEPAD_DIRECTIVE + prompt })
      // 6. Log injection
      log(`[${HOOK_NAME}] Injected notepad directive to task`, { sessionID: input.sessionID })
    },
  }
}
```

**Five guarantees from this 14-line handler:**

1. **Fires only on `task` tool calls.** Other Atlas tools (read, write, bash, glob) do not get the directive.
2. **Fires only when the caller is Atlas** (via `isCallerOrchestrator(sessionID)` against `ctx.client`). Other orchestrators (Sisyphus, Hephaestus, Prometheus) do not inject it. This is the guard PR #3147 tightened — see §1.4.
3. **Idempotent.** The `SYSTEM_DIRECTIVE_PREFIX` check prevents the directive from being prepended twice if some upstream layer also injected it.
4. **Prepend, not replace.** Atlas's user prompt is preserved at the tail.
5. **Log-only observability.** The `log()` call records each injection but does not return a value to the caller — failure is silent.

**This is the entire "propagation mechanism."** The light survey's "prompt-instructed" characterization is now exact: a 14-line hook in `src/hooks/sisyphus-junior-notepad/` is what causes the 4-file directive to appear in every Sisyphus-Junior subagent's prompt.

### 1.3 The `notepad-write-guard` from CHANGELOG `f313eb1` — partially misnamed

The CHANGELOG line "Notepad-write-guard wired and extended to `.omo/notepads`, preventing accidental overwrites in the new workspace layout" refers to a **path-coverage extension to the pre-existing `write-existing-file-guard` hook**, not a new hook named "notepad-write-guard." The pre-existing hook was introduced in PR #1476 (referenced in issue #1871) and originally blocked all `write` calls to existing files with the message *"File already exists. Use edit tool instead."*

The f313eb1 extension moved the exemption from a hard-coded `.sisyphus/*.md` check (added in PR #1593 to fix #1576) to a generic `isOmoWorkspacePath(canonicalPath)` check. Source `src/hooks/write-existing-file-guard/tool-execute-before-handler.ts:90-95` (webfetched, current `dev`):

```ts
if (isOmoWorkspacePath(canonicalPath)) {
  log("[write-existing-file-guard] Allowing .omo/** overwrite", {
    sessionID: input.sessionID,
    filePath,
  })
  invalidateOtherSessions(readPermissionsBySession, canonicalPath, input.sessionID)
  return
}
```

And the matcher (`tool-execute-before-handler.ts:34-36`):

```ts
export function isOmoWorkspacePath(canonicalPath: string): boolean {
  return /(^|[/\\])\.omo([/\\]|$)/.test(canonicalPath)
}
```

**Closure of gap #6 from the light survey (§6.6):** the "knowledge is dead-end data" problem is *not* solved by this hook. The hook only permits the subagent to overwrite its own notepad (i.e. re-`write` a file that already exists). It does not promote the contents anywhere. RFE #1397 is the actual feature that would close the loop and it remains unimplemented (see §5.2 below).

### 1.4 The hook's read-gate and the append-only contradiction

The hook is not a simple block. It is a *read-gate*: a `read` unlocks exactly one `write` to the same file. This was the second major iteration of the hook, designed in response to issue #1871 ("write-existing-file-guard causes significant token waste"). Source `tool-execute-before-handler.ts:140-150` (webfetched, current `dev`):

```ts
if (input.sessionID && consumeReadPermission({ sessionID: input.sessionID, canonicalPath, readPermissionsBySession, sessionLastAccess })) {
  log("[write-existing-file-guard] Allowing overwrite after read", {
    sessionID: input.sessionID, filePath, resolvedPath,
  })
  invalidateOtherSessions(readPermissionsBySession, canonicalPath, input.sessionID)
  return
}

log("[write-existing-file-guard] Blocking write to existing file", { ... })
throw new Error("File already exists. Use edit tool instead.")
```

State held by the hook (`hook.ts:67-69`):

```ts
const readPermissionsBySession = new Map<string, Set<string>>()  // sessionID -> set of canonical paths read
const sessionLastAccess = new Map<string, number>()               // sessionID -> last access ts
const maxTrackedSessions = options?.maxTrackedSessions ?? MAX_TRACKED_SESSIONS              // 256
const maxTrackedPathsPerSession = options?.maxTrackedPathsPerSession ?? MAX_TRACKED_PATHS_PER_SESSION  // 1024
```

**This creates a direct contradiction with the notepad directive's "always APPEND":**

- A subagent that follows the directive literally must *append* — i.e. write a new combined file replacing the old one. With the write-guard's read-gate, the subagent must first `read` the notepad, then `write` the original + new content. The hook's invalidate-other-sessions line means that no other session can write to that file until the writing session's read-token is consumed.
- If the subagent skips the `read` and tries to `write` a fresh notepad file (which doesn't yet exist), the hook returns early (`if (!existsSync(resolvedPath)) { return }` at `tool-execute-before-handler.ts:88`) and the write proceeds — i.e. the first-ever write to a notepad works without a read-gate, as expected.
- If two subagents try to write the same notepad concurrently, the second one is **silently rate-limited by the read-gate**, not blocked. They both succeed but each "consumes" the other's read-permission, which means the *next* attempt to write the same file by either will be blocked. This is a per-session, per-file, single-use token.

**Resolution of the contradiction in practice:** the prompt's "use `bash` to append" is the only clean path. `cat >> .omo/notepads/{plan-name}/learnings.md` (or PowerShell equivalent) bypasses the write-guard entirely. The 4-file directive's "always APPEND" is enforced by **bash redirection**, not by the `write` tool.

### 1.5 The directive was re-scoped in April 2026 — PR #3147

The light survey quoted the *original* (pre-Apr 2026) directive with the wording *"SACRED and READ-ONLY" / "VIOLATION = IMMEDIATE FAILURE."* That wording is **no longer the canonical text**. PR #3147 (Apr 5, 2026) replaced it with the current scoping-aware version, which adds the explicit line *"applies to YOU, the delegated worker — NOT to the Orchestrator."* The PR body (webfetched) is explicit:

> *"The current NOTEPAD_DIRECTIVE still says the plan file is 'SACRED and READ-ONLY' with 'VIOLATION = IMMEDIATE FAILURE'. That wording is unscoped and can be misread as a universal constraint, even though this hook is specifically prepended to delegated worker prompts."*

The fix is behaviour-preserving — subagents still cannot modify the plan, but the directive now states that explicitly as a subagent-only rule and names Atlas as the actor that updates plan state. This is a small but real fix to a known source of confusion (the maintainer was getting bug reports like #1576 / #1363 where Prometheus *itself* was being blocked from updating its own plan).

### 1.6 The `glob` bug is real and is fixed — but old installs are still affected

Light survey gap #4 (the glob tool) is now characterized with the exact fix. Issue #631 (Jan 9, 2026, `chilipvlmer`) reported: agents using `glob(".sisyphus/notepads/**/*.md")` got `[]` back, even though the files existed. The fix shipped in PR #720 (Jan 13, 2026) by defaulting `hidden: true` and `follow: true` on the glob tool to align with OpenCode's internal ripgrep behaviour. The PR also added a `follow?: boolean` option. Test count: 18 tests / 21 assertions.

**For users on `dev` today:** notepads are findable. **For users on `v3.0.0-beta.2` (the issue's pinned version):** notepads are still invisible to glob. The bug is closed, but any pre-Jan-13-2026 install (v3.0.0-beta.2 and earlier) is silently broken. The light survey correctly identified this class of failure; the deep survey adds the ship date and the test count.

### 1.7 Gitignore is consistent across both paths

Light survey §6.7 was correct. Current `dev/.gitignore` (webfetched) has identical `!rules/` exceptions for both:

```
.omo/*
!.omo/rules/
!.omo/rules/**
.sisyphus/*
!.sisyphus/rules/
!.sisyphus/**
```

Note: `.sisyphus/**` (the second stanza) is *not* actually a no-op because it was negated by the preceding `.sisyphus/*` rule — `**` does not match under `*` in gitignore semantics. The result is: `.sisyphus/rules/` is the only allowed tracked content under `.sisyphus/`. Same for `.omo/`. The user's notepads, plans, and boulder.json are all gitignored.

---

## 2. Cross-references: boulder.json, team_mode, plan lifecycle

### 2.1 Notepads and boulder.json — co-located, co-synced, co-scoped

Both notepads and boulder.json live under `<worktree>/.sisyphus/` (or `.omo/`), are gitignored, and are plan-scoped. The sync between worktree and main repo is performed by `syncSisyphusStateFromWorktree()`, shipped in commit `19ab3b5` to fix issue #2853. The fix's commit message (webfetched) is explicit:

> *"add worktree-sync.ts: syncSisyphusStateFromWorktree() copies `.sisyphus/` contents from worktree to main repo directory. update start-work.ts template: documents the sync step as CRITICAL when worktree_path is set in boulder.json. update work-with-pr/SKILL.md: adds explicit sync step before worktree removal."*

The 5 tests in `worktree-sync.test.ts` (webfetched) include a specific notepad scenario:

```ts
test("#given nested .sisyphus dirs in worktree #when syncing #then copies full tree recursively", () => {
  const worktreePlans = join(WORKTREE, ".sisyphus", "plans")
  const worktreeNotepads = join(WORKTREE, ".sisyphus", "notepads", "my-plan")
  ...
  writeFileSync(join(worktreeNotepads, "learnings.md"), "learned something")
  ...
  expect(readFileSync(join(MAIN_REPO, ".sisyphus", "notepads", "my-plan", "learnings.md"), "utf-8")).toBe("learned something")
})
```

`worktree-sync.ts` (from the diff in `19ab3b5`) is 34 lines and uses `cpSync(srcDir, destDir, { recursive: true, force: true })`. It copies the entire `.sisyphus/` tree including `notepads/`, `plans/`, `boulder.json`, and any other artifact.

**Implication:** notepads are part of the same "ephemeral, worktree-scoped, gitignored" cohort as boulder.json. They share the same worktree-removal hazard, the same gitignore-by-design reasoning, and the same `start-work` resume semantics. If a worktree is removed without first running the sync, **both** boulder.json and notepad content are lost. (See issue #2853's bug body: *"OmO later resumes / continues using outdated state and may treat completed steps as incomplete."*)

### 2.2 Notepads and team_mode — orthogonal, with one convergence point

Team mode (per the team-mode.md light survey) is a 12-tool mailbox orchestration feature with its own per-team runtime state under `~/.omo/runtime/{teamRunId}/`. It does not read or write to the notepad directory. The two systems are **architecturally separate**:

| Aspect | Notepads | team_mode |
|---|---|---|
| Location | `<worktree>/.omo/notepads/{plan-name}/` | `~/.omo/runtime/{teamRunId}/` |
| Scope | Per-plan | Per-team-run |
| Lifetime | Until manually deleted | Until `team_delete` |
| Visible to | Subagents via prompt | Team members via mailbox |
| State store | Five markdown files | Per-message atomic JSON |
| Gitignored? | Yes | No (user-home) |

**The one convergence point:** the `sisyphus-junior-notepad` hook fires whenever Atlas calls `task(...)`, and team_mode's `team_create` spawns members via `bgMgr.launch({ ... agent: 'sisyphus-junior' ... })`. So when a team member is a Sisyphus-Junior that receives a task via the team mailbox, the same `tool.execute.before` hook fires on that member's `task` tool calls (provided the *caller* is Atlas — see §1.2). In a team-mode run, the lead is Atlas; team members are not orchestrators. So a team member invoking `task` does **not** have the directive injected on its outbound delegations. (Unverified: whether `isCallerOrchestrator` correctly returns `false` for a non-Atlas-team-member session. The hook's log statement is the only observable signal.)

### 2.3 Notepads and the plan lifecycle — the central fact

Notepads are *named by the same key as the plan folder*. The Prometheus planner creates a plan at `.omo/plans/{plan-name}.md` (the key choice is the plan's slug — see `docs/guide/orchestration.md`). The notepad folder is then `.omo/notepads/{plan-name}/`. The two are not auto-discovered from each other; the link is the *name* the orchestrator chooses at delegation time, which the `sisyphus-junior-notepad` hook templatizes as `{plan-name}`.

**Lifecycle interactions:**

| Phase | Who | What touches notepads |
|---|---|---|
| Plan created | Prometheus (via `prometheus-md-only` hook, restricted to `.omo/*.md`) | Nothing. The plan file is created; the notepad folder is not. |
| `/start-work` invoked | Atlas (via start-work hook) | Reads `boulder.json`, creates if missing. Does not create the notepad folder. |
| First subagent dispatched | Atlas → `task(...)` → `sisyphus-junior-notepad` hook fires → directive prepended | The subagent is *told* the notepad path. It creates the folder + files on first append. |
| Subagent writes | Subagent via `bash cat >> ...` (bypasses write-guard) or `write` with read-gate (allowed because `.omo/**` is exempted anyway) | Notepad file created/appended. |
| Subagent returns to Atlas | Atlas reads response, extracts learnings, formats digest for next subagent | Reads from the notepad via `bash cat` or `read` (or just by inspecting the response). |
| Worktree removed | `worktree-sync.ts` runs first | `.omo/notepads/` recursively copied to main repo. |
| Next session resumes | `boulder.json` says plan is incomplete; user re-runs `/start-work` | `notepads/{plan-name}/` is found in main repo and continues to be appended. |

**One subtle interaction:** if the subagent uses the `write` tool to a notepad file (rather than `bash cat >>`), the write-guard's `.omo/**` exemption fires *and* the read-gate is irrelevant. The exemption is unconditional for any `.omo/**` path. So notepad writes that go through the `write` tool are completely unblocked; the read-gate mechanism (the more sophisticated part of the hook) only matters for writes *outside* `.omo/`.

---

## 3. Design rationale

### 3.1 Why 5 files (and why the worker sees only 4)

The 5-file split in `docs/guide/orchestration.md` maps to the orchestrator's *Wisdom Accumulation* categorization (also from the orchestration guide):

> *"Categorize into: Conventions, Successes, Failures, Gotchas, Commands"*

…which is 5 categories, and the 5 notepad files do map 1:1 — but with `verification.md` being the *command-results* bucket:

| Notepad file | Orchestrator category | Written by |
|---|---|---|
| `learnings.md` | Conventions + Successes (positive knowledge) | Subagents (Sisyphus-Junior) |
| `issues.md` | Failures + Gotchas (friction Atlas logs) | Subagents + Atlas |
| `decisions.md` | Architecture choices with rationale | Subagents |
| `verification.md` | Commands — test/build results, lsp_diagnostics | **Atlas only** (runs the checks) |
| `problems.md` | Long-term unresolved | Subagents (final entry per task) |

The worker directive's omission of `verification.md` is a **separation-of-concerns pattern**: the worker is told to *report* what it did; the orchestrator is told to *verify* what it did. The "inherited wisdom" section of an Sisyphus-Junior delegation (per issue #1150's template) typically *reads* from `learnings.md` and `decisions.md` but not from `verification.md` — verification is the orchestrator's output, not its input. The `NOTEPAD_DIRECTIVE` text in `constants.ts` reflects this asymmetry precisely.

### 3.2 Why append-only

The light survey correctly identified that the system is append-only with no schema and no eviction. The deeper design rationale is **avoiding the merge-conflict class of failures**:

- A subagent may be many turns into a task when it remembers to write the notepad. By the time it writes, another subagent (or a parallel one in the same run) may have already appended. Append-without-merge is the only commutative write operation available in a text file. `read` + `write` (the read-gate pattern) loses concurrent writes.
- The prompt's "never use Edit tool" rule is a corollary — Edit operates on a string match that may be invalidated by a concurrent append.
- The 4-file directive also instructs `bash cat >> ...` as the canonical mechanism, which is append-at-end by construction.

**Cost:** no eviction, no size cap, no schema. A multi-day plan that runs hundreds of delegated tasks will produce a `learnings.md` that grows linearly with the task count. The package-layering-refactor plan in commit `44f057d` produced a 116-line `learnings.md` and a 19-line `decisions.md` — evidence the files can grow into the hundreds but are not unbounded under normal use. RFE #1397's lift-to-`AGENTS.md` feature would break the append-only invariant by introducing a *move* operation; that is why it is gated on a PR-only workflow with a validator (see §5.2).

### 3.3 Why per-plan scope

Three reasons, in priority order:

1. **Boulder alignment.** `boulder.json` is keyed by `plan_name`. The notepad folder is keyed by the same name. When `/start-work` resumes a boulder, it knows the plan name and therefore knows which notepad to load. If notepads were per-session or per-user, the resume would have to either (a) merge all relevant notepads or (b) pick one heuristically. Per-plan scope makes resume trivial.
2. **Disposal-by-association.** Discussion #2999 (JonasDoe, Apr 1 2026) asks *"are they meant to be persisted/committed for future work, unrelated to the original plan, or can I drop them?"* — unanswered as of 2026-06-05. The implicit answer from the design is: **drop them**. The `.gitignore` and the absence of any lift mechanism make this the default. Per-plan scope makes disposal safe: deleting the plan folder deletes its notepads atomically.
3. **No merge logic.** Two plans with the same name in the same repo would collide on `.omo/notepads/{plan-name}/`. The planner (Prometheus) is responsible for picking a unique slug; the design assumes this is enforced upstream. The maintainer's stance is "docs are the warning" — no runtime check.

A subtle consequence: **a subagent running in worktree A cannot share notepads with a subagent in worktree B unless they have the same `plan_name`.** The `syncSisyphusStateFromWorktree` function (commit `19ab3b5`) copies notepads from worktree to main repo, but does *not* merge them — it uses `cpSync({ force: true })`, which overwrites. Two parallel worktrees on the same plan would lose notepad data on the second `worktree remove`. This is not flagged in the docs.

### 3.4 Why gitignored

Issue #2853 is the canonical reference. The maintainer's position: *"`boulder.json` contains session IDs, active plan pointers, and runtime state that is inherently local… Committing it would create merge conflicts on every branch switch and pollute git history with ephemeral state."* Notepads share the same justification, plus a content sensitivity angle: `learnings.md` may contain code snippets, file paths, or fragments of error output that are not appropriate to commit alongside source code.

The `.gitignore` rule (current `dev`):

```
.omo/*
!.omo/rules/
!.omo/rules/**
.sisyphus/*
!.sisyphus/rules/
!.sisyphus/rules/**
```

Note that the second `!.sisyphus/rules/**` is an inconsistency in the actual file (the `*` does not match `rules/...`). The `!`-exceptions only match `.omo/rules/...` in practice. This is a minor file-content bug, not a behavioural one.

---

## 4. The `notepad-write-guard` hook in detail (commit `f313eb1`)

The CHANGELOG line for `f313eb1` (webfetched verbatim) is:

> *"Notepad-write-guard wired and extended to `.omo/notepads`, preventing accidental overwrites in the new workspace layout."*

In the release-gate "Fixed in this release gate" section. The actual change is a 1-line code diff to `src/hooks/write-existing-file-guard/tool-execute-before-handler.ts` that broadens the existing exemption from `.sisyphus/*.md` to any `.omo/**` path via the `isOmoWorkspacePath` regex.

### 4.1 The hook's 5-rule decision tree (current source)

For a `write` tool call to a path inside the session root, in order:

1. **Path is not inside the session root** → return, no action. (`isPathInsideDirectory` check.)
2. **Path does not exist on disk** → return, write proceeds. (`!existsSync(resolvedPath)`.)
3. **Path is `.omo/**` (the new exemption from `f313eb1`)** → log and return, write proceeds; other sessions' read-tokens invalidated.
4. **Caller passed `overwrite: true`** → log and return, write proceeds; token invalidated.
5. **Caller previously read this path in the same session** → consume the read-token, log, return; write proceeds; other sessions' tokens invalidated.
6. **Otherwise** → throw `"File already exists. Use edit tool instead."`

For a `read` tool call:

- If the file exists, register the canonical path in `readPermissionsBySession[sessionID]`.
- Bound by `MAX_TRACKED_PATHS_PER_SESSION = 1024` (LRU-evicted via `trimSessionReadSet`).
- Bound by `MAX_TRACKED_SESSIONS = 256` (LRU-evicted via `evictLeastRecentlyUsedSession`).

### 4.2 What the hook does NOT do

It does not:
- Block `write` to non-existent files (rule 2).
- Block `write` to any path outside the session root (rule 1).
- Block `edit` tool calls (only `write` is checked).
- Block `bash` redirects (the bash tool is unchecked).
- Detect a `write` that *replaces* a file with identical content (no SHA check).
- Persist state across process restarts (the Map is in-memory; restart = empty Map = first `read` re-registers).

### 4.3 The token-state lifecycle

The hook is per-process. `readPermissionsBySession` is a `Map<sessionID, Set<canonicalPath>>` held in module scope by `createWriteExistingFileGuardHook`. The map is **never persisted** — a process restart loses all read-tokens. The hook's `event` handler (in `hook.ts:102-114`) deletes a session's entry on `session.deleted`, which is the only way entries leave the map during normal operation.

**Implication for notepads specifically:** because the `.omo/**` exemption (rule 3) is unconditional, the read-gate state is irrelevant for notepad writes. The hook is a *no-op* for `.omo/notepads/**` writes. It only matters for writes outside `.omo/` that target files the agent has read.

This is the right behavior for a notepad — the read-gate would block concurrent subagents from writing the same notepad (each `write` to an existing file by a different session would be blocked, because their read-tokens are invalidated by the previous session's write). Without the `.omo/**` exemption, the notepad system would not work at all in multi-subagent plans.

### 4.4 Why the CHANGELOG called it "notepad-write-guard" — a guess

The maintainer's release-gate CHANGELOG line uses the nickname "notepad-write-guard" while the actual hook name in code is `write-existing-file-guard`. The nickname is descriptive of *what changed in this commit* (the notepad path is now exempted), not of the hook itself. The hook is shared with `.sisyphus/*.md` plans (since PR #1593) and would be shared with any future workspace-rooted artefact directory. The actual hook name reflects the general-purpose intent; the CHANGELOG reflects the specific change.

---

## 5. Issue #2897 — silent failures in parallel delegation

### 5.1 The bug

Issue #2897 (tad-hq, Mar 27 2026) — *"Atlas has no clue how to spawn parallel agents most of the time"*. Body verbatim (webfetched):

> *"Using sonnet 4.6, with cliproxyapi for Claude usage. This issue existed prior to me switching to this provider. It's just terrible at this. Even after multiple messages of you stating you need to include multiple messages in 1 tool call it still fails terribly at this simple task."*

The user expects Atlas to issue **parallel** `task(...)` tool calls in a single turn (a single assistant message with N tool invocations). Instead, Atlas serializes them: one tool call per turn, N turns total, no parallelism. The maintainer closed it as "not planned" with the label `triage:question`.

### 5.2 Why this is structurally relevant to notepads

The notepad wisdom-pass-forward loop is **inherently sequential**. The propagation is prompt-instructed, not data-driven:

1. Subagent A returns its response to Atlas.
2. Atlas (in its next turn) reads the response, extracts the digest, formats a new prompt.
3. Atlas dispatches subagent B with the digest prepended/inlined.
4. Subagent B starts, may write to the notepad.
5. Loop.

The flow is by design a per-task *extract → re-dispatch* cycle. Even with #2897's parallel-spawning fixed, the notepad loop cannot be parallel because step 2 (Atlas's synthesis) is the rate-limiting step. The light survey's "weak Atlas model may skip the synthesis step" failure mode is the same class of bug as #2897 — a model that fails to follow the structural instruction.

### 5.3 Documented reliability work in the same area

CHANGELOG `f313eb1` references a series of fixes in the v4.2.0 / v4.2.1 / v4.2.3 release chain for related silent-failure modes (webfetched verbatim from the CHANGELOG diff):

- **First-prompt watchdog** (PR #4051, commit `a130fa70d`) — *"The final watchdog logic shipped via #4051 + `a130fa70d` covers subagent first-prompt silence past 90 seconds with cleanup via session.deleted."* This is a *timeout-driven* reliability mechanism: a subagent that does not produce any tool call within 90s of being dispatched is killed and the session is cleaned up. It does not address #2897's "serial instead of parallel" failure, but it bounds the blast radius.
- **Runtime-fallback synthetic continuation** (PR #3645) — *"Synthetic continuation when session messages are empty, preventing silent failure on Git operations and other empty-history retries."* This is a recovery path, not a prevention.
- **Delegate-task empty-history fallback** (BLOCKER-4, PR #3825 reverted by PR #4044) — *"Relanded BLOCKER-4 delegated child-session empty-history fallback. Runtime fallback now consumes the captured bootstrap prompt when a delegated child session fails before history is persisted."* The original PR was reverted because its own regression test failed on clean root `bun test` (per the v4.2.0 CHANGELOG footnote). The reland target is v4.2.1.
- **Todo-continuation-enforcer** (PR #4013) — *"Stops looping after all todos are complete."* This is the "sisyphus never stops" myth-mechanic, made less infinite.
- **Atlas boulder continuation** (v4.2.1 CHANGELOG) — *"Atlas boulder continuation now hard-stalls after three consecutive continuation turns with no successful bash/edit/write tool progress, preventing the #3446 runaway loop where text-only blocker reports kept the session alive for hours."*

None of these fix #2897's underlying model-behaviour issue. The pattern across all of them is **timeouts and counters that bound failure** rather than fixes that prevent the model from failing. This is consistent with the design philosophy documented in the orchestration guide: *"The intelligence is in the system, not a single worker model."* — the harness adds belts and suspenders, the model is treated as a probabilistic component.

### 5.4 Status as of survey date

Issue #2897 is **closed as not planned**. No PR is linked. The fix in the same release gate that would help is PR #4121 (CHANGELOG: *"delegate_task now supplies sensible defaults for `run_in_background` and `load_skills` instead of throwing when they are omitted"*), which is *adjacent* but not the same — defaults do not force parallel.

---

## 6. Issue #1150 — the full subagent prompt template (which omits `verification.md`)

Issue #1150 (chaunsin, Jan 26 2026) is the canonical reference for the subagent prompt template. The TUI log in the bug report contains the full prompt the Sisyphus-Junior subagent received, including the `<Work_Context>` block. The relevant excerpt (webfetched verbatim from the issue body):

```
<system-reminder>
[SYSTEM DIRECTIVE: OH-MY-OPENCODE - SINGLE TASK ONLY]
**STOP. READ THIS BEFORE PROCEEDING.**
If you were NOT given **exactly ONE atomic task**, you MUST:
1. **IMMEDIATELY REFUSE** this request
2. **DEMAND** the orchestrator provide a single, specific task
...
</system-reminder>
<Work_Context>
## Notepad Location (for recording learnings)
NOTEPAD PATH: .sisyphus/notepads/{plan-name}/
- learnings.md: Record patterns, conventions, successful approaches
- issues.md: Record problems, blockers, gotchas encountered
- decisions.md: Record architectural choices and rationales
- problems.md: Record unresolved issues, technical debt
You SHOULD append findings to notepad files after completing work.
IMPORTANT: Always APPEND to notepad files - never overwrite or use Edit tool.
## Plan Location (READ ONLY)
PLAN PATH: .sisyphus/plans/{plan-name}.md
CRITICAL RULE: NEVER MODIFY THE PLAN FILE
...
</Work_Context>
```

**Differences from the current `src/hooks/sisyphus-junior-notepad/constants.ts`:**

| Aspect | #1150 (Jan 2026) | Current `constants.ts` (post-#3147) |
|---|---|---|
| Notepad path | `.sisyphus/notepads/...` | `.omo/notepads/...` |
| Files listed | 4 (no `verification.md`) | 4 (no `verification.md`) |
| Plan restriction wording | "NEVER MODIFY THE PLAN FILE" / "VIOLATION = IMMEDIATE FAILURE" | "SUBAGENT PLAN RESTRICTION (applies to YOU, the delegated worker — NOT to the Orchestrator)" |
| Orchestrator scope | Not mentioned | Explicitly named as the actor that updates checkboxes |

**The 4-vs-5 file discrepancy is consistent across both versions.** `verification.md` has *never* been in the worker-facing directive as far as can be reconstructed from public sources. The orchestration guide (`docs/guide/orchestration.md`) lists 5 files but the worker only sees 4. This confirms §3.1: `verification.md` is the orchestrator's output bucket.

**The `SYSTEM DIRECTIVE: SINGLE TASK ONLY` wrapper is unrelated to notepads** — it is a different `system-reminder` injected by the delegate-task tool to prevent subagent scope creep. It is not the `SYSTEM_DIRECTIVE_PREFIX` checked by the `sisyphus-junior-notepad` hook for double-injection. (Verified: the `notepad-write-guard` source uses `SYSTEM_DIRECTIVE_PREFIX` imported from `../../shared/system-directive`; the "SINGLE TASK ONLY" text is the delegate-task tool's own reminder, a separate system. This is why PR #4036 in the f313eb1 CHANGELOG says *"prometheus-md-only replaced the SYSTEM DIRECTIVE marker with an XML tag in external prompts"* — the SYSTEM DIRECTIVE marker was a single string being abused by multiple systems, and the rename is part of the de-conflation.)

---

## 7. Related artifacts (not in the light survey)

### 7.1 `.omo/evidence/` — task evidence files

Commit `44f057d` (the package-layering-refactor plan) modified files in `.omo/evidence/` (webfetched file tree, current `dev`):

```
.omo/evidence/
├── task-1-baseline.txt
├── task-2-no-coupling.txt
├── task-2-package-exists.txt
├── task-2-reexports.txt
├── task-2-tests.txt
├── task-3-di-interface.txt
├── task-3-no-coupling.txt
├── task-3-tests.txt
├── task-5-no-coupling.txt
├── task-5-tests.txt
├── task-9-loc-check.txt
├── task-9-no-coupling.txt
└── task-9-tests.txt
```

These are not notepads — they are **task evidence files** produced by the ultrawork directive's *"RED→GREEN→SURFACE" evidence capture* (per PR #4382's added TDD contract). The naming convention is `task-{N}-{check}.txt` where `{check}` is a specific assertion (`tests`, `no-coupling`, `package-exists`, `loc-check`, `di-interface`, `reexports`). They are the ultrawork-mode equivalent of `verification.md` and live alongside notepads in the same gitignored `.omo/` tree.

**The notepad system and the evidence system are not the same** — notepads are the wisdom-accumulation pattern (human-readable summaries, distributed across 5 files), evidence is the TDD-contract pattern (machine-checkable per-task assertion outputs, one file per check). Both are gitignored. Both are plan-scoped. Both can grow unbounded. They share the gitignore rationale and the worktree-sync path; they do not share the prompt-injection mechanism (the evidence system is driven by the ultrawork prompt, not by the `sisyphus-junior-notepad` hook).

### 7.2 `.omo/ulw-loop/` — durable notepad for ultrawork (per PR #4382)

PR #4382 (May 24 2026, merged) added a *separate* durable notepad to the ultrawork directive, backed by `mktemp -t ulw-*.md`. The PR body (webfetched) lists the file structure as append-only sections:

> *"Durable notepad: mktemp -t ulw-*.md with append-only sections (Plan, Scenarios, Now, Todo, Findings, Learnings). Survives context loss; resume by re-reading."*

This is **not the same as `.omo/notepads/{plan-name}/`** — `mktemp` produces a path in `/tmp/` (Linux/macOS) or `%TEMP%` (Windows), not in the project tree. The ulw-loop notepad is per-session (lives in the OS temp directory, deleted on reboot) rather than per-plan (lives in `.omo/notepads/`). It is a complementary mechanism for surviving in-session context loss, not a replacement for the cross-task notepad.

The light survey correctly flagged this as a separate system. The deep survey adds: the section structure is `Plan | Scenarios | Now | Todo | Findings | Learnings` — note that `Verification` is again absent from the durable-notepad sections, consistent with the notepad's separation-of-concerns pattern.

---

## 8. Updated honest-gaps status

Re-stating each of the light survey's 7 honest gaps with current resolution:

1. **No source file is publicly browsable** → **Resolved.** `src/hooks/sisyphus-junior-notepad/{constants,hook,index}.ts` is the entire notepad system. There is no `src/features/notepads/` module. The system is 14 lines of hook code + 1 constant string + 1 system-directive-prefix check.
2. **The path is mid-rename** → **Confirmed.** Docs (`docs/guide/orchestration.md`) still say `.sisyphus/`; current `constants.ts` says `.omo/`; `worktree-sync.ts` copies from `.sisyphus/` (commit `19ab3b5` was pre-rename). The mismatch is consistent with the dev-branch having both rule blocks in `.gitignore`.
3. **Propagation is prompt-driven, not data-driven** → **Confirmed and now exact.** The mechanism is a 14-line `tool.execute.before` hook in `sisyphus-junior-notepad/`. The hook is gated on (a) tool=`task`, (b) caller=Atlas, (c) prompt not already containing `SYSTEM_DIRECTIVE_PREFIX`.
4. **The glob tool was broken for hidden dirs** → **Resolved (Jan 13 2026, PR #720).** Pre-PR-720 versions (v3.0.0-beta.2 and earlier) are still affected.
5. **No size/line/byte cap** → **Confirmed and unchanged.** The 116-line `learnings.md` from commit `44f057d` is the largest observed in the public sources. No size cap is documented or implied.
6. **No automated promotion to AGENTS.md** → **Confirmed, unimplemented.** RFE #1397 (open as of 2026-02-02, assigned to maintainer) is the canonical reference. PR #4382's durable notepad is a complementary mechanism, not a promotion.
7. **Gitignored by design** → **Confirmed.** `dev/.gitignore` excludes both `.sisyphus/` and `.omo/`. The `!rules/` exceptions only allow `.omo/rules/` and `.sisyphus/rules/` to be tracked. Notepads are entirely ephemeral from git's perspective.

---

## 9. Sources (with line/file paths verified via webfetch)

### Code
- `src/hooks/sisyphus-junior-notepad/constants.ts` — `NOTEPAD_DIRECTIVE` string + `HOOK_NAME` constant.
- `src/hooks/sisyphus-junior-notepad/hook.ts` — 14-line `tool.execute.before` handler; `isCallerOrchestrator` gate; `SYSTEM_DIRECTIVE_PREFIX` idempotency check.
- `src/hooks/sisyphus-junior-notepad/index.ts` — barrel export.
- `src/hooks/write-existing-file-guard/hook.ts` — `createWriteExistingFileGuardHook`, `MAX_TRACKED_SESSIONS = 256`, `MAX_TRACKED_PATHS_PER_SESSION = 1024`, `toCanonicalPath` (uses `realpathSync.native`), `isOverwriteEnabled` (`overwrite: true` bypass), `session.deleted` event handler.
- `src/hooks/write-existing-file-guard/tool-execute-before-handler.ts` — 6-rule decision tree, `isOmoWorkspacePath` regex (the `f313eb1` extension), `consumeReadPermission` (the read-gate), `invalidateOtherSessions` (the cross-session lock), `registerReadPermission` (the read-side of the gate).
- `src/hooks/write-existing-file-guard/session-read-permissions.ts` — LRU eviction helpers (`evictLeastRecentlyUsedSession`, `touchSession`, `trimSessionReadSet`).
- `src/features/boulder-state/worktree-sync.ts` (commit `19ab3b5`) — 34 lines, `cpSync` of entire `.sisyphus/` tree, 5 test cases including a notepad-specific one.
- `.gitignore` (current `dev`) — lines 2-9 covering both `.omo/*` and `.sisyphus/*` with `!rules/` exceptions.

### Issues
- #1150 (chaunsin, Jan 26 2026) — full Sisyphus-Junior subagent prompt with `<Work_Context>` block, `SYSTEM DIRECTIVE: SINGLE TASK ONLY` wrapper, and the "lottery-go-to-ts-refactor" task.
- #1364 (COLDTURNIP, Feb 1 2026) — *Session Debrief* RFE, closed as not planned. The maintainer's take: *"It is risky to update related AGENTS.md and project Skills automatically. It may introduce the possibility of prompt injection."*
- #1397 (agno01, Feb 2 2026) — *Automated Learning Capture System* RFE, assigned to maintainer, open. Consolidates 5 issues (#598, #663, #869, #1077, #1364) plus #74. Defines a 3-tier system: session `.sisyphus/learnings/{session}.jsonl` → validation → PR-based promotion to `AGENTS.md` / `CLAUDE.md` / `skill/<name>`. 5-type learning taxonomy: `incident-resolution | anti-pattern | procedure | gotcha | warning`. Conservative design — `auto_detect: false` default, PR-only workflow, no auto-merge.
- #1576 — Prometheus cannot rewrite plan file (fixed by PR #1593, which added the `.sisyphus/*.md` exception to the write-guard).
- #1871 (gustavosmendes, Feb 16 2026) — write-existing-file-guard causes token waste. Maintainer's response: confirmed valid, design is moving to a read-gate model. 14-scenario test coverage cited.
- #2853 (AlgoOy, Mar 26 2026) — task state lost across worktree→main sync. Closed via commit `19ab3b5`.
- #2897 (tad-hq, Mar 27 2026) — Atlas cannot spawn parallel agents. Closed as not planned.

### PRs
- #720 (kdcokenny, Jan 13 2026) — `fix(glob): default hidden=true and follow=true`. Closed #631. 18 tests / 21 assertions.
- #1476 — introduced `write-existing-file-guard`.
- #1593 (code-yeongyu, Feb 7 2026) — `fix: allow Prometheus to overwrite .sisyphus/*.md plan files`. Path check anchored to `ctx.directory` to prevent false positives; `path.normalize()` applied before `startsWith`.
- #3147 (EZotoff, Apr 5 2026) — `fix(sisyphus-junior-notepad): scope plan directive to delegated workers`. Re-worded the directive to explicitly scope the plan-readonly rule to subagents.
- #4013 — todo-continuation-enforcer stops looping after all todos complete.
- #4044 — reverts PR #3825 (BLOCKER-4) because its regression test failed.
- #4051 + commit `a130fa70d` — first-prompt watchdog (90s timeout, session.deleted cleanup).
- #4121 — `delegate_task` supplies sensible defaults for `run_in_background` and `load_skills`.
- #4382 (code-yeongyu, May 24 2026) — ultrawork TDD, scenario contract, durable notepad, reviewer gate. Adds `mktemp -t ulw-*.md` durable notepad with 6 sections (Plan, Scenarios, Now, Todo, Findings, Learnings). Char deltas: default +26%, gpt +37%, gemini +14%.

### Commits
- `44f057d` (May 20 2026) — package-layering-refactor plan with 116-line `learnings.md`, 19-line `decisions.md`, and 13 `task-N-*.txt` evidence files.
- `f313eb1` — release-gate commit: *"Notepad-write-guard wired and extended to `.omo/notepads`, preventing accidental overwrites in the new workspace layout."* Actual code change is 1 line in `tool-execute-before-handler.ts` (broadens exemption to all `.omo/**` paths).
- `19ab3b5` — worktree-sync fix for #2853; 144 insertions across 5 files; 5 unit tests.
- `a4c45e2` (Apr 18 2026) — `fix(write-existing-file-guard): defer realpath/existsSync to first tool call`. Lazy-initializes `canonicalSessionRoot` to avoid running `realpathSync.native` on plugin startup. Test delta: 3→3 existsSync calls (one more due to lazy init), 1→2 realpathNative calls.

### Discussion
- #2999 (JonasDoe, Apr 1 2026) — *"How should I handle `sisyphus/`, esp. the learnings?"* Unanswered. The implicit design answer: drop them; they are plan-scoped and ephemeral.

### Documentation
- `docs/guide/orchestration.md` — *Wisdom Accumulation* section; 5-file notepad tree block; Atlas flow diagram (Read → Analyze → Accumulate Wisdom → Delegate → Verify → Report).
- `src/features/boulder-state/AGENTS.md` (auto-generated 2026-05-15) — *"Atomic writes: temp file → fsync (where supported) → rename. File lock prevents concurrent corruption."* (Note: the boulder light survey notes this is aspirational; the actual `storage.ts` still uses `writeFileSync` on the current `dev`.)

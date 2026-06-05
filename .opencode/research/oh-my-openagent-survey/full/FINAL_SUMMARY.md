# `oh-my-openagent` Final Survey — Synthesis for Agents-Opencode-Jake

**Surveyed repo:** https://github.com/code-yeongyu/oh-my-openagent (branch `dev`, snapshot 2026-06-05). The npm package is still published as `oh-my-opencode`; both names refer to the same project (mid-rename).
**Builds on:** [`../SUMMARY.md`](../SUMMARY.md) (light-survey synthesis, 4 areas).
**Adds:** the 11-agent roster, the full 4-phase plan-lifecycle loop, and adoption candidates surfaced by the 8 newly-surveyed areas (4 agent docs + 4 orchestration docs).

**Project priorities of Agents-Opencode-Jake** (the lens for every verdict):
1. **Single-model** — one provider/model, no routing layer.
2. **Auditability** — every state change is inspectable post-hoc.
3. **Plan-as-artifact** — implementation plans live as markdown files, not JSON blobs.
4. **ADRs** — architectural decisions recorded in `.opencode/decisions/adr-NNN-*.md`.
5. **Mechanical verify gates** — verification is programmatic, not prompt-driven.

---

## 1. TL;DR

- **The 11-agent roster is the most distinctive part of `oh-my-openagent`, and most of it is untranslatable to this project.** The 4 primary agents (Sisyphus, Hephaestus, Prometheus, Atlas) plus 7 subagents (Sisyphus-Junior, Oracle, Metis, Momus, Librarian, Explore, Multimodal-Looker) are all built around multi-model category routing, parallel fan-out, and capability-gated activation. The project's single-model + `@mention` dispatch is structurally simpler, and adopting even one of these agents would import the multi-model machinery the project has explicitly rejected.
- **The 4-phase plan lifecycle (Prometheus plan → Momus review → Atlas execute → Oracle verify) is a clean conceptual pattern, but every phase has a markdown-native equivalent in the project already.** The conductor already does plan-as-artifact, @reviewer, @tester, and verification via the work-log. The lifecycle is worth studying as a *vocabulary*, not as a *template*.
- **The light survey's four "weak fit" verdicts hold up under the deep read.** Boulder.json's `works` map, team_mode's 8-member mailbox, the notepad append-only files, and the 8-category routing chains all encode priorities orthogonal to this project's. None of the deep-survey evidence flips a verdict.
- **Two NEW ideas are strong fits and worth a small design exercise:** the **Momus 4-criteria plan-review rubric** (Clarity / Verification / Context / Big Picture with 100/80/90/0 thresholds) and the **`prometheus-md-only` style role-boundary hook** (a `tool.execute.before` guard that *mechanically* blocks an agent from writing outside its permitted paths — exactly the kind of programmatic enforcement this project wants).
- **Two more ideas are weak-but-worth-noting:** the **`/handoff` command template** (a portable session-context markdown export — could become an ADR or handoff template) and the **non-main-session guard for keyword injection** (if the project ever adds keyword detection, only fire on the main session to avoid prompt-injection loops in subagent turns).
- **The project should explicitly NOT replicate four things:** prompt-driven enforcement (notepads), documentation-only "dangerous override" detection (categories), mid-rename paths (`.sisyphus/` → `.omo/`), and the auto-generated `AGENTS.md` that lies about atomic writes. All four are concrete design anti-patterns visible in the source.
- **One process risk worth naming explicitly:** the `omo` CLI alias collides with an unrelated npm package. The maintainer's "do not invoke `bunx omo`" warning in `docs/guide/installation.md:21-29` is the kind of footgun the project should not introduce.

---

## 2. The 11-agent roster

The full set, with role, default model (as of the snapshot), when-to-use, and source path:

| # | Agent | Mode | Default model (per `agent-model-matching.md`) | When to use | Source path |
|---|-------|------|----------------------------------------------|-------------|-------------|
| 1 | **Sisyphus** | primary (tab 0) | `claude-opus-4-7 (max)` | Default for any user request. Plans, classifies intent, delegates in parallel. | [agents-doers.md](./agents-doers.md) · `src/agents/sisyphus.ts` |
| 2 | **Hephaestus** | primary (tab 1) | `openai/gpt-5.5 (medium)`, **no fallback** | Deep architectural reasoning, complex debugging, GPT-5.5 reasoning style. Built exclusively for GPT. | [agents-doers.md](./agents-doers.md) · `src/agents/hephaestus/agent.ts` |
| 3 | **Prometheus** | primary (tab 2) | `claude-opus-4-7 (max)` | Multi-day projects, complex refactors, "documented decision trail." Runs interview → plan-write. | [agents-planners.md](./agents-planners.md) · `src/agents/prometheus/` |
| 4 | **Atlas** | primary (tab 3) | `claude-sonnet-4-6` | Reads a verified plan, delegates per-task, re-verifies. "Boulder Orchestrator" — drives plan to completion. | [agents-executor-verifier.md](./agents-executor-verifier.md) · `src/agents/atlas/agent.ts` |
| 5 | **Sisyphus-Junior** | subagent | category-dependent (default `claude-sonnet-4-6`) | Spawned by `task(category="…")` for categorized unit work. Cannot re-delegate. | [agents-doers.md](./agents-doers.md) · `src/agents/sisyphus-junior/agent.ts` |
| 6 | **Oracle** | subagent | `openai/gpt-5.5 (high)` | Read-only architecture/debug consultant. Hard-rejected in team_mode. | [agents-executor-verifier.md](./agents-executor-verifier.md) · `src/agents/oracle.ts` |
| 7 | **Momus** | subagent | `gpt-5.5 (xhigh)` | Read-only plan critic. OKAY/REJECT verdict on a plan file. | [agents-planners.md](./agents-planners.md) · `src/agents/momus.ts` |
| 8 | **Metis** | subagent | `claude-sonnet-4-6` | Pre-planning gap analyzer. MUST/MUST-NOT directives for Prometheus. | [agents-planners.md](./agents-planners.md) · `src/agents/metis.ts` |
| 9 | **Librarian** | subagent | `opencode-go/minimax-m2.7` | External library / OSS lookup with GitHub permalinks. Read-only. | [agents-support.md](./agents-support.md) · `src/agents/librarian.ts` |
| 10 | **Explore** | subagent | `github-copilot\|xai/grok-code-fast-1` | Internal codebase grep. Read-only + 5 LSP/ast_grep tools. Fire 2–5 in parallel. | [agents-support.md](./agents-support.md) · `src/agents/explore.ts` |
| 11 | **Multimodal-Looker** | subagent | vision-capable (default `openai/gpt-5.4 (medium)`) | Image/PDF/diagram interpretation. Only `read` allowed. | [agents-support.md](./agents-support.md) · `src/agents/multimodal-looker.ts` |

**Cross-cutting facts that matter for adoption:**

- All 11 are registered in `src/agents/builtin-agents.ts:36-46` and consumed via Sisyphus's metadata-driven Delegation Table.
- All subagents use `temperature: 0.1` and deny mutating tools (`write`, `edit`, `apply_patch`, `task`, `call_omo_agent`). The exception is **Multimodal-Looker**, which uses an allowlist of `read` only.
- **Team-Mode eligibility** is a separate axis: eligible = Sisyphus, Atlas, Sisyphus-Junior; conditional = Hephaestus (needs `teammate: "allow"`); hard-rejected = Oracle, Librarian, Explore, Multimodal-Looker, Metis, Momus, Prometheus. The 7 hard-rejects are all "cannot write mailbox state" — i.e. read-only agents structurally can't be team members.
- **Hephaestus is uniquely dangerous** to copy: it has a `requiresProvider: ["openai","github-copilot","venice","opencode"]` hard gate and a `no-hephaestus-non-gpt` hook that redirects non-Claude→Sisyphus with a "Hephaestus is trash without GPT" toast. Adopting Hephaestus as an agent-name would import that gate.
- The dual-prompt pattern (Claude prompt vs GPT prompt per agent) is implemented in `packages/prompts-core/prompts/<agent>/{default,gpt,gemini,kimi,opus-4-7}.md`, auto-selected by `getAtlasPromptSource(model)`. The Claude variants are 500–1,100 lines; the GPT variants are 121–254 lines and principle-driven. This is **load-bearing only for multi-model deployments**.

---

## 3. The orchestration loop

The 4-phase plan lifecycle, end-to-end:

```
                              USER PROMPT
                                  │
                                  ▼
                    keyword-detector (chat.message hook)
                       strips code-fences, detects ulw/
                       search/analyze/team/hyperplan
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ PHASE 1: PLAN GENERATION                                     │
   │   Promethus (primary) — interview, research, summarise       │
   │     ├─► call_omo_agent(explore)   (parallel)                 │
   │     ├─► call_omo_agent(librarian) (parallel)                 │
   │     └─► task(agent="metis")  ← MANDATORY gap analysis        │
   │   OUTPUT: .omo/plans/{name}.md  (Prometheus's own prompt     │
   │            loop, no persistent state)                        │
   └──────────────────────────────────────────────────────────────┘
                                  │  /start-work  (slash command)
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ PHASE 2: PLAN REVIEW                                         │
   │   Momus (subagent, gpt-5.5 xhigh, read-only)                 │
   │     inputs: file path string only                            │
   │     rubric: 100% refs / ≥80% clear refs /                    │
   │              ≥90% acceptance criteria / 0 business-logic      │
   │              assumptions / 0 red flags                        │
   │     verdict: OKAY | REJECT (up to 3 specific issues)          │
   │   LOOP back to Prometheus if REJECT (no max retry)           │
   └──────────────────────────────────────────────────────────────┘
                                  │  OKAY
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ PHASE 3: PLAN EXECUTION                                      │
   │   /start-work  → start-work hook                             │
   │     └─► updateSessionAgent("atlas")  (or fall back to sisy)  │
   │     └─► readBoulderState(".omo/boulder.json")                │
   │     └─► buildStartWorkContextInfo                            │
   │   Atlas (primary, sonnet-4-6) — "Boulder Orchestrator"       │
   │     for each unchecked `- [ ]` in active_plan:               │
   │       ├─► task(category="…")  → Sisyphus-Junior              │
   │       ├─► tick checkbox, re-read plan (enforced)             │
   │       ├─► lsp_diagnostics on changed files                   │
   │       └─► update notepad (learnings/decisions/...)           │
   │     session.idle event → idle-event.ts                      │
   │       └─► if progress < 100% → continuation prompt           │
   │         (5s cooldown, 10-failure cap, 5-min backoff)         │
   │       └─► if progress = 100% → BOULDER_COMPLETE_PROMPT       │
   └──────────────────────────────────────────────────────────────┘
                                  │  all tasks done
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ PHASE 4: PLAN VERIFICATION                                   │
   │   Two layers:                                                │
   │     (a) Per-plan ## Verification section (written by         │
   │         Prometheus, enforced ≥90% concrete by Momus)         │
   │     (b) Live: Atlas calls task(subagent_type="oracle") for   │
   │         architecture/debug questions (read-only advice)      │
   │   On 100% checkboxes: boulder.status="completed"             │
   │   Independent re-verification via lsp_diagnostics + plan     │
   │   re-read — "trusts nothing, verifies everything"            │
   └──────────────────────────────────────────────────────────────┘
```

**State machine summary (where state lives):**

| Phase | State location | Owner |
|-------|----------------|-------|
| Plan generation | `.omo/plans/*.md` | Prometheus prompt loop (in-memory) |
| Plan review | none persistent | Momus returns text verdict |
| Plan execution | `.omo/boulder.json` + `.omo/notepads/{plan}/` | `boulder-state` + `start-work` + `atlas` hooks + `todo-continuation-enforcer` |
| Plan verification | `.omo/notepads/{plan}/verification.md` | Atlas writes; Oracle advises |
| Cross-phase continuation | `.omo/ralph-loop.local.md` | ralph-loop hook (when active) |
| Cross-session continuity | `boulder.json.session_ids[]` + `task_sessions` | boulder's atomic file lock (per [boulder-deep.md](./boulder-deep.md) — actually **not** atomic, see §6) |

**Resume semantics:** on session end mid-plan, the next `session.start` reads `boulder.json`, computes progress as `(checked / total)` checkboxes in `active_plan`, and re-injects a continuation prompt into Atlas pointing at the next unchecked box. The `task_sessions` map reuses the same subagent session id for a given top-level task to preserve accumulated context.

Sources: [orchestration-workflow.md](./orchestration-workflow.md) for the full phase descriptions; [orchestration-keywords.md](./orchestration-keywords.md) for the dispatch layer; [boulder-deep.md](./boulder-deep.md) for state mechanics; [notepads-deep.md](./notepads-deep.md) for the notepad layer.

---

## 4. Adoption candidates — final verdict (updates to light survey)

The light survey covered 4 areas (boulder.json, team_mode, notepads, category routing). The deep survey confirmed all four verdicts and added no new information that flips a verdict. The verdicts stand:

| Area | Light-survey verdict | Deep-survey update | Final verdict |
|------|---------------------|--------------------|--------------:|
| `boulder.json` | Weak fit | **Confirmed.** [boulder-deep.md](./boulder-deep.md) §1 found the auto-generated `AGENTS.md` *lies* about atomic writes — `write-state.ts:40` uses plain `writeFileSync`, no file lock, no temp+rename. The schema-mirroring trick (`BoulderState` has both v1 and v2 fields; lazy migration) is clever but the maintenance cost is real. | **Weak fit** |
| `team_mode` | Weak fit | **Confirmed and deeper.** [team-mode-deep.md](./team-mode-deep.md) §1.1 documents the actual FSM transition table, the per-inbox `.lock` protocol with 5-min stale detection, and the 7-agent hard-reject registry. The runtime state machine is genuinely well-engineered (atomic writes, lock files, 60s stale-deleting TTL), but every bit of it is solving multi-agent/multi-model problems the project doesn't have. | **Weak fit** |
| Notepads | Weak fit | **Confirmed and the 4-vs-5 file asymmetry is now exact.** [notepads-deep.md](./notepads-deep.md) §1.1 found the actual `NOTEPAD_DIRECTIVE` string — it lists 4 files (no `verification.md`), while the orchestration guide documents 5. The asymmetry is intentional (`verification.md` is the orchestrator's output bucket) but a project copying the 5-file system would either drop a file or get a stray worker writing verification entries. The `notepad-write-guard` hook is a 1-line path extension; the actual "always APPEND" rule lives in the prompt. | **Weak fit** |
| Category routing | Weak fit | **Confirmed and the 6-step pipeline is now exact.** [category-routing-deep.md](./category-routing-deep.md) §2 documents the full pipeline (UI → user config → category default → user fallback → hardcoded chain → system default) with provenance strings. The 8 categories × 6 steps × per-category prompt-append × per-category model + variant × family-diverse fallbacks is a lot of machinery. The cross-provider fuzzy match in Step 5 is a nice safety net for the multi-provider case, but the project has one provider. | **Weak fit** |

**No verdict changes.** All four are still weak fits. See [`../SUMMARY.md`](../SUMMARY.md) §3 for the detailed reasoning per area.

---

## 5. Adoption candidates — new ideas (from agents + shell)

The 8 newly-surveyed areas (4 agent docs + 4 orchestration docs) surface these candidate ideas, ranked by fit. None were in the light survey.

### 5.1 Strong fit — worth a small design exercise

#### 5.1.1 Momus 4-criteria plan-review rubric

Momus's OKAY/REJECT verdict is gated by 4 concrete criteria, not a vibe check ([agents-planners.md](./agents-planners.md) §2.4, [orchestration-workflow.md](./orchestration-workflow.md) §2):

1. **Clarity** — does each task specify WHERE to find implementation details?
2. **Verification** — are acceptance criteria concrete and measurable?
3. **Context** — is there enough to proceed without >10% guesswork?
4. **Big Picture** — is the purpose / background / workflow clear?

With these thresholds:

- 100% of file references verified
- ≥80% of tasks have clear reference sources
- ≥90% of tasks have concrete acceptance criteria
- 0 tasks require assumptions about business logic
- 0 critical red flags

**Why it fits:** the project's `@reviewer` and `@tester` agents currently review against an ad-hoc checklist. Codifying these 4 criteria + thresholds as a markdown template that `@reviewer` is *required* to fill in before marking a plan done is a **mechanical verify gate**, not a prompt-instructed one. It would be a new file under `.opencode/` (e.g. `.opencode/templates/plan-review-checklist.md`) and an ADR-anchored rubric. The "80% clarity is good enough" approval bias prevents the gate from becoming a perfectionism blocker.

**Effort:** small. ~50-line template + a `@reviewer` prompt update + 1 ADR.

**Caveat:** the thresholds are calibrated to GPT-5.5-style reasoning in the surveyed project. The project's single model may need different numbers; the rubric itself transfers, the thresholds are an open question.

#### 5.1.2 Role-boundary hook (the `prometheus-md-only` pattern)

`prometheus-md-only` is a `tool.execute.before` hook on `write` and `edit` that *mechanically* blocks a planner agent from writing outside `.omo/*.md` ([agents-planners.md](./agents-planners.md) §1.2). Source: `src/hooks/prometheus-md-only/hook.ts:1-20`. The implementation is ~20 lines; the enforcement is the *opposite* of prompt-driven:

```ts
// Verbatim pattern
if (!isPathInsideOmoMd(canonicalPath)) {
  throw new Error("Prometheus is read-only outside .omo/*.md. Use delegate-task for code changes.")
}
```

**Why it fits:** this is the *exact* anti-prompt-driven enforcement the project wants. The project already has the `plan-as-artifact` principle: a plan can be edited freely, but plan-edit operations should be mechanically distinct from code-edit operations. A `tool.execute.before` hook that routes plan edits to a markdown-only guard and code edits to the existing path is a small, high-leverage addition.

**Effort:** small. ~30 lines + a per-agent permission map.

**Caveat:** the surveyed hook uses a hard-coded path check; the project should make it configurable per agent so `@builder` is not blocked from writing source, only `@planner` is.

### 5.2 Weak fit — worth a paragraph in the design notes

#### 5.2.1 `/handoff` command template

`/handoff` emits a portable session-context summary as a markdown file (one of the 9 builtin commands at [orchestration-keywords.md](./orchestration-keywords.md) §3). The use case is: end a session, hand off the context to a new session or a new agent.

**Why weak fit:** the project has `.opencode/work-log.md` and `.opencode/todo.md` which already serve this role. A dedicated `/handoff` template that exports a single self-contained markdown file is a marginal addition. Worth considering only if the project's resume experience is poor.

**Effort:** tiny. One template file.

#### 5.2.2 Non-main-session guard for keyword injection

The `keyword-detector` hook explicitly skips `task()` calls, subagent sessions, and background-task sessions ([orchestration-keywords.md](./orchestration-keywords.md) §1, step 6: "Subagent / background-task sessions ⇒ skip entirely"). This is the guard that prevents a `ulw` keyword typed in Sisyphus from re-injecting the ultrawork prompt in every Sisyphus-Junior turn.

**Why weak fit:** the project doesn't have inline keyword detection yet. The principle ("only mutate the main session's prompt") is generic enough that it belongs in a design note, not in a new feature. If the project ever adds `ulw`-style keywords, this guard is load-bearing.

**Effort:** design-doc only (paragraph). Zero code.

#### 5.2.3 4-phase plan lifecycle as a vocabulary

The Prometheus → Momus → Atlas → Oracle loop is a clean separation of concerns: planner writes, critic reviews, executor runs, advisor verifies. Each phase has a single owner and a single artifact. The 4-phase structure is *not* new to the project (the conductor does roughly this), but naming the phases explicitly and giving each a markdown template (`.opencode/templates/plan.md`, `.opencode/templates/review.md`, `.opencode/templates/execute.md`, `.opencode/templates/verify.md`) would make the workflow more legible.

**Why weak fit:** it's a vocabulary refactor, not a feature. The conductor already produces the right artifacts; this is a documentation effort.

**Effort:** medium. 4 template files + an ADR + an `AGENTS.md` section.

### 5.3 Already evaluated

- **`@plan` mention pattern** — already adopted (the project has `@builder`, `@architect`, etc.).
- **`/start-work` slash command** — already evaluated; the project's `conductor` startup check on `.opencode/todo.md` is the equivalent.
- **The dual-prompt pattern** (Claude + GPT variants per agent) — does not apply to a single-model project.
- **Category-routed `task()` dispatch** — already evaluated as weak fit; the project uses `@mention` instead.
- **The `task_sessions` map in boulder.json v2** — already evaluated as part of the boulder verdict; the project does not need per-task session reuse.
- **Per-agent `temperature: 0.1` convention** — already adopted (`temperature: 0.1` in `opencode.json`).
- **Hard-reject registry for team_mode** — does not apply; the project does not have a multi-agent runtime.
- **The 6-step model resolution pipeline** — does not apply to a single-model project.

### 5.4 Rejected — actively bad ideas

- **Telemetric opt-out env vars** (`OMO_DISABLE_POSTHOG=1`): the project has no telemetry. Don't introduce the precedent.
- **`@team` keyword that prompts the user to enable a feature flag**: the team's `team_mode` keyword body literally tells the user "set `team_mode.enabled: true` if tools are missing" ([orchestration-keywords.md](./orchestration-keywords.md) §5.3). This is a prompt-level workaround for a config-level opt-in — the wrong shape.
- **`requiresProvider` hard gate on agents**: Hephaestus cannot activate without GPT access ([category-routing-deep.md](./category-routing-deep.md) §8). A single-model project has no use for this; the equivalent is "the project is broken if the model is missing," not "the agent is hidden."
- **`default_mode.ultrawork` + `default_mode.ralph_loop` "fully autonomous" recipe** ([orchestration-keywords.md](./orchestration-keywords.md) §5.2): opt-in full autonomy. The project's conductor should not have a "fire and forget" mode that overrides per-task verification.

---

## 6. Risk callouts (do NOT replicate)

These are concrete design decisions surfaced by the deep survey that the project should explicitly avoid.

1. **Prompt-driven enforcement is everywhere.** The "always APPEND" rule in notepads ([notepads-deep.md](./notepads-deep.md) §1.1), the "continue boulder work" injection in the continuation loop ([boulder-deep.md](./boulder-deep.md) §8), and the wisdom-pass-forward loop in Atlas all rely on a model following a prompt instruction. The project rejects this via the "mechanical verify gates" priority — keep doing that. Every "the model will remember to X" design in the surveyed source is a candidate for a different shape in this project.

2. **Documentation-only safety detection.** The category-routing "safe vs dangerous overrides" is a doc table, not a runtime check ([category-routing-deep.md](./category-routing-deep.md) §6.3). The maintainer's stance is "the docs are the warning; the user is responsible." The project has a different stance: if a configuration is wrong, the system should detect it. Any feature copied from `oh-my-openagent` must be re-enforced, not just re-documented.

3. **Mid-rename paths.** `.sisyphus/` → `.omo/` is in flight as of the snapshot. `boulder.json`'s constants say `.omo` ([boulder-deep.md](./boulder-deep.md) §3), the notepad `constants.ts` says `.omo`, but `worktree-sync.ts` (commit `19ab3b5`) still copies from `.sisyphus/`, and the docs still say `.sisyphus/`. Both paths are in `.gitignore`. **Cosmetic churn that the project should avoid by picking a path once and not renaming.**

4. **The auto-generated `AGENTS.md` lies about atomic writes.** `src/features/boulder-state/AGENTS.md` (generated 2026-05-15) claims: *"Write operations use atomic file replacement with a file lock to prevent corruption from concurrent hook invocations."* The actual `writeBoulderState` in `write-state.ts:40` uses plain `writeFileSync` ([boulder-deep.md](./boulder-deep.md) §1, §5). This is a concrete instance of the "auto-generated docs are aspirational" failure mode — if the project ever auto-generates documentation, it must be regenerated on every code change or be deleted.

5. **`SYSTEM_DIRECTIVE_PREFIX` was a single string being abused by multiple systems.** PR #4036 had to rename the marker to an XML tag in external prompts because the old "SYSTEM DIRECTIVE" string was being injected by the notepad hook *and* the delegate-task "SINGLE TASK ONLY" wrapper, with `SYSTEM_DIRECTIVE_PREFIX`-based double-injection guards catching each other. **Lesson:** identifiers in prompt-injection guards should be namespaced per-feature, not global.

6. **The `omo` CLI alias collides with an unrelated npm package.** `docs/guide/installation.md:21-29` explicitly warns: *"do not invoke `bunx omo` — that resolves to an unrelated npm package."* Any project publishing a CLI must check npm for alias collisions first.

7. **The `.omo/**` exemption in the write-guard is bypassable via `bash cat >>`.** The hook's read-gate is a no-op for `.omo/**` paths ([notepads-deep.md](./notepads-deep.md) §1.4). The 4-file "always APPEND" directive only works because workers use `bash` redirection, not the `write` tool. **Lesson:** a hook that exempts a path class from its own enforcement cannot rely on the same path class to be the only thing accessed there.

8. **Schema states that are never written.** `BoulderWorkStatus` permits `"paused"` and `"abandoned"` but `idle-event.ts` only writes `"active"` and `"completed"` ([boulder-deep.md](./boulder-deep.md) §12). The types allow states that have no code path that sets them. **Lesson:** don't add enum values "for future use" — they rot.

9. **`prometheus` is hard-rejected from team_mode because it cannot write to the team mailbox.** The structural reason: the hook restricts Prometheus to `.omo/*.md` writes. The consequence: Prometheus is excluded from the team-mode "do work" pool. **Lesson:** when a role-boundary hook is too strict, it cascades into other systems that need to be more lenient. The project's mechanical permission hooks should be designed so the *default* agent is not in a "blocked from everything but plans" state.

10. **The "parallel by default" promise is partly false for non-Claude models.** Issue #2897 ([notepads-deep.md](./notepads-deep.md) §5) — *"Atlas has no clue how to spawn parallel agents most of the time"* — is closed as **not planned**. The maintainer's fix is per-model prompt variants and a first-prompt watchdog timeout, not a guarantee of parallelism. **Lesson:** if a feature description says "parallel by default," verify it works on your model, not on the maintainer's.

11. **Approval-bias Momus threshold of 80% is calibrated to one model's reasoning style.** The doc says "80% clarity is good enough" ([agents-planners.md](./agents-planners.md) §3.5) but the threshold is a single number that may not generalise. The rubric is the transferable part, not the number.

12. **The `requiresProvider` gate silently drops agents.** If no provider in the `requiresProvider` list is connected, the agent is *not invoked* ([category-routing-deep.md](./category-routing-deep.md) §6.5). No error, no warning — the user simply doesn't get the agent. The maintainer's stance is "better to skip than run broken," but the failure mode is invisible. **Lesson:** if the project ever gates an agent, emit a warning, not a silent skip.

13. **The `disabled_hooks` allowlist is a flat kill switch, not a per-axis enable.** Users can disable built-in hooks but cannot enable custom user-written hooks in the same way ([orchestration-skills-hooks.md](./orchestration-skills-hooks.md) §2). The only user hook surface is the Claude Code compat shim. **Lesson:** if a project allows user extensions, design the extension surface alongside the built-in toggles, not as a follow-up.

14. **Telemetric "best effort" patterns are not optional.** The `omo_daily_active` event fires at most once per UTC day, opt-out env vars disable the PostHog client, and "the PostHog client is a no-op and no telemetry network call is made" ([orchestration-cli-config.md](./orchestration-cli-config.md) §4.3). The project has no telemetry — don't introduce it without a clear opt-out story.

15. **The maintenance burden of a 32-file Zod schema and 100+ KB JSON schema asset** ([orchestration-cli-config.md](./orchestration-cli-config.md) §2.3) is a real cost. The project should keep its `opencode.json` simple — adding 100+ KB of generated JSON Schema for editor autocomplete is a feature, not a free feature.

---

## 7. Open questions

After the deep survey, the following are still unresolved or under-characterized:

1. **Empirical error rate of the notepad "always APPEND" rule.** The deep survey notes that a "weak/fast model for the executor can skip the append entirely" ([notepads-deep.md](./notepads-deep.md) §1.4) but no metrics are available. The project would want to know how often this fails in practice before adopting any append-only pattern.

2. **How often does the `works` map's multi-plan support get used?** The boulder v2 schema supports multiple concurrent plans ([boulder-deep.md](./boulder-deep.md) §4) but the project has only ever had one active plan at a time. The generalisation may be over-engineering for the typical user. No data in the surveyed sources.

3. **Does the `task_sessions` resume pattern actually preserve useful context?** The map is updated on every iteration ([boulder-deep.md](./boulder-deep.md) §9) but no surveyed code reads it to summarise. The claim is "context preservation"; the evidence is "session ID reuse." Untested.

4. **Where is `max_member_turns: 500` enforced?** The field is in `RuntimeBoundsSchema` and persisted into `RuntimeState.bounds` ([team-mode-deep.md](./team-mode-deep.md) §6.3) but the deep survey notes no surveyed call site reads it for enforcement. Likely a parameter to `bgMgr.launch` (not surveyed) or a future enforcement. Not relevant for adoption but a reminder that the surveyed source is not the whole code.

5. **Would the Momus 4-criteria thresholds (100/80/90/0) translate to a single-model project?** The thresholds are calibrated to GPT-5.5 / Claude-Opus-4.7 reasoning. A project using a different model may need different numbers. The rubric transfers; the numbers are an open question.

6. **What's the cost of the dual-prompt pattern (one markdown per model family)?** Maintenance is non-trivial — 5 markdown variants per primary agent, with model-specific heuristics in the loader. The project would only need this if it goes multi-model.

7. **The `unspecified-high → Opus max` safety net** ([category-routing-deep.md](./category-routing-deep.md) §6.5) is a deliberately expensive default for unrecognized categories. The project has no category system, but if it adopts one, the same deliberate-degradation pattern is worth considering.

8. **The `team_create` caller-eligibility check** ([team-mode-deep.md](./team-mode-deep.md) §9.1) is unique — it checks the *caller's* agent identity, not the spec's `lead` field, to prevent a read-only agent from spawning a team. This is a generalisable pattern: "even if the spec is valid, check that the caller is allowed to do this." The project has no equivalent.

9. **The "non-main session" guard for keyword injection** ([orchestration-keywords.md](./orchestration-keywords.md) §1, step 6) is critical for avoiding prompt-injection loops, but the implementation is scattered across the hook (skip if subagent, skip if background, etc.). A cleaner design would be: "only inject on `session.id === MAIN_SESSION`." Worth thinking about if the project adds any inline detection.

10. **What happens to notepad state if `worktree-sync.ts`'s `cpSync` is interrupted mid-call?** The function uses `{ recursive: true, force: true }` ([notepads-deep.md](./notepads-deep.md) §2.1) with no atomic-rename. A crash mid-copy leaves partial state. Not surveyed at the error-recovery level.

11. **Is the "init-deep slash command migrated to a skill" pattern a sign that the maintainer prefers skills to builtin commands?** The migration in `init-deep-migration.test.ts:5-12` ([boulder-deep.md](./boulder-deep.md) §1) asserts the builtin slot is empty. If the maintainer is moving toward skills, future OmO features may all be skills, not builtin commands. The project has a `~/.claude/skills/` directory; the dual-support pattern in [orchestration-skills-hooks.md](./orchestration-skills-hooks.md) §1 (`.opencode/skills/*/SKILL.md`, `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/`) is what to follow.

12. **The `disabled_hooks` schema is in `src/config/schema/hooks.ts` (`HookNameSchema`)** — 50+ hook names. The project would inherit the same schema if it adopts the same extensibility model. Is the per-hook toggle the right granularity? An alternative is hook *categories* (a single flag for "disable all tool-guard hooks"). No surveyed source addresses this.

13. **The `getMainSessionID()` and `subagentSessions` mechanism in `keyword-detector/hook.ts:7-12`** ([orchestration-keywords.md](./orchestration-keywords.md) §1, step 9) is a session-namespace primitive that the project does not need (single-conductor) but is the kind of thing to be aware of when reading the surveyed source.

14. **The `dist-tags` upgrade mechanism with per-channel throttles** ([orchestration-cli-config.md](./orchestration-cli-config.md) §5.1, step 4) is over-engineered for a single-package project. Don't replicate.

15. **The `bunx oh-my-openagent doctor` 6-category health check** ([orchestration-cli-config.md](./orchestration-cli-config.md) §1.1) is a useful pattern for a project with optional integrations. If the project ever adds optional providers or MCPs, a `doctor`-style command is a clean way to surface state. The project currently has no such command.

---

## 8. Final recommendation

**Do not adopt any of the four light-survey areas verbatim.** The deep survey confirms the weak-fit verdicts with no new evidence that flips a recommendation. The project's priorities (single-model, auditability, plan-as-artifact, ADRs, mechanical verify gates) are the structural opposite of the surveyed project's priorities (multi-model, prompt-instructed, JSON state, multi-agent runtime).

**Adopt two new ideas as small, markdown-native design exercises:**

1. **Momus 4-criteria plan-review rubric** — codify the 4 criteria + thresholds as `.opencode/templates/plan-review-checklist.md` and require `@reviewer` to fill it in before marking a plan done. Effort: ~50 lines + 1 ADR.
2. **Role-boundary hook** — implement a `tool.execute.before` guard that mechanically enforces which paths an agent can write to (the `prometheus-md-only` pattern, generalised). Effort: ~30 lines + a per-agent permission map.

**Adopt two more as design notes, not code:**

3. **4-phase plan lifecycle as a vocabulary** — name the phases (plan / review / execute / verify) and give each a template. The conductor already does this work; this is a documentation effort. Effort: 4 templates + 1 ADR.
4. **Non-main-session guard for any future keyword detection** — if the project ever adds `ulw`-style keywords, only fire on the main session. Effort: a paragraph in the design doc.

**Do not replicate the 15 risk-callout design decisions** in §6, especially the prompt-driven enforcement pattern, the documentation-only safety detection, the mid-rename paths, the auto-generated `AGENTS.md` that lies about atomic writes, the `omo` CLI alias collision, and the schema-states-that-are-never-written.

The single most productive follow-up is the plan-review rubric (§5.1.1). It is a small, mechanical improvement that directly serves the project's auditability and verification priorities.

---

## Source documents (all 12)

### Light-survey (carried forward)
- [`../SUMMARY.md`](../SUMMARY.md) — synthesis of the 4 areas (boulder, team-mode, notepads, category-routing)
- [`../boulder.md`](../boulder.md) — per-worktree orchestrator state file
- [`../team-mode.md`](../team-mode.md) — multi-agent mailbox orchestration
- [`../notepads.md`](../notepads.md) — plan-scoped append-only memory
- [`../category-routing.md`](../category-routing.md) — category-to-model fallback chains

### Deep-survey (new)
- [boulder-deep.md](./boulder-deep.md) — code-anchored walkthrough of boulder state; closes the atomic-write, schema-version, and AGENTS.md-out-of-sync gaps
- [team-mode-deep.md](./team-mode-deep.md) — full FSM, reservation protocol, eligibility registry, tmux wiring
- [notepads-deep.md](./notepads-deep.md) — actual `NOTEPAD_DIRECTIVE` text, `sisyphus-junior-notepad` hook source, `notepad-write-guard` mechanism
- [category-routing-deep.md](./category-routing-deep.md) — full 6-step pipeline, 8 categories, `transformModelForProvider`, runtime-fallback reactive system

### Agent docs (new)
- [agents-doers.md](./agents-doers.md) — Sisyphus, Sisyphus-Junior, Hephaestus
- [agents-planners.md](./agents-planners.md) — Prometheus, Momus, Metis
- [agents-executor-verifier.md](./agents-executor-verifier.md) — Atlas, Oracle
- [agents-support.md](./agents-support.md) — Librarian, Explore, Multimodal-Looker

### Orchestration docs (new)
- [orchestration-workflow.md](./orchestration-workflow.md) — full 4-phase plan lifecycle
- [orchestration-keywords.md](./orchestration-keywords.md) — `ulw`/`hyperplan` keyword dispatch, slash command registry
- [orchestration-skills-hooks.md](./orchestration-skills-hooks.md) — skills, hooks, plugin architecture, MCPs
- [orchestration-cli-config.md](./orchestration-cli-config.md) — CLI, configuration, telemetry, update mechanism

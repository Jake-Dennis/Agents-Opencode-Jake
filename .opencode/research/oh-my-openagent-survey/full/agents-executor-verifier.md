# Executor / Verifier Agents Survey: Atlas, Oracle

Repo: [code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) (branch `dev`, plugin package `oh-my-openagent`, alias `oh-my-opencode` / "omo" / "Sisyphus"). All paths and line numbers below are from the `dev` branch at the time of survey.

---

## 1. Atlas — Master Executor / Todo Orchestrator

### 1.1 Purpose

Atlas is the "Master Executor" of the OmO harness. It is a `primary`-mode agent that reads a verified plan (`.omo/plans/{name}.md` produced by Prometheus/Metis/Momus) and walks every top-level checkbox to completion by delegating work to category-routed subagents and re-verifying each one. It is described externally as: "Reads verified plans, delegates to specialized agents via category+skills system. Tracks learnings across tasks. Verifies independently — never trusts subagent claims." (omo.dev hero copy; "Atlas" tile, omo.dev root).

In the orchestration tree it sits under Sisyphus as the "executor" half of the planner/executor split:

```
Sisyphus (CTO) ──► Prometheus (plan) ──► /start-work ──► Atlas (execute) ──► Oracle / Sisyphus-Junior / category workers
```

### 1.2 Prompt shape

Atlas's prompt is **not** a single inlined string in the agent file. It is a markdown variant loaded via the `@oh-my-opencode/prompts-core` package, with **runtime-injected** dynamic sections. The agent factory is tiny (158 lines) and only chooses the right markdown file plus injects the live sections.

**Agent factory:** `src/agents/atlas/agent.ts`

- `createAtlasAgent(ctx)` — returns an `AgentConfig` (description, mode `primary`, optional model override, temperature `0.1`, color `#10B981`, and the composed prompt). `src/agents/atlas/agent.ts:127-140`
- `getAtlasPromptSource(model)` — resolves which markdown variant to load via `resolveVariant({ agentName: "atlas", modelID: model, variants: atlasPromptVariants })`. `src/agents/atlas/agent.ts:43-52`
- `buildDynamicOrchestratorPrompt(ctx)` — calls `loadPromptSync(...)` with five `SyncRuntimeInjection`s and prepends a `buildAgentIdentitySection("Atlas", ...)` line. `src/agents/atlas/agent.ts:79-124`

**Variant routing order** (from the in-file comment block at `src/agents/atlas/agent.ts:1-19` and the AGENTS.md):

| Priority | Match | Markdown file |
|---|---|---|
| 1 | Claude Opus 4.7 | `packages/prompts-core/prompts/atlas/opus-4-7.md` (literal-following + explicit fan-out push) |
| 2 | GPT family | `packages/prompts-core/prompts/atlas/gpt.md` (calibrated for GPT-5.5) |
| 3 | Gemini family | `packages/prompts-core/prompts/atlas/gemini.md` |
| 4 | Kimi K2.x family | `packages/prompts-core/prompts/atlas/kimi.md` (Claude base + K2.6 thinking-mode calibration) |
| 5 | Default (Claude 4.6 family: opus-4-6, sonnet-4-6, haiku-4-5) | `packages/prompts-core/prompts/atlas/default.md` |

**Runtime placeholders** (replaced at load time by `loadPromptSync({...inject: runtimeInjections})`, `src/agents/atlas/agent.ts:102-110`):

- `{CATEGORY_SECTION}` → `buildCategorySection(userCategories)`
- `{AGENT_SECTION}` → `buildAgentSelectionSection(agents)`
- `{DECISION_MATRIX}` → `buildDecisionMatrix(agents, userCategories)`
- `{SKILLS_SECTION}` → `buildSkillsSection(skills)`
- `{{CATEGORY_SKILLS_DELEGATION_GUIDE}}` → `buildCategorySkillsDelegationGuide(...)`

These resolvers live in `src/agents/atlas/prompt-section-builder.ts` and depend on live category, agent, and skill state.

**Length.** The default markdown is 500 lines / 18 KB / ~372 lines of content (`packages/prompts-core/prompts/atlas/default.md`). The in-agent factory is 158 lines (5.47 KB). Top-level structure of `default.md` (visible at the source listing):

1. Persona preamble ("Atlas - the Master Orchestrator from OhMyOpenCode ... Greek mythology, Atlas holds up the celestial heavens")
2. `<Anti_Duplication>` — do not re-explore what explore/librarian already covered
3. `<delegation_system>` — `task(category=…)` vs `task(subagent_type=…)`, 6-section prompt structure (TASK / EXPECTED OUTCOME / REQUIRED TOOLS / MUST DO / MUST NOT DO / CONTEXT), with the rule "If your prompt is under 30 lines, it's TOO SHORT"
4. `<auto_continue>` — never ask "should I continue?" between plan steps
5. `<parallel_by_default>` — fan-out is the default, sequential is the exception, with a hard "**NEVER `background_cancel(all=true)`**" rule
6. Step 0–4 procedure (register tracking → analyze plan → init notepad → execute tasks → Final Verification Wave)
7. `<notepad_protocol>`, `<verification_philosophy>`, `<critical_overrides>`, `<post_delegation_rule>`, `<boulder_completion_response>`

This is the Claude/dual-prompt agent family — it has model-specific variants rather than one prompt that gets re-tuned by an LLM call. (See `agent-model-matching.md:40-55` for the dual-prompt design rationale.)

### 1.3 Triggers

Atlas is invoked in three concrete ways:

1. **Direct tab switch (primary agent).** Atlas is one of the four core "tab-switchable" agents (alongside Sisyphus, Hephaestus, Prometheus). Fixed runtime priority order per `agent-model-matching.md`: `Sisyphus (0) → Hephaestus (1) → Prometheus (2) → Atlas (3)`. The user selects Atlas from the agent selector and chats normally, normally with a plan path in their message.
2. **Hand-off from Prometheus via `/start-work`.** A `command.execute.before` + `chat.message` hook named `start-work` detects the marker `You are starting a Sisyphus work session.` in the outgoing prompt, calls `parseUserRequest(promptText)`, and re-binds the session's agent to `atlas` (if registered) or `sisyphus`. `src/hooks/start-work/start-work-hook.ts:55-132`
3. **Auto-continuation when the session goes idle — the "Atlas idle-event".** This is the most distinctive trigger. It is a hook, not a user command, and it is what makes Atlas a "Boulder Orchestrator" instead of a normal chat agent.

**Atlas idle-event in detail** (`src/hooks/atlas/idle-event.ts`, `atlas-hook.ts`, `boulder-continuation-injector.ts`, `system-reminder-templates.ts`):

- `handleAtlasSessionIdle({ctx, getState, sessionID})` (≈`idle-event.ts:228-515`) runs on every `session.idle`.
- It calls `resolveActiveBoulderSession(...)` to see whether the current session is part of an active "boulder" (a registered plan run) — boulder state lives in `.omo/boulder.json` and is updated by the start-work hook and the task delegation system.
- If there is **no active boulder** for the session → return (log "Skipped: session not registered in active boulder").
- If progress is **not complete** → `injectContinuation(...)` calls `injectBoulderContinuation(...)` (`boulder-continuation-injector.ts`), which:
  - Cooldown-gates re-injection (`CONTINUATION_COOLDOWN_MS = 5000`, `idle-event.ts:43`).
  - Confirms the active descendant agent matches the boulder agent (`canContinueTrackedBoulderSession`), otherwise skips.
  - Confirms no background tasks are running for this session (`hasRunningBackgroundTasks`).
  - Composes a continuation prompt referencing the next unchecked top-level task and dispatches it via `dispatchInternalPrompt({ mode: "async", client, sessionID, source: HOOK_NAME, queueBehavior: "defer" })`. The continuation is injected as a synthetic text part (`createInternalAgentContinuationTextPart`).
- If progress **is complete** → the hook reads `boulder.json` to build a per-task timing breakdown, builds a `BOULDER_COMPLETE_PROMPT` via `system-reminder-templates.ts` (the `BOULDER_COMPLETE` phrase is in the injected message), and injects that single nudge into the Atlas session so it can print the final summary and mark `pass-final-wave` complete. `idle-event.ts:292-360`
- Failure handling: per-session `promptFailureCount` with a cap `MAX_CONSECUTIVE_PROMPT_FAILURES = 10` and a 5-minute backoff `FAILURE_BACKOFF_MS`. `idle-event.ts:45-46`, `:55-117`

**Tool-level denial as a trigger shape.** Atlas has the `task` and `call_omo_agent` tools **denied** by `AGENTS.md` ("Denied tools: `task`, `call_omo_agent` (Atlas delegates; it does not run subagents directly)"). Note: this contradicts the prompt's heavy use of `task(...)`; the resolution per the code is that Atlas *itself* calls `task()` against a delegated subagent — the "deny" line in the AGENTS.md is shorthand for "Atlas only delegates, it does not implement." (See `critical_overrides` in the prompt: "NEVER write/edit code yourself — always delegate" and "ALL code writing/editing" → DELEGATE.)

### 1.4 Model

Default: `claude-sonnet-4-6` (per `src/agents/atlas/AGENTS.md`, "Key Behaviors" section).

Documented fallback chain (from `agent-model-matching.md:347-362`, "Atlas" row):

```
claude-sonnet-4-6  →  kimi-k2.6  →  gpt-5.5 (medium)  →  minimax-m3  →  minimax-m2.7
```

**Category per the agent-model-matching doc:** "Dual-Prompt Agents → Claude preferred, GPT supported." Auto-detects model family at runtime via `resolveVariant` and switches to the matching markdown (see §1.2).

The doc explicitly lists Atlas as safe to override within the Claude family: "Atlas: Claude Sonnet 4.6 → Kimi K2.6 → GPT-5.5 (auto-switches to the GPT prompt)". Cross-family overrides are tracked in the safe-vs-dangerous list at `agent-model-matching.md:464-475`.

### 1.5 When to use

From `src/agents/atlas/agent.ts:147-176` (`atlasPromptMetadata.useWhen`):

- "User provides a todo list path (.omo/plans/{name}.md)"
- "Multiple tasks need to be completed in sequence or parallel"
- "Work requires coordination across multiple specialized agents"

From the docs (omo.dev/ohmyopenagent.com hero + `agent-model-matching.md:159-164`):

- "Plan first, then execute (previously Plan) → Select Prometheus. It interviews you and produces a plan. Type `/start-work` to hand off to Atlas."
- "Atlas is for when the planner doesn't code, the executor follows verified plans, intelligence lives in the system, not individual agents."

From `docs.olares.com/use-cases/opencode-omo.html` ("Orchestrate multi-agent workflows"):

> "Atlas | Plan executor. Takes over a Prometheus plan and executes it. | Agent selector, or `/start-work` after planning."

From the AGENTS.md narrative (omo.dev): "Intent-based task routing, Wisdom accumulation across tasks, Boulder session continuity, Independent result verification."

### 1.6 When NOT to use

From `atlasPromptMetadata.avoidWhen` (`src/agents/atlas/agent.ts:165-170`):

- "Single simple task that doesn't require orchestration"
- "Tasks that can be handled directly by one agent"
- "When user wants to execute tasks manually"

From the larger "When you should not use ultrawork" framing (`https://www.glukhov.org/ai-devtools/opencode/oh-my-opencode/`): small edits and straightforward questions should not trigger the multi-agent flow.

**Team mode.** Atlas is `eligible` as a team-mode lead or member (`team-mode.md:78-83`: "Eligible: `sisyphus`, `atlas`, `sisyphus-junior`"). When used as a lead via `kind: "subagent_type", subagent_type: "atlas"` it spawns members and coordinates them. Hard-reject agents in team mode are `oracle, librarian, explore, multimodal-looker, metis, momus, prometheus` — they cannot write mailbox state and must be used through `delegate-task` instead.

### 1.7 Source location

- `src/agents/atlas/agent.ts` (158 lines) — `createAtlasAgent`, `getAtlasPromptSource`, `OrchestratorContext`, `atlasPromptMetadata`
- `src/agents/atlas/index.ts` (2 lines) — barrel
- `src/agents/atlas/prompt-section-builder.ts` — `buildCategorySection`, `buildAgentSelectionSection`, `buildDecisionMatrix`, `buildSkillsSection`, `getCategoryDescription`
- `src/agents/atlas/AGENTS.md` (64 lines) — developer reference, lists variant files and "Key Behaviors"
- `src/agents/atlas/atlas-prompt.test.ts`, `prompt-byte-preservation.test.ts`, `prompt-checkbox-enforcement.test.ts`, `prompt-routing.test.ts`
- `packages/prompts-core/prompts/atlas/{default,opus-4-7,gpt,gemini,kimi}.md` — the actual prompt bodies
- Registration: `src/agents/builtin-agents/atlas-agent.ts` (`maybeCreateAtlasConfig`)
- Idle-event / continuation: `src/hooks/atlas/atlas-hook.ts`, `idle-event.ts`, `boulder-continuation-injector.ts`, `final-wave-approval-gate.ts`, `system-reminder-templates.ts`, `tool-progress.ts`, `tool-execute-before.ts`, `tool-execute-after.ts`
- Hand-off: `src/hooks/start-work/start-work-hook.ts` (the `/start-work` slash command)

---

## 2. Oracle — Read-Only Strategic Advisor / Verifier

### 2.1 Purpose

Oracle is a `subagent`-mode specialist. It is the "verifier" half of the harness: a read-only GPT-5.5-class consultant that primary agents (Sisyphus, Hephaestus, Atlas itself) call when a question needs more reasoning depth than their own context budget affords. The metadata block at the top of `src/agents/oracle.ts:14-37` declares:

```ts
category: "advisor",
cost: "EXPENSIVE",
triggers: [
  { domain: "Architecture decisions",       trigger: "Multi-system tradeoffs, unfamiliar patterns" },
  { domain: "Self-review",                  trigger: "After completing significant implementation" },
  { domain: "Hard debugging",               trigger: "After 2+ failed fix attempts" },
],
```

Its `description` (set in `createOracleAgent` at `src/agents/oracle.ts:127-133`):

> "Read-only consultation agent. High-IQ reasoning specialist for debugging hard problems and high-difficulty architecture design. (Oracle - OhMyOpenCode)"

External copy (`docs.olares.com`): "Read-only architecture consultant. Advises on architecture decisions and complex debugging without modifying files. | Auto-dispatched in `ultrawork`."

### 2.2 Prompt shape

Oracle has **three** inlined prompt constants, picked at agent-construction time based on the resolved model:

- `ORACLE_DEFAULT_PROMPT` — used for Claude and other non-GPT models (`src/agents/oracle.ts:43-167`).
- `ORACLE_GPT_PROMPT` — tuned for GPT-5.4 system-prompt design principles (`src/agents/oracle.ts:170-292`).
- `ORACLE_GPT_5_5_PROMPT` — the explicit GPT-5.5 prompt, with its own structure (`src/agents/oracle.ts:295-422`).

The factory `createOracleAgent(model)` (`src/agents/oracle.ts:424-451`) chooses the right prompt + tuning:

```ts
if (isGpt5_5Model(model)) { return { prompt: ORACLE_GPT_5_5_PROMPT, reasoningEffort: "medium", textVerbosity: "high", ... } }
if (isGptModel(model))     { return { prompt: ORACLE_GPT_PROMPT,      reasoningEffort: "medium", textVerbosity: "high", ... } }
return { ...base, ...buildClaudeThinkingConfig(model) }   // Claude default
```

**Default prompt structure** (`ORACLE_DEFAULT_PROMPT`, ~125 lines, XML-tagged):

- `<context>` — on-demand specialist invoked by a primary coding agent
- `<expertise>` — five bullets
- `<decision_framework>` — "pragmatic minimalism": simplicity bias, leverage what exists, prioritize DX, one clear path, match depth to complexity, signal effort (Quick < 1h / Short 1-4h / Medium 1-2d / Large 3d+), know when to stop
- `<output_verbosity_spec>` — hard caps on length per section
- `<response_structure>` — Essential / Expanded / Edge cases three-tier format
- `<uncertainty_and_ambiguity>` — ask 1-2 clarifying questions, or state interpretation explicitly
- `<long_context_handling>` — anchor claims to file paths, function names, line numbers
- `<scope_discipline>` — recommend only what was asked; max 2 "Optional future considerations"
- `<tool_usage_rules>`, `<high_risk_self_check>`, `<guiding_principles>`, `<delivery>` — response goes directly to the user with no intermediate processing

**GPT-5.5 prompt** (`ORACLE_GPT_5_5_PROMPT`, ~127 lines) is principle-driven (per `agent-model-matching.md:55-60` "GPT responds to principle-driven prompts — concise principles, XML structure, explicit decision criteria") and adds: "You are read-only. You advise; others execute. You cannot write, edit, patch, or delegate further work." and an explicit "Hard cap total response length at around 400 lines."

**Tool restrictions.** `createAgentToolRestrictions(["write", "edit", "apply_patch", "task"])` (`src/agents/oracle.ts:425-429`) is applied to the base config — Oracle cannot mutate files, cannot patch, and cannot spawn further subagents. This is what makes it genuinely "read-only consultation."

### 2.3 Triggers

There is no dedicated "Oracle trigger" hook. Oracle is invoked by the orchestrator via the `task()` delegation tool with `subagent_type="oracle"`. The two documented invocation paths:

1. **From Sisyphus / Hephaestus via `task()` with `subagent_type="oracle"`.** The Sisyphus prompt's delegation rules say "Complex architecture → consult Oracle" (deepwiki Delegation Strategy: "Frontend work → delegate. Deep research → parallel background agents. Complex architecture → consult Oracle"). The `AgentPromptMetadata.triggers` array in `oracle.ts:17-25` is what the dynamic prompt builder surfaces into the orchestrator's decision matrix — this is how Sisyphus knows to call Oracle.
2. **From a user prompt directly, via `ultrawork` (or `ulw`)**. The keyword-detector (`src/hooks/keyword-detector/constants.ts:48-55`) registers `ultrawork` with regex `/\b(ultrawork|ulw)\b/i` and prepends a banner that calls for Sisyphus's full delegation tree to fire; Oracle is one of the workers that get dispatched automatically as part of that banner. (`KEYWORD_DETECTORS` in `constants.ts:48-67`.)
3. **From the user prompt literally asking for Oracle.** Users can prepend "ask the oracle" or `@oracle` to a message; the user-facing copy in the ohmyopenagent.com/Glukhov quickstart explicitly shows this convention: `"ultrawork ask @oracle to design the endpoint contract and dependencies first, then implement with minimal changes and add tests"`. The string is interpreted by Sisyphus as a directive to call `task(subagent_type="oracle", ...)`. There is no dedicated `oracle`-keyword regex in `keyword-detector/constants.ts` — the `@oracle` mention is convention, not a hook, and Oracle is reached through Sisyphus's task tool.
4. **The Final Verification Wave** is a separate verification layer in the Atlas plan lifecycle (see `src/hooks/atlas/final-wave-approval-gate.ts` and the Atlas default.md `<boulder_completion_response>` section) — that uses Momus, not Oracle. Oracle is not a reviewer of the plan as a whole; it is invoked ad-hoc for architecture/debug questions.

Oracle has **no** idle-event hook of its own. It is a one-shot consultation, and follow-ups reuse the same session via `task_id="ses_..."` (called out explicitly in `ORACLE_GPT_5_5_PROMPT`'s "Follow-ups in the same session" section).

### 2.4 Model

Default: `openai/gpt-5.5` (variant `high`). Documented chain from `agent-model-matching.md:347-362` (Oracle row):

```
gpt-5.5 (high)  →  gemini-3.1-pro (high)  →  claude-opus-4-7 (max)  →  glm-5.1
```

**Category per the doc:** "Deep Specialists → GPT. These agents are built for GPT's principle-driven style. Their prompts assume autonomous, goal-oriented execution. Don't override to Claude." (See `agent-model-matching.md:357-373`.)

The doc is explicit and restrictive about safe overrides (`agent-model-matching.md:464-475`):

- **Dangerous:** "**Oracle → MiniMax**: Same reason. Oracle needs sustained reasoning; MiniMax drifts."
- **Safe (within GPT family):** gpt-5.5 → gpt-5.4 → gpt-5.5-codex.

The deepwiki "Worker Agents" page summarizes it as: "Oracle: Strategic advisor · subagent · High-IQ architecture/debug advice."

### 2.5 When to use

From `ORACLE_PROMPT_METADATA.useWhen` (`src/agents/oracle.ts:27-34`):

- "Complex architecture design"
- "After completing significant work"
- "2+ failed fix attempts"
- "Unfamiliar code patterns"
- "Security/performance concerns"
- "Multi-system tradeoffs"

External (docs.olares.com): "Read-only architecture consultant. Advises on architecture decisions and complex debugging without modifying files. Auto-dispatched in `ultrawork`."

Practical examples from the omo community:

- `https://www.glukhov.org/ai-devtools/opencode/oh-my-opencode/`: `"ultrawork ask @oracle to design the endpoint contract and dependencies first, then implement with minimal changes and add tests"`.
- Deepwiki on `Sisyphus Delegation Strategy`: "Complex architecture → consult Oracle."

### 2.6 When NOT to use

From `ORACLE_PROMPT_METADATA.avoidWhen` (`src/agents/oracle.ts:35-42`):

- "Simple file operations (use direct tools)"
- "First attempt at any fix (try yourself first)"
- "Questions answerable from code you've read"
- "Trivial decisions (variable names, formatting)"
- "Things you can infer from existing code patterns"

**Team mode.** Oracle is **hard-rejected** as a team-mode agent. From `docs/guide/team-mode.md:79-86`:

> "**Eligible:** `sisyphus`, `atlas`, `sisyphus-junior`. **Conditional:** `hephaestus` (needs teammate permission `teammate: "allow"`; otherwise use `subagent_type: "sisyphus"`). **Hard-reject:** `oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus`. Hard-reject agents fail TeamSpec parsing because they cannot write mailbox state. Use `delegate-task` for those agents."

So Oracle is excluded from team mode structurally — its read-only restriction (no `write`/`edit`/`apply_patch`/`task`) makes it incompatible with the team mailbox protocol.

### 2.7 Source location

- `src/agents/oracle.ts` (452 lines) — `ORACLE_PROMPT_METADATA`, three prompt constants, `createOracleAgent(model)` factory, tool restrictions via `createAgentToolRestrictions(["write","edit","apply_patch","task"])`
- Registration path: not present as a separate `src/agents/builtin-agents/oracle-agent.ts` (per the directory listing) — registered through `general-agents.ts` in `src/agents/builtin-agents/`
- Doc page (deepwiki mirror): `https://deepwiki.com/code-yeongyu/oh-my-openagent/3.3-worker-agents` ("Oracle (Advisor)" subsection)

---

## Cross-cutting notes & gaps

- **Where "ask the oracle" actually lives.** There is no keyword-detector regex for "oracle" (`src/hooks/keyword-detector/constants.ts:48-67` only registers `ultrawork`, `search`, `analyze`, `team`, `hyperplan`, and the `hyperplan-ultrawork` combo). The "ask the oracle" / `@oracle` pattern is convention enforced by the Sisyphus prompt's delegation rules, not by a hook. The orchestrator surfaces Oracle's existence via `ORACLE_PROMPT_METADATA.triggers` (rendered into the Atlas decision matrix by `buildDecisionMatrix`).
- **Atlas's idle-event is what makes it a "Boulder Orchestrator"** rather than just another primary agent. The four moving parts are: `.omo/boulder.json` state file, the `start-work` hook (registers the boulder), the `atlas-hook` (handler skeleton), and `idle-event.ts` (the actual `session.idle` consumer with cooldown + backoff + `BOULDER_COMPLETE` final nudge).
- **Verifier in the title.** Oracle is a per-question consultant, not a plan-level verifier. The actual "approve/reject" gate on plans is the **Final Verification Wave** in the Atlas lifecycle (F1-F4 reviewers, including Momus), defined in `src/hooks/atlas/final-wave-approval-gate.ts` and the Atlas default prompt's "Step 4: Final Verification Wave" section.
- **Honest gaps.** I could not pull the full text of the `gpt.md`, `opus-4-7.md`, `gemini.md`, and `kimi.md` Atlas variants — only the default and the AGENTS.md file listing exist on the public web in a directly fetchable form. I also could not verify the exact line counts for `system-reminder-templates.ts`'s `BOULDER_COMPLETE_PROMPT` shape (the idle-event output was truncated past line ~360 in the web fetch — the file is 515 lines). The `atlas-prompt.test.ts`/`prompt-routing.test.ts` files assert byte-for-byte invariants between the inlined markdown and runtime injections, which strongly implies the `default.md` and the five placeholders are the canonical contract for the prompt body.

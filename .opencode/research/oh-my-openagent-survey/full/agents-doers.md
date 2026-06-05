# Doer Agents Survey: Sisyphus, Sisyphus-Junior, Hephaestus

The three agents in `oh-my-openagent` (omo) that actually *do* code: a primary orchestrator that also implements (Sisyphus), a category-spawned executor for delegated work (Sisyphus-Junior), and an autonomous deep worker built for GPT (Hephaestus). All three share a common builder pipeline but diverge sharply in mode, model, and prompt shape.

---

## 1. Sisyphus — Main Orchestrator (Tab 0, primary)

### Purpose
The "batteries-included" default agent. Plans obsessively, classifies user intent, delegates specialized work to subagents in parallel, and only implements directly when the task is trivial or no specialist fits. Drives tasks to completion with "no AI slop" discipline.

### Prompt shape
Stored in `src/agents/sisyphus.ts` (~664 lines, 25.9 KB) with model-specific variants in `src/agents/sisyphus/` (`default.ts`, `claude-opus-4-7.ts`, `gpt-5-4.ts`, `gpt-5-5.ts`, `kimi-k2-6.ts`, `gemini.ts`). Built by `buildDynamicSisyphusPrompt()` which composes sections from `dynamic-agent-prompt-builder.ts`:

- `<Role>` — identity ("SF Bay Area engineer. Work, delegate, verify, ship.")
- **Phase 0** — Intent Gate: verbalize intent, classify request type (Trivial / Explicit / Exploratory / Open-ended / Ambiguous), turn-local intent reset, ambiguity check, context-completion gate, delegation check
- **Phase 1** — Codebase Assessment (open-ended tasks only)
- **Phase 2A** — Exploration & Research (explore/librarian sections, parallel delegation)
- **Phase 2B** — Implementation
- `<tool_usage_rules>`, `<Constraints>`, hard blocks, anti-patterns, oracle/consensus sections, category+skills delegation guide, task-management section

Gemini gets four extra patches injected mid-prompt to fight lost-in-the-middle (intent-gate enforcement, tool guide, delegation+verification overrides before `<Constraints>`). GPT-5.4/5.5 use entirely different builder functions (`buildGpt54SisyphusPrompt`, `buildGpt55SisyphusPrompt`).

### Triggers
- **Default agent on session start** (order: 0 in the deterministic tab cycle: Sisyphus → Hephaestus → Prometheus → Atlas).
- User types in the main TUI prompt with no agent prefix.
- Eligible as `lead` or `member` in Team Mode via `kind: "subagent_type"`.
- `ulw` / `ultrawork` keyword activates "every agent" mode within Sisyphus.

### Model
`anthropic/claude-opus-4-7` (variant `max`), reasoning effort inherited from Claude thinking config (32k budget tokens). Fallback chain (per `docs/reference/features.md` and `src/shared/model-requirements.ts`):

`claude-opus-4-7 (max)` → `opencode-go/kimi-k2.6` → `kimi-for-coding/k2p5` → `kimi-k2.5` family → `gpt-5.5 (medium)` → `glm-5` → `opencode/big-pickle`.

Per the agent-model-matching doc: Sisyphus is a **utility/orchestrator** category — built for Claude-family models (Opus 4.7), Kimi K2.6, and GLM 5.1. GPT-5.4 and 5.5 have dedicated prompt paths now but older GPT models are explicitly steered toward Hephaestus instead. The `no-sisyphus-gpt` hook hard-blocks incompatible GPT models at message time.

```ts
// src/agents/sisyphus.ts (≈ line 590-640, dev branch)
description: "Powerful AI orchestrator. Plans obsessively with todos, assesses search complexity before exploration, delegates strategically via category+skills combinations...",
mode: "primary",
model,
maxTokens: 64000,
color: "#00CED1",
permission: { question: "allow", call_omo_agent: "deny" },
// Claude path: thinking: { type: "enabled", budgetTokens: 32000 }
// GPT path:    reasoningEffort: "medium"
```

### When to use
- Default for *any* user request. Per `docs/guide/overview.md`: "He plans, delegates to specialists, and drives tasks to completion with aggressive parallel execution. He doesn't stop halfway."
- Complex multi-step tasks where orchestration value exceeds direct execution.
- Anywhere you want the Intent Gate + verbalization + category delegation flow.

### When NOT to use
- On older / incompatible GPT models — `no-sisyphus-gpt` hook will block.
- When you need pure single-model deep execution with no orchestration overhead → use Hephaestus.
- When the task is so trivial that even classification adds noise → user usually just lets Sisyphus self-classify it as "Trivial" and proceed directly.

### Source location
- Factory: `src/agents/sisyphus.ts` (664 lines on dev as of 2026-06; 559 LOC earlier per `src/agents/AGENTS.md`).
- Builder helpers: `src/agents/sisyphus/{default,claude-opus-4-7,gpt-5-4,gpt-5-5,kimi-k2-6,gemini}.ts`.
- Registration: `src/agents/builtin-agents.ts` (`agentSources.sisyphus = createSisyphusAgent`) and `maybeCreateSisyphusConfig()` in `src/agents/builtin-agents/sisyphus-agent.ts`.
- Metadata: `SISYPHUS_PROMPT_METADATA = { category: "utility", cost: "EXPENSIVE", promptAlias: "Sisyphus", triggers: [] }` (`src/agents/sisyphus.ts:30-35`).

---

## 2. Sisyphus-Junior — Category-Spawned Executor

### Purpose
The delegated executor that runs whenever an orchestrator (Sisyphus, Atlas, Hephaestus) calls `task(category="…")`. It executes the assigned categorized work end-to-end *without* re-delegating, preventing infinite delegation loops. As of `1566cfc` (2026-02-16) it was rewritten in "Hephaestus style" — full autonomy, parallelism, reporting, no "you work ALONE" messaging.

### Prompt shape
Stored under `src/agents/sisyphus-junior/` as a per-model directory:

```
src/agents/sisyphus-junior/
├── agent.ts                  # createSisyphusJuniorAgentWithOverrides, SISYPHUS_JUNIOR_DEFAULTS, getSisyphusJuniorPromptSource
├── index.ts                  # barrel
├── default.ts                # Claude / generic path
├── gpt.ts                    # generic GPT path
├── gpt-5-3-codex.ts          # GPT-5.3 Codex tuned
├── gpt-5-4.ts                # GPT-5.4 native
├── gpt-5-5.ts                # GPT-5.5 native (added c57d08c, 2026-04-24)
└── gemini.ts                 # Gemini path
```

`getSisyphusJuniorPromptSource(model)` routes to one of `"default" | "gpt" | "gpt-5-5" | "gpt-5-4" | "gpt-5-3-codex" | "gemini"`. Each builder returns a string; the GPT-5.5 template is ~254 lines and explicitly says:

> "You are the category-spawned counterpart to Hephaestus. Hephaestus handles open-ended exploratory work under direct user conversation; you handle well-defined categorized tasks routed through an orchestrator."

Key sections (post-Hephaestus-style rewrite):
- `<Role>` / `## Identity and role` — "Execute tasks directly" — no "you work ALONE" language anymore
- `## Autonomy & Persistence` + Three-attempt failure protocol
- `## Ambiguity Protocol (EXPLORE FIRST)` — table of situation → action
- `<tool_usage_rules>` — parallelize independent calls, call_omo_agent for research only
- `<Todo_Discipline>` / `## Task Discipline` (per `useTaskSystem` flag)
- `## Progress Updates` + Code Quality
- `# Category context` block — runtime-injected `promptAppend` carries the category-specific guidance (deep, quick, ultrabrain, writing, …)

Tool restrictions (`createAgentToolRestrictions`) deny `task` and (historically) `sisyphus_task` so it can't re-delegate. `call_omo_agent` is allowed for spawning `explore`/`librarian`/`oracle` research-only.

### Triggers
- Spawned implicitly by `task(category="…", prompt="…")` calls from any agent that has access to the category-delegation tool. The category model overrides the agent's default at request time.
- In **Team Mode**, eligible as a direct `kind: "subagent_type"` lead or member, OR as the implicit executor for any `kind: "category"` member.
- Never invoked directly by the user from the TUI tab cycle (it isn't in the core tab order Sisyphus / Hephaestus / Prometheus / Atlas).

### Model
**Category-dependent.** The model is selected by whichever category routed to it. Defaults: `claude-sonnet-4-6` (`SISYPHUS_JUNIOR_DEFAULTS.model = "anthropic/claude-sonnet-4-5"` in earlier branches; current `claude-sonnet-4-6`), temperature `0.1`, `maxTokens: 64000`.

Built-in general fallback chain (`src/shared/model-requirements.ts`, PR #2352):

`anthropic|github-copilot|opencode/claude-sonnet-4-6` → `opencode-go/kimi-k2.6` → `openai|github-copilot|opencode/gpt-5.5 (medium)` → `opencode-go/minimax-m2.7` → `opencode/big-pickle`.

Per the matching doc, it can land on any category model — `visual-engineering` (Gemini 3.1 Pro), `ultrabrain` (GPT-5.5 xhigh), `deep` (GPT-5.5 medium), `quick` (GPT-5.4 Mini), `writing` (Claude Opus 4.7), etc. The `sisyphus-junior-notepad` PreToolUse hook manages notepad state across category invocations.

```ts
// src/agents/sisyphus-junior.ts (≈ legacy single-file variant)
export const SISYPHUS_JUNIOR_DEFAULTS = {
  model: "anthropic/claude-sonnet-4-5",
  temperature: 0.1,
} as const
// BLOCKED_TOOLS = ["task", "sisyphus_task", "call_omo_agent"]  // historical;
// current dev branch allows call_omo_agent for research
mode: "subagent",
description: "Sisyphus-Junior - Focused task executor. Same discipline, no delegation.",
color: "#20B2AA",
```

### When to use
- Whenever an orchestrator decides "this is a categorized unit of work" — let it spawn Junior. Don't invoke directly.
- Team Mode `kind: "category"` members route through Junior automatically (per `docs/guide/team-mode.md`).
- User-configurable via `agents["Sisyphus-Junior"]` in `oh-my-opencode.json` (model, temperature, prompt_append, tools, permission) per PR #648.

### When NOT to use
- For interactive conversation — it's a sub-agent (`mode: "subagent"`), not a primary tab agent.
- For work that needs further delegation to other categories — Junior is the *terminal* executor by design (prevents infinite loops). If sub-categories matter, the orchestrator should decompose before spawning.
- It is **eligible** in Team Mode's `AGENT_ELIGIBILITY_REGISTRY` (`docs/guide/team-mode.md`: "Eligible: `sisyphus`, `atlas`, `sisyphus-junior`"), so the exclusion is the opposite: don't use the *hard-rejected* read-only agents in its place.

### Source location
- Factory: `src/agents/sisyphus-junior/agent.ts` exporting `createSisyphusJuniorAgentWithOverrides` and `SISYPHUS_JUNIOR_DEFAULTS`.
- Per-model prompts: `src/agents/sisyphus-junior/{default,gpt,gpt-5-3-codex,gpt-5-4,gpt-5-5,gemini}.ts`.
- Registration: `src/agents/builtin-agents.ts` (`"sisyphus-junior": createSisyphusJuniorAgentWithOverrides as unknown as AgentFactory`); special-cased out of `collectPendingBuiltinAgents` in `src/agents/builtin-agents/general-agents.ts` (same pattern as Atlas).
- Schema: `src/config/schema/agent-names.ts` `BuiltinAgentNameSchema` includes `"sisyphus-junior"`; `src/agents/types.ts` `BuiltinAgentName` union includes it.
- Tests: `src/agents/sisyphus-junior/index.test.ts` (asserts `## Identity`, `Scope Discipline`, `<tool_usage_rules>`, `Progress Updates` for GPT path; `<Role>`, `<Todo_Discipline>`, `todowrite` for Claude path).

---

## 3. Hephaestus — The Legitimate Craftsman

### Purpose
Autonomous deep worker on GPT-5.5 ("Codex on steroids"), inspired by AmpCode's deep mode. Receives goals — not step-by-step instructions — and executes end-to-end with thorough research before action. Named with intentional irony: Anthropic blocked OpenCode from their API because of this project, so the team built a GPT-native agent ("born from necessity, not privilege").

### Prompt shape
Stored under `src/agents/hephaestus/` (refactored from the historical single-file `hephaestus.ts` at 507–618 LOC). Per `agent.ts`:

```
src/agents/hephaestus/
├── agent.ts          # createHephaestusAgent, getHephaestusPromptSource, HephaestusPromptSource
├── gpt.ts            # generic GPT path
├── gpt-5-3-codex.ts  # GPT-5.3 Codex path
├── gpt-5-4.ts        # GPT-5.4 native
└── gpt-5-5.ts        # GPT-5.5 native (added a432e29, 2026-04-24; tightened caaa3d4, 2026-05-06)
```

`getHephaestusPromptSource(model)` checks `gpt-5-5` first, then `gpt-5-4`, then `gpt-5-3-codex`, then generic `gpt`. The GPT-5.5 template (`gpt-5-5.ts`, ~301+ lines) replaces threat-style rhetoric ("FORBIDDEN", "NEVER") with contract frames ("Forbidden stops", "Three-attempt failure protocol"). Major sections:

- **Identity and role** — "an autonomous deep worker on GPT-5.5… you receive goals, not step-by-step instructions, and execute them end-to-end. You are Hephaestus, the forge god. Where other agents orchestrate, you execute."
- **Tone** — "Warm but spare. Communicate efficiently."
- **Autonomy & Collaboration** — default: implement, don't propose
- **Goal** — "an artifact that **works when used through its surface**" (not "green build")
- **Intent** — one-line intent statement before acting; commitment to finish in same turn
- **Manual QA Gate** — drive the artifact through its matching surface (`interactive_bash` for TUI/CLI, `playwright` for browser, `curl` for HTTP, driver script for library)
- **Discovery & Retrieval** — fire 2–5 `explore`/`librarian` sub-agents in parallel with `run_in_background=true`
- **Tool Use** — `task()` for research subagents (`explore`, `librarian`, `oracle`) and *limited* category delegation for genuinely disjoint sub-work; `GPT_APPLY_PATCH_GUIDANCE` for file edits
- **Three-attempt failure protocol**, **Dig deeper trio**, **Stop Rules**
- `{{ taskSystemGuide }}`, `{{ categorySkillsGuide }}`, `{{ delegationTable }}`, `{{ oracleSection }}`, `{{ frontendGuidance }}` — placeholders filled by `buildGpt55HephaestusPrompt(...)`

Earlier prompt versions added an Intent Gate, Assumptions Check, Challenge-the-User block, and "Parallel Execution & Tool Usage" rules ported back from Sisyphus (commit `199992e`, 2026-02-16).

### Triggers
- **Tab key (order: 1)** in the deterministic core-agent tab cycle — Sisyphus → **Hephaestus** → Prometheus → Atlas. User explicitly selects it.
- In Team Mode: **conditional** — eligible as a direct `kind: "subagent_type"` lead/member only when the calling agent has `teammate: "allow"` permission; otherwise the parser substitutes `subagent_type: "sisyphus"`.
- Hooks: `no-hephaestus-non-gpt` Message hook prevents Hephaestus from running on non-GPT models.

### Model
`openai/gpt-5.5` (variant `medium`). Per the `Hephaestus Agent` API doc: "Hephaestus does NOT have a deep fallback chain. If both models are unavailable, the agent cannot be used. This is intentional — Hephaestus is optimized specifically for GPT's reasoning capabilities." Required providers: `openai`, `github-copilot`, `venice`, `opencode`.

Per the agent-model-matching doc, Hephaestus lives in the **deep** category (autonomous research and execution; `"deep": { "model": "openai/gpt-5.5", "variant": "medium" }`). Note the user's prompt referenced "GPT-5.5 xhigh in the deep category" — current `dev` actually maps `deep` to GPT-5.5 *medium* and `ultrabrain` to GPT-5.5 *xhigh*; older snapshots routed `deep` to GPT-5.4 high. This is a moving target — re-verify against the live `categories` block before quoting.

```ts
// src/agents/hephaestus.ts (legacy single-file form)
description: "Autonomous Deep Worker - goal-oriented execution with GPT 5.2 Codex. Explores thoroughly before acting, uses explore/librarian agents for comprehensive context, completes tasks end-to-end. Inspired by AmpCode deep mode. (Hephaestus - OhMyOpenCode)",
mode: "primary",
model,
maxTokens: 32000,
color: "#D97706",   // Forged Amber
permission: { question: "allow", call_omo_agent: "deny" },
reasoningEffort: "medium",
```

### When to use
Per `docs/guide/orchestration.md` "Hephaestus vs Sisyphus + ultrawork":

1. **Deep architectural reasoning needed** — "Design a new plugin system", "Refactor this monolith into microservices".
2. **Complex debugging requiring inference chains** — "Why does this race condition only happen on Tuesdays?", "Trace this memory leak through 15 files".
3. **Cross-domain knowledge synthesis** — "Integrate our Rust core with the TypeScript frontend", "Migrate from MongoDB to PostgreSQL with zero downtime".
4. **You specifically want GPT-5.5's reasoning style** — some problems benefit from GPT-5.5's training characteristics over Claude's.

Recommendation in the docs: "For most users: Use `ulw` keyword in Sisyphus. For power users: Switch to Hephaestus when you specifically need GPT-5.5's reasoning style or want the AmpCode deep-mode experience of fully autonomous exploration and execution."

### When NOT to use
- On non-GPT models — `no-hephaestus-non-gpt` hook blocks; the API doc explicitly lists "Dangerous overrides: Hephaestus → Claude (built for Codex)".
- Default day-to-day orchestration — Sisyphus is the right tool; Hephaestus is a deliberate switch.
- Team Mode lead/member when caller lacks `teammate: "allow"` — parser substitutes Sisyphus and rejects the Hephaestus spec.

### Source location
- Factory: `src/agents/hephaestus/agent.ts` exporting `createHephaestusAgent`, `getHephaestusPromptSource`, type `HephaestusPromptSource`.
- Per-model prompts: `src/agents/hephaestus/{gpt,gpt-5-3-codex,gpt-5-4,gpt-5-5}.ts`.
- Registration: `src/agents/builtin-agents.ts` (`agentSources.hephaestus = createHephaestusAgent`) and `maybeCreateHephaestusConfig()` in `src/agents/builtin-agents/hephaestus-agent.ts`. Special-cased order in `createBuiltinAgents()`: Sisyphus then Hephaestus, *then* pending agents, *then* Atlas — to maintain canonical tab order.
- Model requirement: `src/shared/model-requirements.ts` — GPT-5.5 medium only, no fallback.

---

## Cross-cutting notes

- All three live in the same `agentSources` map in `src/agents/builtin-agents.ts` and share:
  - `permission: { question: "allow", call_omo_agent: "deny" }` on the factories (Junior overrides historically; modern Junior allows call_omo_agent for research).
  - `temperature: 0.1` (per `src/agents/AGENTS.md` table).
  - `dynamic-agent-prompt-builder.ts` helpers (`buildExploreSection`, `buildLibrarianSection`, `buildDelegationTable`, `buildOracleSection`, `buildCategorySkillsDelegationGuide`, …) — same Lego pieces, different assemblies.
- Sisyphus and Hephaestus are `mode: "primary"`. Sisyphus-Junior is `mode: "subagent"` (per the legacy file) but registered as a *builtin* agent (PR #2352, `1c7eb55f`, 2026-03-07) so the model-fallback hook works for it.
- Team Mode eligibility (`docs/guide/team-mode.md`, PR #3493): **eligible** = `sisyphus`, `atlas`, `sisyphus-junior`; **conditional** = `hephaestus` (needs `teammate: "allow"`); **hard-rejected at parse** = `oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus`.
- Sisyphus-Junior's denied tools (per `src/agents/AGENTS.md` table): historically `task, sisyphus_task` (and `call_omo_agent` in some branches). Current dev allows `call_omo_agent` for research sub-agents.

### Gaps / honesty caveats
- LOC counts drift between branches (Sisyphus: 530 → 559 → 540 → 664; Hephaestus: 507 → 618 → split into per-model files). Numbers cited above are from `src/agents/AGENTS.md` snapshots and the live `dev` branch as visible 2026-06.
- Model defaults change frequently. The `deep` category was GPT-5.4 high, then GPT-5.5 high, now GPT-5.5 medium on `dev`. Treat any specific variant string as "as-of-snapshot".
- I could not directly fetch `src/agents/hephaestus.ts` on `dev` (404 — the file has been split into the `hephaestus/` directory). The factory's pre-split form was reconstructed from earlier commits and the per-model `gpt-5-5.ts` template diff (`a432e29`, `caaa3d4`).
- The "AGENT_ELIGIBILITY_REGISTRY" name comes from the team-mode docs and PR #3493 text; I did not locate a file literally named `agent-eligibility-registry.ts` — the rules appear to be enforced in the Team Mode parse step. Eligibility list itself is verified against `docs/guide/team-mode.md`.

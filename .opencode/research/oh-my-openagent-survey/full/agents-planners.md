# Planners / Reviewers in oh-my-openagent — Prometheus, Momus, Metis

**Repo:** `code-yeongyu/oh-my-openagent` (dev branch)
**Scope:** Three agents that form a planning-quality-control triad.
**Method:** Web research only — no clone, no code execution. Sources are linked inline.

---

## 1. Prometheus — The Strategic Planner

### 1.1 Purpose
Read-only strategic planner that runs an **interview** with the user, explores the codebase, and emits a markdown work plan at `.omo/plans/*.md`. It never writes source code. It also gates its own output with two sub-agents: Metis (pre-generation) and Momus (post-generation). ([overview.md:55-75](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/overview.md), [orchestration.md:91-122](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/orchestration.md))

### 1.2 Prompt shape
- **Storage location:** prompts have been refactored into a harness-neutral `packages/prompts-core/prompts/prometheus/` package, with three markdown variants — `default.md` (Claude), `gpt.md`, and `gemini.md`. The OpenCode adapter under `src/agents/prometheus/` is now a thin loader.
- **Loader files:** `src/agents/prometheus/index.ts:1-6` (barrel), `src/agents/prometheus/system-prompt.ts:1-39` (variant selection via `getPrometheusPromptSource(model)` → `"default" | "gpt" | "gemini"`), `src/agents/prometheus/gpt.ts`, `src/agents/prometheus/gemini.ts`.
- **Size asymmetry:** the Claude variant is **~1,100 lines across 7 files**; the GPT variant achieves the same behavior with **3 principles in ~121 lines** (XML structure, principle-driven). The runtime `isGptModel()` / `isGeminiModel()` checks auto-switch prompts — no manual juggling.
- **Key sections of the Claude prompt (recovered from AGENTS.md + orchestration docs):** interview state machine, intent classification (Refactoring / Build from Scratch / Mid-sized / Collaborative / Architecture / Research), MUST/MUST-NOT directives, QA/Acceptance Criteria directives (zero user intervention principle), workflow reminder, and a "plan re-read rule" requiring re-reading from disk on follow-up turns.
- **Tool gating:** `PROMETHEUS_PERMISSION` (system-prompt.ts:6-11) is `{edit: "allow", bash: "allow", webfetch: "allow", question: "allow"}`. A separate `prometheus-md-only` hook blocks `Write` and `Edit` unless the path targets `.omo/*.md` ([prometheus-md-only/hook.ts:1-20](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/prometheus-md-only/hook.ts)).

### 1.3 Triggers
- **User invocation:** either **press `Tab`** and select Prometheus from the agent list, or type **`@plan "your task"`** from inside Sisyphus — both invoke the same flow.
- **Internal invocation:** Sisyphus delegates to Prometheus for non-trivial tasks when `replace_plan: true` (default). The mandatory workflow reminder is injected via the `prometheus-md-only` hook constants (`src/hooks/prometheus-md-only/constants.ts:52-89`).
- **Prometheus itself dispatches to Metis** with `task(agent="Metis - Plan Consultant", ...)` and to **Momus** with `task(agent="Momus - Plan Critic", ...)` (constants.ts:64-66, 71-73).
- **Automatic or keyword-driven?** Both — keyword-driven from the user (Tab / `@plan`), and automatic from Sisyphus when it chooses to plan. Sisyphus's `planner_enabled` config flag controls the auto-routing.

### 1.4 Model
- **Default:** `claude-opus-4-7` (variant `max`) → `gpt-5.5` (high) → `glm-5.1` → `gemini-3.1-pro` ([agent-model-matching.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/agent-model-matching.md), `Prometheus` row).
- **Category per agent-model-matching doc:** "Dual-Prompt Agents → Claude preferred, GPT supported" — Prometheus ships separate prompts per model family and auto-switches.
- **Why Claude:** the 1,100-line mechanics-driven prompt needs high instruction-following compliance. Why GPT also works: 121-line principle-driven XML variant is tuned for GPT-5.5's "more rules = more drift" behavior. Other Claude-likes (Kimi K2.6, GLM 5.1) are listed as safe substitutions; older GPT models are a bad fit and should route elsewhere.

### 1.5 When to use (explicit)
- "Multi-day projects, critical production changes, complex refactoring, or when you want a documented decision trail" (overview.md).
- "Complex + Precise" lane in the orchestration TL;DR — when `ulw` is too lazy and you need verifiable execution.
- High-accuracy mode (Momus loop) when ≥80% of tasks needing clear references and ≥90% concrete acceptance criteria matters.

### 1.6 When NOT to use
- Simple / quick fixes — just prompt normally.
- "Complex + Lazy" — type `ulw` or `ultrawork` and let the agent figure it out.
- **Team Mode hard-reject:** `prometheus` is on the hard-reject list for `team_mode` team-member roles — `oracle, librarian, explore, multimodal-looker, metis, momus, prometheus` are all "Hard-reject" because they cannot write mailbox state. For these, use `delegate-task` instead ([team-mode.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/team-mode.md)).
- It cannot write source code — by design, the `prometheus-md-only` hook makes it impossible.

### 1.7 Source location
- `src/agents/prometheus/index.ts:1-6`
- `src/agents/prometheus/system-prompt.ts:1-39`
- `packages/prompts-core/prompts/prometheus/{default,gpt,gemini}.md`
- `src/hooks/prometheus-md-only/constants.ts:52-89` (workflow reminder)
- `src/hooks/prometheus-md-only/hook.ts:1-20` (write restriction)
- `docs/guide/agent-model-matching.md` (Prometheus row)
- `docs/guide/orchestration.md:91-160` (Prometheus section)

---

## 2. Momus — The Plan Reviewer

### 2.1 Purpose
A ruthless, read-only plan critic named after the Greek god of mockery. Its only job is to answer: **"Can a capable developer execute this plan without getting stuck?"** It does not design, plan, or implement — it just OKAYs or REJECTs. ([momus.ts:9-19](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/agents/momus.ts))

### 2.2 Prompt shape
- **Storage location:** a single self-contained file at `src/agents/momus.ts` contains both the default (Claude) and GPT prompt bodies as string constants.
- **Two variants:**
  - `MOMUS_DEFAULT_PROMPT` (momus.ts:31-147) — long-form markdown, ~115 lines, mechanics-driven for Claude. Sections: Critical First Rule, Your Purpose, What You Check (4 categories), What You Do NOT Check, Input Validation (Step 0), Review Process, Decision Framework, Anti-Patterns, Output Format, Final Reminders.
  - `MOMUS_GPT_PROMPT` (momus.ts:149-217) — principle-driven, XML-tagged (`<identity>`, `<input_extraction>`, `<plan_reread_rule>`, `<purpose>`, `<checks>`, `<review_process>`, `<decision_framework>`, `<anti_patterns>`, `<output_verbosity_spec>`, `<final_rules>`), shorter and more declarative.
- **Selection logic:** `isGptModel(model)` (momus.ts:225) returns either prompt; the GPT path also sets `reasoningEffort: "medium"` and `textVerbosity: "high"`. Claude path gets `buildClaudeThinkingConfig(model)`.
- **Tool restrictions:** `createAgentToolRestrictions(["write", "edit", "apply_patch"])` (momus.ts:219-223) — read-only reviewer.
- **Metadata block:** `momusPromptMetadata` (momus.ts:248-273) exports `category: "advisor"`, `cost: "EXPENSIVE"`, `triggers`, `useWhen`, `avoidWhen`, and the critical `keyTrigger` documenting how it should be invoked.

### 2.3 Triggers
- **Internal — by Prometheus** as the final mandatory step of the planning workflow. The `prometheus-md-only` hook constants inject: "MOMUS REVIEW: Verification loop via `task(agent='Momus - Plan Critic', ...)` until an `OKAY` verdict is reached" (constants.ts:71-73).
- **Manual — high-accuracy mode** is selected by the user after Prometheus writes a plan. Per orchestration.md:143-156, Momus only says OKAY when 100% of file references are verified, ≥80% of tasks have clear references, ≥90% have concrete acceptance criteria, and zero contradictions or business-logic assumptions.
- **Input validation:** Momus's `keyTrigger` says explicitly: "Work plan saved to `.omo/plans/*.md` → invoke Momus with the file path as the sole prompt (e.g. `prompt='.omo/plans/my-plan.md'`). Do NOT invoke Momus for inline plans or todo lists" (momus.ts:267-272). YAML files are rejected.
- **Automatic or keyword-driven?** Automatic from Prometheus's workflow; manual for explicit high-accuracy review.

### 2.4 Model
- **Default:** `gpt-5.5` (variant `xhigh`) → `claude-opus-4-7` (max) → `gemini-3.1-pro` (high) → `glm-5.1` ([agent-model-matching.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/agent-model-matching.md), `Momus` row).
- **Category:** "Deep Specialists → GPT" — Momus is grouped with Hephaestus and Oracle. The doc explicitly warns "Don't override to Claude" for this group (Claude is only the fallback).
- **Why GPT-5.5 xhigh:** the README's section on "Deep Specialists" notes GPT-5.5 uses xhigh variant for Momus. Stable, reproducible critique is the goal — glukhov.org's deep-dive recommends temperature ≤ 0.1 for self-hosted equivalents.
- **Temperature:** `0.1` (momus.ts:230), reinforcing "stable, reproducible critique."

### 2.5 When to use (explicit)
- "After Prometheus creates a work plan"
- "Before executing a complex todo list"
- "To validate plan quality before delegating to executors"
- "When plan needs rigorous review for ADHD-driven omissions"
- (all four from `momusPromptMetadata.useWhen`, momus.ts:255-260)

### 2.6 When NOT to use
- "Simple, single-task requests"
- "When user explicitly wants to skip review"
- "For trivial plans that don't need formal review"
- (all three from `momusPromptMetadata.avoidWhen`, momus.ts:261-265)
- **Team Mode hard-reject:** `momus` is explicitly listed under the "Hard-reject" team-member eligibility list ([team-mode.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/team-mode.md)). Use `delegate-task` instead.
- **80% clarity threshold / approval bias:** Momus will REJECT only for true blockers, and only list up to 3 specific issues. Do not invoke it expecting exhaustive design opinions.

### 2.7 Source location
- `src/agents/momus.ts:1-273` (full file — agent + both prompt variants)
- `src/agents/momus.test.ts:20-29` (path-extraction tests)
- `src/shared/agent-tool-restrictions.ts:48-51` (write/edit deny)
- `src/hooks/prometheus-md-only/constants.ts:71-73` (MOMUS_REVIEW workflow injection)
- `docs/guide/agent-model-matching.md` (Momus row)

---

## 3. Metis — The Pre-Planning Gap Analyzer

### 3.1 Purpose
A pre-planning consultant (Greek goddess of wisdom / counsel) that runs **before** Prometheus drafts the plan. It identifies hidden intentions, ambiguities, AI-slop patterns, and missing acceptance criteria, then emits intent-specific directives (MUST/MUST-NOT) that Prometheus must incorporate. ([metis.ts:1-20](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/agents/metis.ts))

### 3.2 Prompt shape
- **Storage location:** single self-contained file at `src/agents/metis.ts`. One prompt body, `METIS_SYSTEM_PROMPT`, no model-family variant split (only Claude path exists in the current file).
- **Length:** ~165 lines (metis.ts:22-178). Larger than Momus's default prompt but smaller than Prometheus's.
- **Structure:**
  - `## CONSTRAINTS` — read-only, output feeds Prometheus. Includes injected `buildAntiDuplicationSection()` (imported from `dynamic-agent-prompt-builder`).
  - `## PHASE 0: INTENT CLASSIFICATION (MANDATORY FIRST STEP)` — six categories: Refactoring, Build from Scratch, Mid-sized Task, Collaborative, Architecture, Research.
  - `## PHASE 1: INTENT-SPECIFIC ANALYSIS` — one block per intent with mission, tool guidance, questions, and MUST/MUST-NOT directives.
  - `## OUTPUT FORMAT` — a fixed markdown template: Intent Classification, Pre-Analysis Findings, Questions for User, Identified Risks, Directives for Prometheus (with mandatory QA/Acceptance Criteria directives using the "ZERO USER INTERVENTION PRINCIPLE").
  - `## TOOL REFERENCE` and `## CRITICAL RULES`.
- **Tool restrictions:** `createAgentToolRestrictions(["write", "edit", "apply_patch"])` (metis.ts:181-184). Mode is `subagent`. Temperature `0.3` (metis.ts:191) — slightly higher than Momus's 0.1, because the glukhov.org deep-dive notes "creative gap detection" benefits from non-zero temperature.
- **Metadata block:** `metisPromptMetadata` (metis.ts:201-213) — `category: "advisor"`, `cost: "EXPENSIVE"`, `triggers`, `useWhen`, `avoidWhen`, `keyTrigger: "Ambiguous or complex request → consult Metis before Prometheus"`.

### 3.3 Triggers
- **Internal — by Prometheus** as the mandatory second step of the planning workflow: "METIS CONSULTATION: Pre-generation gap analysis via `task(agent='Metis - Plan Consultant', ...)`" (prometheus-md-only/constants.ts:64-66). Per DeepWiki, the Metis consultation is **mandatory** before plan generation — Prometheus cannot skip it.
- **From Metis itself:** for "Build from Scratch" and "Research" intents, Metis launches background `call_omo_agent(subagent_type="explore", ...)` and `call_omo_agent(subagent_type="librarian", ...)` probes before asking the user clarifying questions (metis.ts:83-90, 158-164).
- **For Architecture intent:** Metis recommends `task(subagent_type="oracle", ...)` to Prometheus (metis.ts:151-165).
- **Automatic or keyword-driven?** Automatic from Prometheus's workflow. There is no user-facing keyword to invoke Metis directly; it runs as a subagent gated by Prometheus.

### 3.4 Model
- **Default:** `claude-sonnet-4-6` → `claude-opus-4-7` (max) → `gpt-5.5` (high) → `glm-5.1` → `k2p5` ([agent-model-matching.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/agent-model-matching.md), `Metis` row).
- **Category:** "Communicators → Claude / Kimi / GLM" — same bucket as Sisyphus. Sonnet is the default; Opus is the first fallback.
- **Why Claude:** Metis needs to follow long, structured instructions (intent classification + per-intent analysis + output template), and the doc notes "More rules = more compliance" for Claude-family models. Sonnet (not Opus) is the default — a cost optimization; Opus is the fallback when Sonnet is unavailable.
- **Unsafe override:** per glukhov.org and agent-model-matching, "MiniMax → STRONGLY DISCOURAGED" for this role — long-context management issues make it a poor substitute.

### 3.5 When to use (explicit)
- "Before planning non-trivial tasks"
- "When user request is ambiguous or open-ended"
- "To prevent AI over-engineering patterns"
- (all three from `metisPromptMetadata.useWhen`, metis.ts:206-210)
- The output template forces "QA/Acceptance Criteria Directives (MANDATORY)" and the "ZERO USER INTERVENTION PRINCIPLE" — every deliverable must be agent-executable.

### 3.6 When NOT to use
- "Simple, well-defined tasks"
- "User has already provided detailed requirements"
- (both from `metisPromptMetadata.avoidWhen`, metis.ts:211-213)
- **Team Mode hard-reject:** `metis` is in the same "Hard-reject" team-member list as Momus and Prometheus ([team-mode.md](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/team-mode.md)). Use `delegate-task` instead.

### 3.7 Source location
- `src/agents/metis.ts:1-213` (full file — agent + single prompt variant + metadata)
- `src/shared/agent-tool-restrictions.ts:43-46` (write/edit deny)
- `src/hooks/prometheus-md-only/constants.ts:64-66` (METIS_CONSULTATION injection)
- `docs/guide/agent-model-matching.md` (Metis row)
- `docs/guide/overview.md:123-142` (gap-analysis philosophy)

---

## Cross-cutting notes

- **Triad ordering:** Interview → Metis consultation → plan generation → Momus review. Momus loops until `[OKAY]`. The `prometheus-md-only` hook injects the workflow reminder (constants.ts:46-89) so Prometheus cannot accidentally skip steps.
- **All three are subagents in the planning layer**, but Prometheus is `mode: "primary"` (it shows in the Tab cycle), while Metis and Momus are `mode: "subagent"` (only invokable via `task(agent="...")` or by another agent).
- **Tool restrictions are uniform:** all three deny `write` / `edit` / `apply_patch`. Prometheus's restriction is path-scoped (`.omo/*.md` only) via a separate hook.
- **The 80% clarity threshold is real but not named in code:** orchestration.md documents it as 100% references / ≥80% clear references / ≥90% acceptance criteria, while Momus's prompt itself phrases it as "APPROVAL BIAS — A plan that's 80% clear is good enough." Both convey the same approval bias.
- **Honest gaps in this research:** I did not clone the repo, so I could not measure the exact line counts of the markdown prompt variants in `packages/prompts-core/prompts/prometheus/` — the ~1,100 vs ~121 figures come from agent-model-matching.md's prose and may include the 7-file breakdown differently. The actual code references for the prompts are confirmed (system-prompt.ts loader, AGENTS.md for `src/agents/prometheus/`). Issue #806 documents a real-world hang on Windows when invoking Momus — relevant to anyone planning a parallel "always-review" workflow.
- **Naming churn:** the upstream repo is branded `oh-my-openagent` (since 2026) but the npm package, install command, and most docs URLs still use `oh-my-opencode` — both work.

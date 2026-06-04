# Category-Based Model Routing in oh-my-openagent

**Source:** https://github.com/code-yeongyu/oh-my-openagent (branch: `dev`)
**Date surveyed:** 2026-06-05
**Scope:** Light survey of category strings, resolution function, fallback chains, dangerous-override detection, and cost tiers.

---

## 1. The concept (one paragraph)

When an agent (Sisyphus, Atlas, Sisyphus-Junior) delegates work via the `task(category="…")` tool, it does **not** name a model. It names a **category** — a semantic label for "what kind of work is this?" (visual, deep reasoning, quick fix, prose, etc.). The harness maps that string to a real `provider/model` call via a hardcoded fallback chain that is tried in priority order until one is reachable. Users can override category defaults in `oh-my-openagent.json[c]` under a `categories:` key. This decouples intent from model names so a user can swap providers (e.g. switch from Anthropic to OpenCode-Go's Kimi K2.6) without re-teaching every agent. Source: `docs/guide/agent-model-matching.md:182-205` ("Task Categories" table) and `docs/guide/orchestration.md:241-261`.

---

## 2. The built-in categories (authoritative list)

Defined in `packages/model-core/src/model-requirements.ts:209-354` as `CATEGORY_MODEL_REQUIREMENTS`. Each entry has a `fallbackChain: FallbackEntry[]` and an optional default `variant`.

| Category | Default model | Default variant | Family | Approx. cost tier |
|----------|---------------|-----------------|--------|-------------------|
| `visual-engineering` | `google/gemini-3.1-pro` | `high` | Gemini | mid |
| `ultrabrain` | `openai/gpt-5.5` | `xhigh` | GPT | **highest** |
| `deep` | `openai/gpt-5.5` | `medium` | GPT | high |
| `artistry` | `google/gemini-3.1-pro` | `high` | Gemini | mid |
| `quick` | `openai/gpt-5.4-mini` | (none) | GPT-mini | **lowest** |
| `unspecified-low` | `anthropic/claude-sonnet-4-6` | (none) | Claude | mid |
| `unspecified-high` | `anthropic/claude-opus-4-7` | `max` | Claude | high |
| `writing` | `google/gemini-3-flash` | (none) | Gemini | low |

Notes:
- Orchestration doc (`docs/guide/orchestration.md:241-249`) also lists `quick-rust`, `quick-zig`, `git` as "user-facing orchestration names" but these are **not** present in `CATEGORY_MODEL_REQUIREMENTS`. They appear to be either project-injected categories (built per-project under `src/tools/delegate-task/*-categories.ts`) or stale doc references. **Honest gap: I could not confirm the status of those three names from the source I read.**
- `unspecified-low` / `unspecified-high` are catch-all buckets for work that doesn't fit a named category. The orchestrator prompt instructs the planner to pick the matching named category when one applies (`docs/guide/agent-model-matching.md:204`).
- Each category has a companion **prompt append** in `src/tools/delegate-task/builtin-categories.ts` (re-exported from `openai-categories.ts`, `google-categories.ts`, `anthropic-categories.ts`, `kimi-categories.ts`). E.g. `deep` has a different system prompt when the resolved model is `gpt-5.5` (`resolveDeepCategoryPromptAppend` in `openai-categories.ts:79-83`). The category string therefore controls **both** the model **and** the system prompt.

### Sample entry (verbatim from `packages/model-core/src/model-requirements.ts:248-256`)

```ts
ultrabrain: {
  fallbackChain: [
    { providers: ["openai","opencode","vercel"], model: "gpt-5.5", variant: "xhigh" },
    { providers: ["google","github-copilot","opencode","vercel"], model: "gemini-3.1-pro", variant: "high" },
    { providers: ["anthropic","github-copilot","opencode","vercel"], model: "claude-opus-4-7", variant: "max" },
    { providers: ["opencode-go","vercel"], model: "glm-5.1" },
  ],
},
```

---

## 3. How a category string becomes a model call

Two layers, both call into `packages/model-core`.

### 3a. Category-config resolution (per-task, in `src/`)

`src/tools/delegate-task/categories.ts:17-72` — `resolveCategoryConfig(categoryName, options)`:

1. Look up `DEFAULT_CATEGORIES[categoryName]` (default model + prompt append from `builtin-categories.ts`).
2. Merge with `userCategories[categoryName]` from `oh-my-openagent.json` (user override).
3. If user set `disable: true`, return `null` (category is opted out).
4. **Gate check:** if the category's `ModelRequirement.requiresModel` is set and that model is not in `availableModels`, return `null` and log a message. (In the built-in categories I inspected, none of `ultrabrain`/`deep`/`quick`/`visual-engineering` set `requiresModel` — the field is a generic mechanism for categories that hard-require a specific model.)
5. Call `resolveModel()` (`packages/model-core/src/model-resolver.ts:33-39`) with priority `userModel > inheritedModel (=defaultConfig.model) > systemDefault`.
6. Attach the category's prompt append (and append user `prompt_append` if any).

The output is what `task(category="…")` actually invokes. The resulting model + prompt go to a Sisyphus-Junior agent that runs them.

### 3b. Pipeline resolution (the hardcoded fallback chain)

`packages/model-core/src/model-resolution-pipeline.ts:65-200` — `resolveModelPipeline(request, providerCache)`. The `request.intent` carries `uiSelectedModel`, `userModel`, `userFallbackModels`, `categoryDefaultModel`. The `request.policy` carries `fallbackChain` and `systemDefaultModel`. Pipeline, in order:

```
1. UI selection        → if uiSelectedModel set, return immediately        (provenance: "override")
2. User config         → if userModel set, return immediately              (provenance: "override")
3. Category default    → fuzzy-match or provider-presence check           (provenance: "category-default")
4. User fallback_models → per-agent user-configured strings/objects         (provenance: "provider-fallback")
5. Hardcoded fallback chain (the FallbackEntry[] in CATEGORY_MODEL_REQUIREMENTS)  (provenance: "provider-fallback")
6. System default      → final safety net                                  (provenance: "system-default")
```

Steps 4 and 5 share the same iteration logic: for each `FallbackEntry`, for each provider, build `provider/model`, `transformModelForProvider(provider, model)` (handles Claude date suffixes, GPT `-mini-fast` aliases, etc. — `packages/model-core/src/provider-model-id-transform.ts`), and check membership in the `availableModels` set via `fuzzyMatchModel()` (`packages/model-core/src/model-availability.ts`). First match wins; its `variant` and `reasoningEffort` flow through.

Steps 3-5 branch on whether `availableModels` is populated or empty:
- **If populated** (the harness already enumerated models via `opencode models`): exact-fuzzy match against the set.
- **If empty** (first run, no cache): fall back to a connected-providers cache (`packages/model-core/src/connected-providers-cache.ts`). If the cache says provider X is connected, trust that the chain entry for X is reachable without re-checking.

This is the runtime picture summarized in `docs/guide/agent-model-matching.md:393-407` ("Resolution pipeline").

### 3c. Source pointers (where to look)

| Concern | File | Lines |
|---|---|---|
| Category-to-chain data | `packages/model-core/src/model-requirements.ts` | 209-354 |
| Re-export shim in main src | `src/shared/model-requirements.ts` | 1-8 |
| Pipeline (the actual logic) | `packages/model-core/src/model-resolution-pipeline.ts` | 65-200 |
| Pipeline wrapper | `src/shared/model-resolution-pipeline.ts` | 11-21 |
| Per-call category config merge | `src/tools/delegate-task/categories.ts` | 17-72 |
| Category metadata (model, prompt, description) | `src/tools/delegate-task/builtin-categories.ts` → `openai-categories.ts`, `google-categories.ts`, `anthropic-categories.ts`, `kimi-categories.ts` | varies |
| Orchestrator/plan-system-prompt injection | `src/tools/delegate-task/constants.ts` | `buildPlanAgentSkillsSection` |
| Capability data (for fuzzy match) | `packages/model-core/src/model-availability.ts`, `models.dev` catalogue | — |

---

## 4. Fallback chains (what happens when the top model is unavailable)

Two distinct fallback systems, called out explicitly in `docs/guide/agent-model-matching.md:209-210`:

- **model-fallback** — proactive, hardcoded chains in `AGENT_MODEL_REQUIREMENTS` and `CATEGORY_MODEL_REQUIREMENTS`. Tried by the pipeline before the call.
- **runtime-fallback** — reactive, recovers from `session.error` after a call has already failed. Per-category/agent, configurable per user.

The model-fallback chain for a single category looks like a list of `FallbackEntry` objects (`packages/model-core/src/model-requirements.ts:1-13`):

```ts
type FallbackEntry = {
  providers: string[];   // Try each in order; first connected wins
  model: string;         // Short model id, no provider prefix
  variant?: string;      // Entry-specific (e.g. "xhigh", "max", "medium")
  reasoningEffort?: string;
  temperature?: number;
  top_p?: number;
  maxTokens?: number;
  thinking?: { type: "enabled" | "disabled"; budgetTokens?: number };
};
```

### Concrete example: `deep` (`packages/model-core/src/model-requirements.ts:271-285`)

```
1. openai | github-copilot | venice | opencode | vercel   / gpt-5.5        variant=medium
2. anthropic | github-copilot | opencode | vercel         / claude-opus-4-7 variant=max
3. google | github-copilot | opencode | vercel            / gemini-3.1-pro variant=high
4. opencode-go | vercel                                   / kimi-k2.6
5. opencode-go | vercel                                   / glm-5.1
```

The chain is **family-diverse on purpose** (GPT → Claude → Gemini → OpenCode-Go Kimi/GLM). If you lose all top-tier providers, the chain degrades into the $10/mo OpenCode-Go utility tier (Kimi K2.6, GLM-5.1) before the system-default safety net.

### Concrete example: `visual-engineering` (`packages/model-core/src/model-requirements.ts:233-246`)

```
1. google | github-copilot | opencode | vercel   / gemini-3.1-pro  variant=high
2. zai-coding-plan | opencode | bailian-coding-plan | vercel / glm-5
3. anthropic | github-copilot | opencode | vercel / claude-opus-4-7 variant=max
4. opencode-go | vercel                          / glm-5.1
5. kimi-for-coding                               / k2p5
```

Note the family preference: Gemini is the *native* choice for visual reasoning. Claude Opus is only the 3rd fallback. The doc warns explicitly: *"`visual-engineering` → Kimi/GLM: wrong reasoning style, use Qwen if Gemini is unavailable, not Claude-likes"* — but the hardcoded chain still includes GLM, because it's the pragmatic cross-provider safety net (`docs/guide/agent-model-matching.md:435-449`).

### Concrete example: `quick` (`packages/model-core/src/model-requirements.ts:316-330`)

```
1. openai | github-copilot | opencode | vercel   / gpt-5.4-mini
2. anthropic | github-copilot | vercel           / claude-haiku-4-5
3. google | github-copilot | opencode | vercel   / gemini-3-flash
4. opencode-go | vercel                          / minimax-m3
5. minimax-coding-plan | minimax-cn-coding-plan  / MiniMax-M3
6. opencode-go | vercel                          / minimax-m2.7
7. opencode | vercel                              / gpt-5-nano
```

The `quick` chain ends in `gpt-5-nano` — a deliberately-ultra-cheap final stop. There is no Opus in this chain by design (see dangerous-override section below).

### `requiresProvider` hard gate

A handful of agents (not categories, but instructive) set `requiresProvider` on their `ModelRequirement` (`packages/model-core/src/model-requirements.ts:67-71`):

```ts
hephaestus: {
  fallbackChain: [ { providers: ["openai", ...], model: "gpt-5.5", variant: "medium" } ],
  requiresProvider: ["openai", "github-copilot", "venice", "opencode", "vercel"],
}
```

When `requiresProvider` is set and **none** of the listed providers is connected, the agent is skipped entirely. This is the most aggressive form of "you don't have what this needs" — it's enforced in `packages/model-core/src/model-requirements.ts` consumer code (I did not read every consumer; the field's contract is documented in the `ModelRequirement` type at line 14). **Honest gap: I did not find an equivalent `requiresProvider` on any built-in category in `CATEGORY_MODEL_REQUIREMENTS`.** Categories can be opted out by the user (`disable: true`) but do not hard-gate on provider presence.

---

## 5. Dangerous-override detection

**Honest answer: there is no runtime code that flags "this model choice is bad for this category."** All "safe vs dangerous" guidance is **documentation**, not enforcement. It lives in `docs/guide/agent-model-matching.md:424-449`:

> **Safe** — same personality type:
> - Sisyphus: Opus → Sonnet, Kimi K2.5/2.6, GLM 5 (all communicative models)
> - Prometheus: Opus → GPT-5.5 (auto-switches to the GPT prompt)
> - Atlas: Claude Sonnet 4.6 → Kimi K2.6 → GPT-5.5 (auto-switches to the GPT prompt)
>
> **Dangerous** — personality mismatch:
> - **Sisyphus → older GPT models**: still a bad fit. GPT-5.4 and GPT-5.5 are the only dedicated GPT prompt paths.
> - **Hephaestus → Claude**: built for Codex's autonomous style. Claude can't replicate this.
> - **Hephaestus → MiniMax**: MiniMax loses coherence on multi-step deep work. **Never do this.**
> - **Oracle → MiniMax**: same reason. Oracle needs sustained reasoning; MiniMax drifts.
> - **Explore → Opus**: massive cost waste. Explore needs speed, not intelligence.
> - **Librarian → Opus**: same. Doc search doesn't need Opus-level reasoning.
> - **`visual-engineering` → Kimi/GLM**: wrong reasoning style. Use Qwen if Gemini is unavailable, not Claude-likes.

The nearest thing to a code-level guardrail is `bunx oh-my-opencode doctor` (mentioned in `docs/guide/agent-model-matching.md:155-164`), which prints the *effective* model for each agent/category and surfaces the literal string `"system-default"` when a chain has no reachable entry — a hint to the user that their setup is incomplete, but not a "danger" verdict on a configured override.

The closest runtime check I found is `resolveCategoryConfig` (`src/tools/delegate-task/categories.ts:42-48`) honoring `requiresModel` — if a category declares "I cannot function without model X" and X is not available, the category silently returns `null` rather than falling back to a "dangerous" substitute. This is *correctness*-gating, not *quality*-gating.

There is no `dangerous: true` flag, no warning emit, no UI banner when a user configures a known-bad model for a known-bad category. The maintainer's stance (per the doc) is "the docs are the warning; the user is responsible."

---

## 6. Cost tiers (deliberate tiers, not an accident)

The 8 built-in categories map cleanly onto 4 cost tiers. This is intentional — the doc calls out "speed over intelligence" for utility categories and "we burn more on the deep ones" implicitly through the variant field.

| Tier | Categories | Top-of-chain | Variant |
|------|------------|--------------|---------|
| **T0 (highest)** | `ultrabrain` | `gpt-5.5` | `xhigh` |
| **T1 (high)** | `deep`, `unspecified-high` | `gpt-5.5` (medium) / `claude-opus-4-7` (max) | `medium`/`max` |
| **T2 (mid)** | `visual-engineering`, `artistry`, `unspecified-low` | `gemini-3.1-pro` (high) / `claude-sonnet-4-6` | `high`/(none) |
| **T3 (low)** | `writing` | `gemini-3-flash` | (none) |
| **T4 (lowest)** | `quick` | `gpt-5.4-mini` | (none) |

The `quick` tier is doubly defended against cost creep: (a) the chain's last stop is `gpt-5-nano`, and (b) its prompt-append (`src/tools/delegate-task/openai-categories.ts:54-83`) explicitly warns the calling orchestrator that the model is "smaller/faster" and demands **exhaustively explicit** task prompts with MUST DO / MUST NOT DO / EXPECTED OUTPUT structure. The "you're getting a small model, behave accordingly" message is hardcoded into the system prompt — a neat trick.

The `unspecified-high` / `unspecified-low` split is the escape hatch: when the orchestrator doesn't recognize a category, it gets a *known* high or low model rather than failing. This makes the system more graceful but also means "fall-through" work hits Claude Opus, which is the most expensive possible default. A user worried about cost should configure explicit categories for everything they delegate, or override `unspecified-high` to a cheaper model in `oh-my-openagent.json`.

### Cross-tier model migration advice (from the doc)

`docs/guide/agent-model-matching.md:266-275` ("Cheat Sheet") — the maintainer's sanctioned substitution matrix:

```
If you lose...        → Swap to (in order)                  → Avoid
Claude Opus/Sonnet    → Kimi K2.5/K2.6 → GLM 5 → Big Pickle → Older GPT models
GPT-5.4/5.5           → GPT-5.5 Codex → DeepSeek v3.2       → MiniMax (except utility)
Gemini 3.1 Pro        → Qwen 3.6-plus / 3.5-plus            → Claude/Kimi (wrong style)
Grok Code Fast 1      → GPT-5.4 Mini Fast → MiniMax M2.7    → Opus (massive cost waste)
```

This is "what to do when the chain exhausts" — i.e. what *you* should put in `fallback_models` if you want to extend the built-in chain.

---

## 7. Adoption takeaways (for the user's question)

Things that make this pattern attractive to copy:

- **Decoupled intent ↔ model.** A `task(category="deep", …)` in the orchestrator code survives a provider switch. The fallback chain absorbs provider outages transparently.
- **Per-category prompt-append.** Categories carry both model + system-prompt shape, so swapping Claude for GPT in `deep` also auto-loads the GPT-tuned deep prompt (`resolveDeepCategoryPromptAppend`).
- **Defensive layering.** Each `FallbackEntry` lists multiple providers for the same model id (e.g. `["openai","github-copilot","opencode","vercel"]` for gpt-5.5) — one provider outage doesn't break the category.
- **User override with a single line** (`categories: { "deep": { "model": "..." } }` in `oh-my-openagent.json`).
- **`disable: true` per category** — opt out cleanly without forking.

Things to be wary of when copying the pattern:

- The "dangerous override" detection is **documentation-only**. If you adopt this, decide whether you want a hard block, a warning, or a docs-only approach. Each has different support costs.
- **The category string is load-bearing.** `quick-rust`, `quick-zig`, `git` show up in the orchestration doc but not in the source `CATEGORY_MODEL_REQUIREMENTS` I read. Either the docs are stale or the strings are project-injected. **Honest gap: I could not fully resolve this in a web-only survey — would need to grep the repo locally to confirm.**
- **`requiresProvider` on agents is a hard gate** (Hephaestus cannot activate without GPT access). The pattern works for "I cannot function without X" but feels too brittle to use for "I'd rather not function without X." If you copy this, distinguish the two.
- **The "available models" set is sometimes empty on first run** — the pipeline then falls back to a connected-providers cache. This is a warm-up tax; a first-call latency spike is possible. Plan a doctor/refresh command.
- **Cost tiers are baked into category names, not separated.** You can't say "use a mid-tier `deep`" without renaming or forking. If you want tunable cost, add a `tier` field to your categories rather than encoding tier in the name.

---

## 8. Gaps I could not close (web-only survey)

- Did not confirm whether `quick-rust`, `quick-zig`, `git` are real built-in categories, project-injected, or stale doc text. The orchestration doc lists them; `CATEGORY_MODEL_REQUIREMENTS` does not.
- Did not read `src/agents/dynamic-agent-prompt-builder.ts` (referenced by `builtin-categories.ts`) to see how `AvailableCategory` is computed at runtime.
- Did not read `runtime-fallback` hook code; the docs reference it but the chain shape and config schema are not in the files I fetched.
- Did not read `packages/model-core/src/connected-providers-cache.ts` in full — relied on type + call-site inference.
- Did not read `transformModelForProvider` implementation — only its signature and one or two call sites.

A local clone + `rg` pass would close all of these in under an hour.

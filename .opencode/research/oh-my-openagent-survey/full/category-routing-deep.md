# Category-Based Model Routing in oh-my-openagent — Deep Survey

**Source:** https://github.com/code-yeongyu/oh-my-openagent (branch: `dev`, fetched 2026-06-05)
**Builds on:** `category-routing.md` (light survey, 264 lines)
**Method:** webfetch on raw source files at `dev` HEAD + GitHub UI tree listings. No local clone. All paths and line numbers refer to the `dev` branch as it stood on fetch day.
**Scope:** Closes the three open "honest gaps" from the light survey, adds the per-category prompt-append behavior, the reactive runtime-fallback system, design rationale, `requiresProvider` enforcement, and cross-references to team_mode / notepads / the plan lifecycle.

---

## 0. Status of the three honest gaps from the light survey

| Gap | Status |
|-----|--------|
| `quick-rust` / `quick-zig` / `git` category strings | **Closed.** They are **not** in any of the four built-in `*-categories.ts` files. They are listed in `docs/guide/orchestration.md` as "user-facing orchestration names" with a note that "projects/users can extend categories via config; additional category names may appear in your session prompt." They are project-injected categories, not built-in. See §6 below. |
| Runtime-fallback hook code | **Closed.** It is a full subdirectory at `src/hooks/runtime-fallback/` with 30+ files. The reactive system is more elaborate than the proactive `model-fallback` chain. See §5 below. |
| `transformModelForProvider` implementation | **Closed.** It is at `packages/model-core/src/provider-model-id-transform.ts` and handles Claude date-suffix renames, GPT `-mini-fast` aliases, and Gemini preview-suffix reformatting on a per-provider basis. See §4 below. |

---

## 1. Reference table — all 8 built-in categories (default model + complete fallback chain + prompt-append summary)

This is the single source-of-truth table for the 8 categories in `CATEGORY_MODEL_REQUIREMENTS` (`packages/model-core/src/model-requirements.ts:209-354`). The "Default model" column is the value from the matching `*-categories.ts` definition (e.g. `visual-engineering` in `google-categories.ts`). Variant comes from `CATEGORY_MODEL_REQUIREMENTS.fallbackChain[0].variant` unless otherwise noted.

| # | Category | Default model + variant | Prompt-append family | Fallback chain (priority order) | Prompt-append resolver |
|---|----------|-------------------------|----------------------|----------------------------------|-------------------------|
| 1 | `visual-engineering` | `google/gemini-3.1-pro` (high) | `VISUAL_CATEGORY_PROMPT_APPEND` (Google) | gemini-3.1-pro high → `zai/opencode/bailian/vercel glm-5` → `anthropic/github-copilot/opencode/vercel claude-opus-4-7 max` → `opencode-go/vercel glm-5.1` → `kimi-for-coding k2p5` | static |
| 2 | `ultrabrain` | `openai/gpt-5.5` (xhigh) | `ULTRABRAIN_CATEGORY_PROMPT_APPEND` (OpenAI) | gpt-5.5 xhigh → gemini-3.1-pro high → claude-opus-4-7 max → `opencode-go/vercel glm-5.1` | static |
| 3 | `deep` | `openai/gpt-5.5` (medium) | `DEEP_CATEGORY_PROMPT_APPEND` (OpenAI, default) or `DEEP_CATEGORY_PROMPT_APPEND_GPT_5_5` (when resolved model is GPT-5.5) | gpt-5.5 medium → claude-opus-4-7 max → gemini-3.1-pro high → `opencode-go/vercel kimi-k2.6` → `opencode-go/vercel glm-5.1` | **dynamic** (`resolveDeepCategoryPromptAppend` at `openai-categories.ts:79-83`) |
| 4 | `artistry` | `google/gemini-3.1-pro` (high) | `ARTISTRY_CATEGORY_PROMPT_APPEND` (Google) | gemini-3.1-pro high → claude-opus-4-7 max → gpt-5.5 → `opencode-go/vercel kimi-k2.6` → `opencode-go/vercel glm-5.1` | static |
| 5 | `quick` | `openai/gpt-5.4-mini` (no variant) | `QUICK_CATEGORY_PROMPT_APPEND` (OpenAI, contains `<Caller_Warning>` block) | gpt-5.4-mini → `anthropic/github-copilot/vercel claude-haiku-4-5` → `google/github-copilot/opencode/vercel gemini-3-flash` → `opencode-go/vercel minimax-m3` → `minimax-coding-plan/minimax-cn-coding-plan MiniMax-M3` → `opencode-go/vercel minimax-m2.7` → `opencode/vercel gpt-5-nano` | static |
| 6 | `unspecified-low` | `anthropic/claude-sonnet-4-6` (no variant) | `UNSPECIFIED_LOW_CATEGORY_PROMPT_APPEND` (Anthropic, contains `<Selection_Gate>` and `<Caller_Warning>`) | claude-sonnet-4-6 → gpt-5.5 medium → `opencode-go/vercel kimi-k2.6` → gemini-3-flash → `opencode-go/vercel minimax-m3` → `MiniMax-M3` → `opencode-go/vercel minimax-m2.7` | static |
| 7 | `unspecified-high` | `anthropic/claude-opus-4-7` (max) | `UNSPECIFIED_HIGH_CATEGORY_PROMPT_APPEND` (Anthropic, contains `<Selection_Gate>`) | claude-opus-4-7 max → gpt-5.5 high → `zai/opencode/bailian/vercel glm-5` → `kimi-for-coding k2p5` → `opencode-go/vercel glm-5.1` → `opencode/bailian/vercel kimi-k2.5` → moonshotai family kimi-k2.5 | static |
| 8 | `writing` | `kimi-for-coding/k2p5` (no variant) | `WRITING_CATEGORY_PROMPT_APPEND` (Kimi, contains explicit anti-AI-slop rules) | gemini-3-flash → `opencode-go/vercel kimi-k2.6` → claude-sonnet-4-6 → `opencode-go/vercel minimax-m3` → `MiniMax-M3` → `opencode-go/vercel minimax-m2.7` | static |

**A small but important discrepancy worth noting.** The `writing` category's `DEFAULT_CATEGORIES` entry points to `kimi-for-coding/k2p5` (`kimi-categories.ts`), but `CATEGORY_MODEL_REQUIREMENTS.writing[0]` is `google/gemini-3-flash`. In practice the category config (`kimi-for-coding/k2p5`) is what `resolveCategoryConfig` returns as `defaultConfig.model`; the `fallbackChain[0]` is what the `resolveModelPipeline` walks when the resolved model is unavailable. The two disagree on the *primary* model — the fallback chain considers Gemini the primary, but the category config considers Kimi. This is consistent with the doc note "Vercel AI Gateway fallback coverage" being universal: the chain entry can effectively be a *fallback* on the config default. Not a bug, but a subtlety.

**`unspecified-low` / `unspecified-high` resolution order.** When the orchestrator (Prometheus) generates a plan and the planner agent picks a category for a task, the plan-system-prompt (`constants.ts`) injects a category table from `CATEGORY_DESCRIPTIONS` and instructs the planner to pick a *named* category when one applies. `unspecified-*` is the catch-all bucket; `unspecified-high` maps to the most expensive default (Opus max), which is a *deliberate* safety net (see §6 design rationale).

---

## 2. The 6-step priority chain — full detail

The pipeline lives in `packages/model-core/src/model-resolution-pipeline.ts:65-200` (`resolveModelPipeline`). The function has one early exit per step:

```
Step 1: UI selection      → uiSelectedModel                (provenance: "override")
Step 2: User config       → userModel                      (provenance: "override")
Step 3: Category default  → categoryDefaultModel           (provenance: "category-default")
Step 4: User fallback_models → userFallbackModels          (provenance: "provider-fallback")
Step 5: Hardcoded fallback chain (CATEGORY_MODEL_REQUIREMENTS) (provenance: "provider-fallback")
Step 6: System default    → systemDefaultModel             (provenance: "system-default")
```

### 2.1 Why six steps (and not fewer)

Each step handles a distinct layer of user/system authority. The order is: **user-explicit → user-inherited → category semantic → user safety net → system safety net → ultimate floor.**

* Steps 1-2 are *user intent*. If the user said "use this model" via UI or config, honor it. No fallback. This is the contract.
* Step 3 is the *category semantic*. If the user said nothing about *this* call but the category itself has a default, that's the answer. This is the *intent* the agent (Sisyphus, Atlas) was encoding by choosing a category name.
* Step 4 is the *user's safety net*. Before the hardcoded chain, walk anything the user put in `categories[name].fallback_models` or `agents[name].fallback_models`. This is the override seam for "I trust the system less than I trust my own list."
* Step 5 is the *hardcoded chain*. This is what the user gets if they did nothing. The whole point of the system.
* Step 6 is the *ultimate floor*. If even the chain failed, fall through to whatever OpenCode has as its own default. The system never *fails* the call; it picks the least-bad answer.

The provenance string flows back to the call site, which surfaces in `bunx oh-my-opencode doctor` and the TUI toast (e.g. a model resolved via Step 3 shows `category-default`; via Step 5 shows `provider-fallback`).

### 2.2 The two-mode split (available-set empty vs populated)

Steps 3-5 each branch on `availableModels.size > 0`:

* **Populated set** (the harness already ran `opencode models`): fuzzy-match against the set. Fuzzy match is a normalized substring match in `packages/model-core/src/model-availability.ts:5-37` (`fuzzyMatchModel`): it lowercases, normalizes Claude `4-6` ↔ `4.6` and `4-7` ↔ `4.7` separators (`normalizeModelName`), then does `String.includes(targetNormalized)`. If multiple candidates match, prefer the shortest (i.e. the most specific / least-suffixed id).
* **Empty set** (first run, no cache): read the connected-providers cache via `providerCache.readConnectedProvidersCache()` (`packages/model-core/src/connected-providers-cache.ts:21`). The interface in `model-core` is a stub; the real implementation lives in `src/shared/connected-providers-cache.ts` and is wired in by the consumer. If the cache exists, treat any chain entry whose `providers` overlap the connected set as "reachable." This is the warm-up tax: the first call after auth may not be as deterministic as later calls.

This two-mode design is what makes the system survive the cold-start problem. A new install has no `availableModels` set; the connected-providers cache is the alternative source of truth until `opencode models` runs.

### 2.3 Cross-provider fuzzy match (a hidden safety net)

Step 5 has a subtle second sub-loop: for each `FallbackEntry`, after iterating `entry.providers` and trying each with a hint-scoped `fuzzyMatchModel(fullModel, available, [provider])`, it also calls `fuzzyMatchModel(entry.model, available)` *without* a provider hint. This is the "cross-provider fuzzy match" — if the configured providers are wrong but the model id is generic enough (e.g. `gpt-5-nano`) to match in another provider's namespace, it still resolves. This is what makes `opencode/vercel gpt-5-nano` work even when no chain entry said `opencode` for it.

### 2.4 `resolveCategoryExecution` is the consumer in `src/`

`src/tools/delegate-task/category-resolver.ts:38-238` is the higher-level wrapper that turns `task(category="…")` into a complete Sisyphus-Junior config. It calls `resolveCategoryConfig` for the model + prompt-append (`categories.ts:17-72`), then `resolveModelForDelegateTask` (`model-selection.ts:62-213`) for the full resolution. The latter is a re-implementation of the pipeline (six steps) tuned for the delegate-task call site. It also adds a `skipped: true` return for the cold-cache pre-warm path, so the orchestrator can still kick off a session that OpenCode will handle with its own system default if no model metadata is cached yet (`model-selection.ts:96-104`).

The category-resolver also handles the `sisyphus_junior.model` global override: it sets `overrideModel = sisyphusJuniorModel` and uses it as the user model. **Precedence at the delegate-task site is: explicit category `model` > sisyphus-junior `model` > category resolved model** (`category-resolver.ts:111`). This is the inverse of the doc example in `agent-model-matching.md` — the per-category override beats the global junior override, which beats the category's own chain.

---

## 3. `transformModelForProvider` — full implementation

`packages/model-core/src/provider-model-id-transform.ts:43-89`. Single export, 24 lines, three branches by provider:

```ts
export function transformModelForProvider(provider: string, model: string): string {
  return transformModelForProviderUsingAnthropicBehavior(provider, model)
}
```

The "Anthropic behavior" name is from when the function was first added for Anthropic's quirks. It has since accreted provider-specific transformations:

| Provider | Transformation |
|----------|---------------|
| `vercel` | If `model` is `"sub/model"`, infer sub-provider from the prefix and apply gateway transforms to the model id. Gateway transforms: `claudeVersionDot` (rewrite `claude-{family}-{N}-{M}` → `claude-{family}-{N}.{M}`, which the Anthropic API rejects the un-dotted form for) and `GEMINI_31_PRO_PREVIEW` (rewrite `gemini-3.1-pro` → `gemini-3.1-pro-preview`, which is the only id the API accepts for that model). |
| `github-copilot` | Apply `claudeVersionDot` + `GEMINI_31_PRO_PREVIEW` + `GEMINI_3_FLASH_PREVIEW` (rewrites `gemini-3-flash` → `gemini-3-flash-preview`). GitHub Copilot exposes only preview ids for these models. |
| `google` | Apply `GEMINI_31_PRO_PREVIEW` + `GEMINI_3_FLASH_PREVIEW`. Native Google API expects the `-preview` suffix. |
| `anthropic` | Return the model id as-is. Anthropic accepts both dotted and dash forms. |
| anything else | Return as-is. |

`inferSubProvider` (lines 1-9) is the heuristic for the `vercel` branch when the model string is bare (no `sub/`): prefixes `claude-` → `anthropic`, `gpt-` → `openai`, `gemini-` → `google`, `grok-` → `xai`, `minimax-` → `minimax`, `kimi-` → `moonshotai`, `glm-` → `zai`.

**Why this matters.** The hardcoded chains list model ids in the "modern" form (`gemini-3.1-pro`, `claude-opus-4-7`) but each provider has its own canonical id form. Without this function, the fuzzy match in Step 5 would silently miss every cross-provider fallback. With it, the *configured* id is rewritten into the *provider-expected* id before fuzzy-matching, so the available-set check actually works.

`transformModelForProviderDisplay` is a duplicate export for the TUI surface — same behavior, different name to make the call site self-documenting.

The pipeline (line 105-110, 133-138, 169-174) calls it for every `FallbackEntry` lookup that uses a `connectedProviders` cache; when the `availableModels` set is populated, the fuzzy match handles the rewrite implicitly because the set is already in provider-canonical form.

---

## 4. Per-category prompt-append behavior (the *other* half of the category contract)

A category is not just a model. It is `model + variant + prompt_append`. Each category carries a system-prompt fragment that is appended to the subagent's system prompt when the category is selected. The fragments are in `src/tools/delegate-task/{openai,anthropic,google,kimi}-categories.ts` and are aggregated by `builtin-categories.ts:8-31` into three maps: `DEFAULT_CATEGORIES`, `CATEGORY_PROMPT_APPENDS`, `CATEGORY_DESCRIPTIONS`, plus an optional `CATEGORY_PROMPT_APPEND_RESOLVERS` map for dynamic resolution.

### 4.1 The 8 static prompt-append blocks

Each `*-categories.ts` file exports an array of `BuiltinCategoryDefinition` objects with `{ name, config, description, promptAppend }`. Highlights (full text is in source; paraphrased summaries here):

| Category | Source file | Prompt-append effect |
|----------|-------------|----------------------|
| `ultrabrain` | `openai-categories.ts:5-32` | Sets strategic-advisor mode: "least complex solution," "leverage existing code," "one clear recommendation with effort estimate (Quick/Short/Medium/Large)." Mandates 3-section response: bottom line, action plan, risks. |
| `deep` (default) | `openai-categories.ts:34-54` | Goal-oriented autonomous mode. 5-15 min silent exploration is *normal*. Goal + numbered phases = ONE atomic task; refuse if the "phases" are actually separate independent tasks. |
| `deep` (GPT-5.5) | `openai-categories.ts:56-100` | **Replaces** the default when the resolved model is GPT-5.5 (dynamic). More aggressive: "ambition scaled to context," "no 'simplified version' deliveries," sparse status cadence, root-cause bias. |
| `quick` | `openai-categories.ts:102-160` | Embeds a `<Caller_Warning>` block warning the calling orchestrator that the model is `gpt-5.4-mini` (small/fast) and demanding MUST DO / MUST NOT DO / EXPECTED OUTPUT structure. The warning is *for the caller*, not the callee. |
| `unspecified-low` | `anthropic-categories.ts:4-26` | Embeds a `<Selection_Gate>`: the caller must verify the task does NOT fit a named category before picking this one. Plus a mid-tier warning to write explicit MUST DO / MUST NOT DO / EXPECTED OUTPUT. |
| `unspecified-high` | `anthropic-categories.ts:28-50` | Same `<Selection_Gate>` pattern; warns that the model is Opus (expensive) and that the task must be genuinely unclassifiable AND high-effort. |
| `visual-engineering` | `google-categories.ts:1-78` | The most aggressive: `<DESIGN_SYSTEM_WORKFLOW_MANDATE>` with 4 phases. Phase 1: read 5-10 existing components before writing a line. Phase 2: build a design system if none exists. Phase 3: extend the system before using. Phase 4: verify no hardcoded magic numbers. |
| `artistry` | `google-categories.ts:80-97` | Creative-genius mode: push boundaries, embrace ambiguity, wild experimentation, balance novelty with coherence. |
| `writing` | `kimi-categories.ts:3-29` | The "anti-AI-slop" rules: no em dashes, no "delve" / "leverage" / "utilize" / "in order to," contractions required, no filler openings. Vivid plain-prose emphasis. |

### 4.2 The dynamic resolver (`deep` only)

`openai-categories.ts:79-83`:
```ts
export function resolveDeepCategoryPromptAppend(model: string | undefined): string {
  if (model && isGpt5_5Model(model)) {
    return DEEP_CATEGORY_PROMPT_APPEND_GPT_5_5
  }
  return DEEP_CATEGORY_PROMPT_APPEND
}
```

`isGpt5_5Model` is a small helper in `src/agents/types.ts` that pattern-matches `gpt-5.5` and `gpt-5.5-codex` (and the occasional `gpt-5.5-mini` if it appears). When the resolved model is GPT-5.5, the *more aggressive* deep prompt is used. This is the only category with model-conditional prompt behavior — the maintainer's call that "deep on GPT-5.5" is a meaningfully different operating mode than "deep on Sonnet" (the original Anthropic target).

The resolution wiring is in `category-resolver.ts:13-22` (`resolveCategoryPromptAppendForModel`):
```ts
function resolveCategoryPromptAppendForModel(
  categoryName, actualModel, staticPromptAppend, userPromptAppend,
) {
  const dynamicResolver = CATEGORY_PROMPT_APPEND_RESOLVERS[categoryName]
  if (!dynamicResolver) {
    return staticPromptAppend || undefined
  }
  const dynamicBase = dynamicResolver(actualModel)
  if (!userPromptAppend) {
    return dynamicBase || undefined
  }
  return dynamicBase ? `${dynamicBase}\n\n${userPromptAppend}` : userPromptAppend
}
```

The user's `categories[name].prompt_append` (file path or text) is appended *after* the static/dynamic base, separated by `\n\n`. This is how a user injects extra guidance without forking.

### 4.3 How the prompt flows out

`category-resolver.ts:198-205` returns `categoryPromptAppend` in the `CategoryResolutionResult`. The Sisyphus-Junior agent that gets invoked (the worker) sees:

```
<base Sisyphus-Junior system prompt>
... existing rules ...
<category_Context block from the prompt append>
<caller's prompt_append if any>
```

The `<Category_Context>` wrapper is the convention; categories frame their content in `<Category_Context name="…">` so the model can self-locate when it sees its own messages in a session log.

### 4.4 The `quick` `<Caller_Warning>` is special

Most prompt-append blocks speak to the *callee* (the subagent). `quick` and `unspecified-low` add a `<Caller_Warning>` block that speaks to the *caller* (the orchestrator that will issue the next `task(category="quick", ...)` call). The text reads like a prompt-engineering manual: "Your prompt MUST be exhaustively explicit." This is the system teaching the caller how to write for a small model — a clever way to push prompt-quality responsibility back to the orchestrator without runtime enforcement.

---

## 5. Runtime-fallback — the reactive system

The proactive fallback chain (Steps 1-6 above) runs *before* the call. If a call is issued and the model then errors at runtime (rate limit, 5xx, quota exceeded, model_not_found), a separate **reactive** system kicks in: `src/hooks/runtime-fallback/`.

### 5.1 Architecture

A chat-message lifecycle hook (`createRuntimeFallbackHook` in `src/hooks/runtime-fallback/hook.ts:38-114`) attaches to `event` and `chat.message` events on the OpenCode server. State is kept in `HookDeps` (`types.ts`): per-session maps for `sessionStates`, `sessionRetryInFlight`, `sessionAwaitingFallbackResult`, `sessionFallbackTimeouts`. A 5-minute interval (`setInterval` at 300_000 ms) cleans up stale sessions older than 30 minutes.

The flow when a model errors:

1. `error-classifier.ts` (`isRetryableError`) classifies the error. It supports:
   - **Status code match** (e.g. 429, 500, 502, 503, 504 — from `runtime_fallback.retry_on_errors`, default `[429, 500, 502, 503, 504]`).
   - **Error type match** (`missing_api_key`, `invalid_api_key`, `model_not_found`, `quota_exceeded`). Quota-exceeded is retryable — the system falls through to a different model rather than stopping.
   - **Message regex match** against `RETRYABLE_ERROR_PATTERNS` in `constants.ts:18-41` (covers "rate limit", "quota", "overloaded", "temporarily unavailable", and several Chinese-localized patterns like `使用上限`, `频率限制`).
2. If retryable, `auto-retry.ts:62-100` (`abortSessionRequest`) cancels the in-flight session and `scheduleSessionFallbackTimeout` ensures the session gets a fresh retry.
3. `fallback-state.ts` (`prepareFallback`) advances `state.fallbackIndex`, marks the failed model as failed with a `cooldown_seconds` (default 60) window, and picks the next available model.
4. `auto-retry.ts:175-260` (`autoRetryWithFallback`) reads the session's last user message, reconstructs the parts, builds a fresh retry payload, and dispatches the prompt with the new model.
5. `retry-model-payload.ts` builds the new `{ providerID, modelID, variant? }` — variant is inherited from `agentSettings.variant` or `agentSettings.reasoningEffort` (fixed in PR #2622 / #2663 after the `fallback models lose variant and reasoningEffort` bug report).

### 5.2 Where the fallback list comes from

`fallback-models.ts:18-36` (`getFallbackModelsForSession`):

```
1. If the session has a registered category (SessionCategoryRegistry.get(sessionID))
   AND userConfig.categories[thatCategory].fallback_models is set → use it.
2. Else if pluginConfig.agents[agentName].fallback_models is set → use it.
3. Else if pluginConfig.agents[agentName].category → use categories[category].fallback_models.
4. Else → undefined (no runtime fallback list; rely on hardcoded chain only).
```

So the user's `fallback_models` config serves *both* the proactive (Step 4 in §2) and the reactive system. Single source of truth.

### 5.3 Cooldown & equivalence

`fallback-state.ts:73-82` (`isModelInCooldown`) keeps a 60-second window per failed model. `isEquivalentModel` (lines 38-57) normalizes both candidates and current to `{providerID, modelID}` with variant-normalized form: `claude-opus-4-7-thinking`, `claude-opus-4-7-max`, `claude-opus-4-7-high` all canonicalize to the same `claude-opus-4-7` (line 14-22). This prevents the system from "falling back" to a model that's the same one with a different variant suffix.

### 5.4 First-prompt watchdog

`constants.ts:52-58` defines a 90-second first-prompt watchdog: if the session produces no text / reasoning / finish event within 90 s of dispatch, `first-prompt-watchdog.ts` treats the provider as silently stuck and triggers the same fallback machinery. Tuned to be longer than typical first-token latency but much shorter than the outer 30-minute poll timeout.

### 5.5 Quota vs. rate-limit distinction

`error-classifier.ts:142-150` explicitly maps `quota_exceeded` to *retryable* (and `model-error-classifier-openai-usage-limit` deals with OpenAI's usage-limit responses, which return *success with a special body*). The intent: when one provider says "no quota left," the system should keep going by switching models, not stop the user mid-task.

### 5.6 What the two systems look like together

`model-fallback` (proactive, in `src/hooks/model-fallback/hook.ts`) intercepts `chat.message` *before* dispatch and applies any pending fallback. `runtime-fallback` (reactive, in `src/hooks/runtime-fallback/`) intercepts `event` and *post-dispatch* errors. The two complement: proactive catches the "this model isn't connected" case before the call; reactive catches the "this model was connected but just returned 429" case after. Together they cover the full model-resolution-and-execution lifecycle.

---

## 6. Design rationale — the why

### 6.1 Why a 6-step priority chain

Because the system must honor four distinct layers of authority without ambiguity:

1. **User explicit** (Steps 1-2) — "I told you what to use."
2. **Semantic intent** (Step 3) — "I picked a category; the category has a default."
3. **User safety net** (Step 4) — "Here are *my* backups, not the maintainer's."
4. **System safety net** (Step 5) — "If nothing else worked, here's the maintainer's chain."
5. **Ultimate floor** (Step 6) — "If even the chain failed, don't fail the call."

Each step is a hard cap. A user who sets `sisyphus.model = "openai/gpt-5.5"` never gets silently downgraded to the chain — but if `gpt-5.5` is unavailable *and* the user didn't configure `fallback_models` *and* no chain entry resolves, the system still tries the system default. This is "fail soft, never refuse" engineering.

### 6.2 Why family-diverse fallbacks

Each `FallbackEntry` lists multiple providers (`["openai", "github-copilot", "opencode", "vercel"]` for `gpt-5.5`). This is not just multi-vendor pricing; it is **provider-outage defense**. If OpenAI is down, GitHub Copilot may still serve `gpt-5.5` through its enterprise agreement; if GitHub is down, the `opencode` or `vercel` AI Gateway may still route it. The chain is *defense in depth at the provider level*.

The cross-family fallbacks (e.g. `deep` chain: GPT → Claude → Gemini → OpenCode-Go Kimi/GLM) are deliberate. The maintainer's stance: "No single provider can cover everything. Anthropic-only setups break Hephaestus. OpenAI-only setups degrade Sisyphus." (`docs/guide/agent-model-matching.md`, Step 2). The chain degrades to OpenCode Go's $10/mo tier (Kimi K2.6, GLM-5.1) before the system-default safety net — i.e. when you have nothing else, you get a free-tier utility model rather than a hard failure.

The chain is **also** a *personality* hierarchy. `deep` starts with GPT (principle-driven, autonomous — what deep work needs), falls through to Claude (mechanics-driven, follows long instructions), then Gemini (different reasoning style), then Kimi/GLM (Claude-like, cheaper). Each step is "the next best at following complex deep-task prompts," not just "the next available."

### 6.3 Why dangerous-override detection is documentation-only

From `docs/guide/agent-model-matching.md` Step "Safe vs Dangerous Overrides": the maintainer documents the personality-mismatch combinations ("Hephaestus → MiniMax: never do this") but does not code-enforce them. The reason is implicit in the architecture: **a category is a *name*, not a *guarantee***. The user can override any category to any model, and the system should not block that. The maintainer's stance is "the docs are the warning; the user is responsible."

The closest code-level guardrail is `bunx oh-my-opencode doctor`, which surfaces the literal string `"system-default"` when a chain has no reachable entry — a *diagnostic* hint, not a verdict on a configured override. There is no `dangerous: true` flag, no warning emit, no UI banner.

The one enforcement that *does* exist is the `no-hephaestus-non-gpt` hook (`src/hooks/no-hephaestus-non-gpt/hook.ts`). It checks on `chat.message`: if the agent is `hephaestus` and the model is non-GPT, it shows a toast ("NEVER Use Hephaestus with Non-GPT. Hephaestus is trash without GPT. For Claude/Kimi/GLM models, always use Sisyphus.") and — if `allowNonGptModel` is not set — *redirects* the agent to Sisyphus via `input.agent = "sisyphus"`. This is the only personality-mismatch *enforcement* in the system, and it is hardcoded to Hephaestus only because Hephaestus's prompt is uniquely GPT-5.5-tuned (1,100 lines of principle-driven instructions that Claude/Kimi/GLM cannot replicate).

### 6.4 Why per-category prompt-append

Two reasons:

1. **Each model has a different operating mode.** A GPT-tuned deep prompt looks like principles and decisions; a Claude-tuned deep prompt looks like checklists and step-by-step. The category's prompt-append switches between them based on which model was resolved. This is the dynamic-resolver pattern (§4.2): `deep` switches prompt at the moment the model resolves to GPT-5.5.

2. **The caller can affect the callee's behavior without modifying agent code.** The user writes `categories.deep.prompt_append = "When implementing, always run the test suite before claiming complete."` and every `task(category="deep", …)` call now includes that guidance. The prompt-append is the user-facing extension surface for the *personality* of a category, parallel to `model` / `variant` for the *hardware*.

### 6.5 Why `requiresProvider` is a hard gate on agents but not categories

`requiresProvider: ["openai", "github-copilot", …]` is set on `hephaestus` only. The contract: if none of those providers is connected, *the agent does not activate at all* (`packages/model-core/src/model-requirements.ts:14-25` defines the field). This is the maintainer's call: "Hephaestus without GPT is *worse* than no Hephaestus" (the `no-hephaestus-non-gpt` hook's toast literally says "Hephaestus is trash without GPT"). The hard gate is *correctness-gating*: better to skip the agent than to run it broken.

Categories are different. A `quick` category that resolves to no model is still a successful category call — it surfaces as `system-default` in `doctor` and the user can see the problem. The category is the *user's* tool; it should never *silently* fail. It returns `null` from `resolveCategoryConfig` only when `requiresModel` is set (a stricter variant used for categories that hard-require one model) or when the user has `disable: true`. Built-in categories don't set `requiresModel`; it's a generic mechanism for future user-defined categories that want the strictness.

In practice the *equivalent* of `requiresProvider` for categories is the chain. If `quick` can't reach any model in its chain, the user gets the system default — a *safe* degradation. Hephaestus with Claude would not be safe (it would produce broken output), so the system refuses to run it.

---

## 7. Cross-references — how category routing interacts with the rest

### 7.1 Team mode

`team_mode` is a parallel multi-agent orchestration system (`docs/guide/team-mode.md`, v4.0+). It is **off by default**; enabled with `{ "team_mode": { "enabled": true, "max_parallel_members": 4, … } }` and unlocks 12 `team_*` tools (`team_create`, `team_send_message`, `team_task_create`, `team_status`, …).

`team-mode.md` notes that team members are *category-specialized*: "A lead agent orchestrates a team of category-specialized members, all running in parallel." This means a team is essentially a fan-out of `task(category="…")` calls with per-category member models. The same `CATEGORY_MODEL_REQUIREMENTS` chains apply, but each member is its own session with its own model.

`docs/guide/orchestration.md` notes the team-mode subagent eligibility:
* **Eligible:** sisyphus, atlas, sisyphus-junior
* **Conditional:** hephaestus (requires teammate permission enablement)
* **Hard-reject:** oracle, librarian, explore, multimodal-looker, metis, momus, prometheus

The hard-reject reasons (from the orchestration doc and `src/agents/dynamic-agent-prompt-builder.ts`): oracle is read-only, prometheus is constrained to `.omo/*.md` writes by the `prometheus-md-only` hook. Neither fits the "do work" model of a team member.

Category routing is *not* changed by team mode; categories are still resolved via `resolveCategoryExecution`, and each member inherits the chain for its assigned category. Team mode adds a coordination layer on top; it does not change the model-resolution contract.

### 7.2 Notepads

`src/hooks/sisyphus-junior-notepad/hook.ts:9-51` is a `tool.execute.before` hook that intercepts `task` calls and prepends a `NOTEPAD_DIRECTIVE` to the prompt. The check is:

1. Is the tool `task`?
2. Is the caller an orchestrator? (`isCallerOrchestrator` — checks if the calling session is sisyphus or atlas)
3. Is there a prompt to inject into?
4. Is the directive already present (double-injection guard)?

If all yes, the directive is prepended. The directive tells the Sisyphus-Junior worker to *read* `.omo/notepads/{plan-name}/` for `learnings.md`, `decisions.md`, `issues.md`, `verification.md`, and `problems.md`, and to *write back* any insights discovered. The notepad mechanism is *prompt-level*, not model-resolution-level. The category still drives the model; the notepad is a context-injection layer.

Notepads interact with category routing only in the following way: the `wisdom` from previous category-delegated tasks is passed forward to subsequent ones, *across categories*. So a `deep` task that discovers a convention in `learnings.md` makes that convention available to the next `quick` task in the same plan.

### 7.3 Plan lifecycle

The plan is created by Prometheus (`docs/guide/orchestration.md`: "Prometheus is your strategic planner"). When the user types `/start-work`, the `start-work` hook reads `.omo/boulder.json` (if present) to resume an in-progress plan, or picks the most recent `.omo/plans/*.md` to begin. Atlas then drives the plan through waves.

The plan-system-prompt (`src/tools/delegate-task/constants.ts:PLAN_AGENT_SYSTEM_PREPEND_STATIC_BEFORE_SKILLS`) *mandates* a per-task `Category: [name]` recommendation:

```
- Category: `category-name` - [reason]
- Skills: [`skill-1`, `skill-2`] - [reason each skill is needed]
```

This is injected into Prometheus's prompt by `buildPlanAgentSystemPrepend(categories, skills)` which calls `renderPlanAgentCategoryRows` to build the available-categories table. **The plan literally encodes the category choice for each task.** When Atlas dispatches the task, it calls `task(category="…", load_skills=[…])` and the routing kicks in. If Prometheus chose the wrong category, Atlas has no override path — the plan is the source of truth.

The `isPlanAgent` / `isPlanFamily` helpers (`constants.ts:217-244`) are for hook-level logic (not category routing). `COORDINATOR_AGENT_NAMES = ["prometheus"]` is the symmetric guard to a caller-eligibility check, mentioned in a comment as "PR #4065 for team_create" — i.e. you cannot `task(subagent_type="prometheus")` from another agent because prometheus is a coordinator.

### 7.4 Background tasks

`docs/guide/orchestration.md` notes background task concurrency defaults to **5**, with `defaultConcurrency` / `providerConcurrency` / `modelConcurrency` keys. Background `task(category="…", run_in_background=true)` calls go through the same `resolveCategoryExecution` path. The model-resolution does not branch on background vs sync; the only effect is concurrency.

### 7.5 Session continuity

`SessionCategoryRegistry` (`src/shared/session-category-registry.ts`, referenced in `runtime-fallback/agent-resolver.ts` and `runtime-fallback/auto-retry.ts`) is the registry that maps a session ID to the category that produced it. The `runtime-fallback` hook uses this to look up `categories[sessionCategory].fallback_models` for the reactive fallback. So when a `task(category="deep", run_in_background=true)` produces session ID `abc`, and the session errors at runtime, the hook can find the original category and use its configured fallback list.

### 7.6 `start-work` ↔ `boulder.json` ↔ category routing

`.opencode/boulder.json` is the per-plan state file (`{ active_plan, session_ids, started_at, plan_name }`). It does not store category choices — those are in the plan markdown itself. Category routing is *re-derived* on every task call by `resolveCategoryExecution`; there is no caching across plans.

---

## 8. The `requiresProvider` hard gate (Hephaestus cannot activate without GPT access)

Set in `packages/model-core/src/model-requirements.ts:67-71`:

```ts
hephaestus: {
  fallbackChain: [
    { providers: ["openai","github-copilot","venice","opencode","vercel"], model: "gpt-5.5", variant: "medium" },
  ],
  requiresProvider: ["openai","github-copilot","venice","opencode","vercel"],
}
```

The contract (`packages/model-core/src/model-requirements.ts:14-25`): when `requiresProvider` is set and *none* of the listed providers is connected, the agent is skipped entirely. This is the strongest form of "you don't have what this needs" — the agent is *not invoked* in the first place.

`hephaestus` is the only agent in `AGENT_MODEL_REQUIREMENTS` that sets `requiresProvider`. The reasoning: Hephaestus's prompt is tuned to GPT-5.5's principle-driven style ("Hephaestus is designed exclusively for GPT models. Hephaestus is trash without GPT" — `src/hooks/no-hephaestus-non-gpt/hook.ts:6-8`). Running it on Claude would produce broken output (Claude would follow the prompt but the prompt is GPT-idiomatic). Running it on MiniMax would be worse. The hard gate avoids the broken run.

The defensive hook (`no-hephaestus-non-gpt`) is the *belt-and-suspenders* companion. If somehow Hephaestus is dispatched with a non-GPT model (e.g. the user manually set `agents.hephaestus.model = "anthropic/claude-sonnet-4-6"`), the hook:
1. Shows a toast: "NEVER Use Hephaestus with Non-GPT" (10-second duration).
2. If `allowNonGptModel` is not set, *redirects* the agent to Sisyphus (sets `input.agent = "sisyphus"`, calls `updateSessionAgent(sessionID, "sisyphus")`).
3. If `allowNonGptModel` is set (an escape hatch for testing), just shows the toast as a warning.

The dual enforcement (gate + hook) means Hephaestus is *practically impossible* to run on a non-GPT model without explicitly opting in. The user has to set `allowNonGptModel` AND have a config that bypasses the gate. The doc says: "What if you have zero subscriptions? OpenCode Go alone gets Sisyphus/Atlas/Oracle/Librarian/Explore working. Hephaestus won't activate without GPT access, so you lose autonomous deep work. Consider adding ChatGPT Plus as soon as you can." (`docs/guide/agent-model-matching.md` Step 2)

**No category sets `requiresProvider`.** This is consistent with §6.5: categories are user-configurable surfaces, and the user is responsible for the consequences. Categories that need a hard requirement use `requiresModel` (a stricter single-model field) instead. None of the 8 built-in categories do.

---

## 9. Honest gap closure — the `quick-rust` / `quick-zig` / `git` categories

The orchestration doc (`docs/guide/orchestration.md`, "Delegate-Task Categories") lists:

> `task(category="...")` supports these category names in user-facing orchestration: `visual-engineering`, `artistry`, `ultrabrain`, `deep`, `quick`, `unspecified-low`, `unspecified-high`, `writing`, `quick-rust`, `quick-zig`, `git`
>
> Notes:
> - Built-in defaults are defined in `src/tools/delegate-task/*-categories.ts` and `src/shared/model-requirements.ts`
> - Projects/users can extend categories via config; additional category names may appear in your session prompt

But the four built-in `*-categories.ts` files contain only the 8 built-in categories. `quick-rust`, `quick-zig`, and `git` are **not** built-in. The most consistent reading is:

1. They are **project-injected** — the project adds a custom `src/tools/delegate-task/{project}-categories.ts` (or registers them via `oh-my-openagent.json[c]` `categories:` key) and they appear in the session prompt via the `CATEGORY_DESCRIPTIONS` table.
2. They are **stale doc text** — the maintainer lists them as "user-facing orchestration names" from older versions and hasn't pruned them.
3. They are **plan-system-prompt entries** the user can include in their project config under `categories:` without any change to the source.

Given the doc's explicit note "Projects/users can extend categories via config; additional category names may appear in your session prompt," option (1) or (3) is the intended reading. The source-of-truth behavior is:

* `resolveCategoryConfig` looks up `DEFAULT_CATEGORIES[categoryName]`. If not present, looks up `userCategories[categoryName]`. If neither, returns `null`.
* `category-resolver.ts:62-67` errors with `"Unknown category: \"<name>\". Available: <merged list>"` if neither map has the name.
* `mergeCategories` (`src/shared/merge-categories.ts`) merges `DEFAULT_CATEGORIES` with `userCategories`, so any user-defined category works as long as it's in the user's config.

So `quick-rust` works if a user has defined:
```jsonc
{
  "categories": {
    "quick-rust": { "model": "openai/gpt-5.5", "variant": "medium" }
  }
}
```

The chain behavior for user-defined categories is: `resolveCategoryConfig` returns the config, `resolveModelForDelegateTask` runs the pipeline with the user-configured `model` as the user-override (Step 2 wins). If the user did not configure `fallback_models`, the hardcoded chain from `CATEGORY_MODEL_REQUIREMENTS["quick-rust"]` would need to exist for Step 5 to work — and it does not. So user-defined categories that omit `fallback_models` rely entirely on Step 4 (user-configured `fallback_models`) and Step 6 (system default) if their primary model is unavailable.

This is *the* mechanism by which the project-specific category names get into the orchestration doc. The doc is documenting the *protocol* of category names, not the *built-in* defaults.

---

## 10. The other light-survey gap — connected-providers cache

For completeness, the `connected-providers-cache.ts` interface in `model-core` (`packages/model-core/src/connected-providers-cache.ts:1-38`) is a stub. The real implementation is wired in by `src/` at the consumer side:

* `hasProviderModelsCache()` / `hasConnectedProvidersCache()` — used in `model-selection.ts:96-104` to determine if the cache has been populated.
* `readConnectedProvidersCache()` — returns the list of connected provider IDs.
* `readProviderModelsCache()` — returns `{ models: Record<providerID, modelIDs>, connected: string[], updatedAt: string }` (`available-models.ts:46-72`).

The cache is populated by a separate flow (not in the files fetched) — likely the `bunx oh-my-opencode auth` / `opencode models` codepath, plus an OpenCode plugin lifecycle hook. The `available-models.ts` consumer prefers the provider-models cache (richer) over the connected-providers cache (just IDs), and falls back to `client.model.list()` if neither is populated.

The cache is what makes the first-run `availableModels.size === 0` path actually work: without it, Step 5 of the pipeline would have nothing to match against. The cache is *the* warm-up tax; once warm, every subsequent call uses the populated fuzzy-match path.

---

## 11. Where the boundaries of the system are (what categories cannot do)

After the deep read, the limits of the category-routing pattern are:

* **No per-call cost ceiling.** A user cannot say "for this call, never spend more than $0.10." Cost is a *side-effect* of the model choice; the system does not budget.
* **No per-call latency ceiling.** Same — latency is a side-effect of the model and the runtime. The `quota_exceeded` path *fails-over*, but does not *time-out*.
* **No category inheritance from parent session.** `resolveCategoryConfig` (`categories.ts:38-43`) explicitly says: "Categories have explicit models - no inheritance from parent session." A `deep` task running under a Sisyphus session does not inherit Sisyphus's model. The category is self-contained.
* **No "deny" list of models for a category.** The user can override any category to any model — there is no `banned_models` field. The dangerous-override detection is docs only.
* **No category-scoped tools permission.** The `tools` field is per-agent, not per-category. The Sisyphus-Junior agent that runs category-dispatched tasks has a single tool-permission set, regardless of category.
* **No category-scoped skills auto-load.** `load_skills` is a parameter on each `task()` call, not a category property. The user could work around this by setting `categories.deep.prompt_append` to mention required skills, but the framework does not auto-load them.
* **No multi-model fanout from a single category.** Each `task(category="…")` call resolves to exactly one model. To fan out across models, the caller must issue multiple `task()` calls.

These are *design choices*, not bugs. The maintainer optimized for: (a) intent-decoupled routing, (b) prompt-append customization, (c) family-diverse fallbacks, (d) docs-only safety. They did not optimize for: runtime cost budgets, latency ceilings, model-allowlist enforcement, or category-inheritance from parent sessions.

---

## 12. Pointers (where to read next)

| Concern | File | Lines |
|---------|------|-------|
| Category-to-chain data (8 categories) | `packages/model-core/src/model-requirements.ts` | 209-354 |
| Pipeline (the 6-step logic) | `packages/model-core/src/model-resolution-pipeline.ts` | 65-200 |
| `transformModelForProvider` (Claude dots, Gemini preview) | `packages/model-core/src/provider-model-id-transform.ts` | 43-89 |
| Connected-providers cache interface | `packages/model-core/src/connected-providers-cache.ts` | 1-38 |
| `fuzzyMatchModel` (substring + shortest-wins) | `packages/model-core/src/model-availability.ts` | 5-37 |
| Per-call category config merge | `src/tools/delegate-task/categories.ts` | 17-72 |
| Delegate-task category resolver (overrides, prompt-append merge) | `src/tools/delegate-task/category-resolver.ts` | 38-238 |
| Model selection at delegate-task site | `src/tools/delegate-task/model-selection.ts` | 62-213 |
| Available-models cache consumer | `src/tools/delegate-task/available-models.ts` | 46-72 |
| `deep` dynamic prompt-append (GPT-5.5 vs default) | `src/tools/delegate-task/openai-categories.ts` | 56-83 |
| `quick` `<Caller_Warning>` block | `src/tools/delegate-task/openai-categories.ts` | 102-160 |
| `unspecified-low/high` `<Selection_Gate>` | `src/tools/delegate-task/anthropic-categories.ts` | 4-50 |
| `visual-engineering` 4-phase design system workflow | `src/tools/delegate-task/google-categories.ts` | 1-78 |
| `writing` anti-AI-slop rules | `src/tools/delegate-task/kimi-categories.ts` | 3-29 |
| Plan-system-prompt category table | `src/tools/delegate-task/constants.ts` | `buildPlanAgentSkillsSection`, `PLAN_AGENT_SYSTEM_PREPEND_*` |
| `requiresProvider` type def | `packages/model-core/src/model-requirements.ts` | 14-25 |
| Hephaestus `requiresProvider` enforcement | `src/hooks/no-hephaestus-non-gpt/hook.ts` | 1-79 |
| Runtime-fallback hook entry | `src/hooks/runtime-fallback/hook.ts` | 38-114 |
| Runtime-fallback auto-retry | `src/hooks/runtime-fallback/auto-retry.ts` | 175-260 |
| Runtime-fallback error classifier | `src/hooks/runtime-fallback/error-classifier.ts` | `isRetryableError` |
| Runtime-fallback retryable patterns | `src/hooks/runtime-fallback/constants.ts` | 18-41 |
| Runtime-fallback state (cooldown, equivalence) | `src/hooks/runtime-fallback/fallback-state.ts` | full file |
| Runtime-fallback model list (per session) | `src/hooks/runtime-fallback/fallback-models.ts` | 18-105 |
| Proactive model-fallback hook | `src/hooks/model-fallback/hook.ts` | `createModelFallbackHook` |
| Notepad injection into Sisyphus-Junior tasks | `src/hooks/sisyphus-junior-notepad/hook.ts` | 9-51 |
| Team mode enablement | `docs/guide/team-mode.md` | full file (151 lines) |
| Plan lifecycle (Prometheus → Atlas → boulder) | `docs/guide/orchestration.md` | full file (627 lines) |
| Safe vs dangerous overrides (docs only) | `docs/guide/agent-model-matching.md` | "Safe vs Dangerous Overrides" section |
| Task-category doc table | `docs/guide/agent-model-matching.md` | "Task Categories" section |

# Support Agents in `oh-my-openagent` — Librarian, Explore, Multimodal-Looker

> Research only. No code changes. All findings sourced from `code-yeongyu/oh-my-openagent` (npm: `oh-my-opencode` / plugin: `oh-my-openagent`) on the `dev` branch via webfetch.

These three agents form the "support" tier in omo's 11-agent roster. They are **always** `subagent` mode (never selectable as a primary), have strict read-only tool restrictions, and are designed to be fired in parallel from a primary agent (Sisyphus, Hephaestus, Atlas) or via the `task` / `call_omo_agent` tools. Their job is retrieval and inspection — they do not write code.

Source of truth for the agent list: `src/agents/builtin-agents.ts:36-46` (registry), with metadata consumed by Sisyphus's dynamic delegation table at `src/agents/builtin-agents.ts:53-62`. The full model/permission matrix lives in `src/shared/model-requirements.ts` (re-exported from `@oh-my-opencode/model-core`).

Common patterns across all three:

- `mode: "subagent"` (types: `src/agents/types.ts:5-11`) — uses own fallback chain, ignores UI-selected model.
- `temperature: 0.1` — deterministic, factual output.
- Read-only tool surface. None can `write`, `edit`, `apply_patch`, `task`, or `call_omo_agent`. Multimodal-Looker is the strictest: **only `read` allowed**.
- Each exports a `*_PROMPT_METADATA` constant (category, cost, promptAlias, keyTrigger, triggers, useWhen, avoidWhen) that Sisyphus uses to build its dynamic Delegation Table, Tool Selection, and Key Triggers sections.

---

## 1. Librarian

### Purpose
Multi-repository analysis and documentation lookup. Answers questions about **open-source libraries and external codebases** with evidence (GitHub permalinks) by combining Context7, grep.app, the `gh` CLI, websearch, and webfetch. Stays current on library APIs and best practices.

> "Specialized codebase understanding agent for multi-repository analysis, searching remote codebases, retrieving official documentation, and finding implementation examples using GitHub CLI, Context7, and Web Search."
> — `src/agents/librarian.ts:32-35`

### Prompt shape
Stored in `src/agents/librarian.ts` (320 lines, 247 LOC). Structure:

- Lines 1-5: imports + `MODE = "subagent"` constant.
- Lines 7-23: `LIBRARIAN_PROMPT_METADATA` object (category, cost, promptAlias, keyTrigger, triggers, useWhen).
- Lines 25-33: `createLibrarianAgent(model)` factory — applies `createAgentToolRestrictions(["write", "edit", "apply_patch", "task", "call_omo_agent"])`.
- Lines 35-43: `AgentConfig` return with description, mode, model, temperature, restrictions, and the `prompt` field.
- Lines 44-318: a large template literal (approx. 11 KB) holding the system prompt.

Prompt sections (in order): `# THE LIBRARIAN` mission → `## CRITICAL: DATE AWARENESS` (uses `${new Date().getFullYear()}` interpolation) → `## PHASE 0: REQUEST CLASSIFICATION` (TYPE A/B/C/D) → `## PHASE 0.5: DOCUMENTATION DISCOVERY` (4-step websearch→version→sitemap→investigate) → `## PHASE 1: EXECUTE BY REQUEST TYPE` (one subsection per type, each with a "Parallel acceleration" code block of 4+ tool calls) → `## PHASE 2: EVIDENCE SYNTHESIS` (mandatory citation format, permalink construction) → `## TOOL REFERENCE` → `## PARALLEL EXECUTION REQUIREMENTS` → `## FAILURE RECOVERY` → `## COMMUNICATION RULES`.

Key inline detail: a `mandatory citation format` block (`librarian.ts:268-279`) requires every claim to carry a `https://github.com/<owner>/<repo>/blob/<sha>/<filepath>#L<start>-L<end>` permalink.

### Triggers
Invoked by:
- **Sisyphus (primary orchestrator)** — fires `librarian` whenever the metadata's `keyTrigger` matches: "External library/source mentioned → fire `librarian` background" (`librarian.ts:11`).
- **Hephaestus** — autonomously uses librarian for OSS research (per docs).
- **Users directly** — `@librarian how is this implemented` in chat, or via the `task` tool with `subagent_type: "librarian"`, or via `call_omo_agent` (`src/tools/call-omo-agent/tools.ts:30-32` confirms librarian is in `ALLOWED_AGENTS`).

### Model
Default: `opencode-go/minimax-m2.7` (latest dev snapshot; previously `glm-4.7`, `gemini-3-flash`, `zai-coding-plan/glm-5` per older docs/registry snapshots). Fallback chain (from `docs/reference/features.md` and `docs/guide/installation.md`): `minimax-m2.7` → `minimax-m2.7-highspeed` → `claude-haiku-4-5` → `gpt-5-nano`.

Per the **agent-model-matching** doc, Librarian sits in the **"Utility Agents"** bucket — "Doc retrieval doesn't need deep reasoning" (`docs/guide/installation.md`). The install guide explicitly warns: **"Librarian → Opus: Same. Doc search doesn't need Opus-level reasoning."** i.e. assigning a heavyweight reasoning model is a cost waste. Metadata `cost: "CHEAP"` (`librarian.ts:9`) encodes this.

### When to use
Explicit `useWhen` list (`librarian.ts:16-21`):
- "How do I use [library]?"
- "What's the best practice for [framework feature]?"
- "Why does [external dependency] behave this way?"
- "Find examples of [library] usage"
- "Working with unfamiliar npm/pip/cargo packages"

Public docs (`code-yeongyu-oh-my-opencode.mintlify.app/api/agents/librarian`) reinforce: external libraries, version-specific info, unfamiliar packages, OSS implementation patterns.

### When NOT to use
- **Internal codebase questions** → "Use Explore agent instead" (public docs related-agents section).
- **Heavy reasoning tasks** → assigning Opus is a "massive cost waste" per the agent-model-matching doc.
- **Code modifications** → blocked tools include `write`, `edit`, `apply_patch`.
- **Team Mode** → hard-rejected at TeamSpec parse time, per `docs/guide/team-mode.md`: "Hard-reject agents fail TeamSpec parsing because they cannot write mailbox state. Use `delegate-task` for those agents." (`oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `prometheus` are all in the hard-reject list.)

### Source location
- Agent definition: `src/agents/librarian.ts:1-320` (current `dev` branch).
- Registry entry: `src/agents/builtin-agents.ts:38` (`librarian: createLibrarianAgent`).
- Metadata export consumed by Sisyphus: `src/agents/builtin-agents.ts:55`.
- `call_omo_agent` allowlist confirms it can be spawned directly: `src/tools/call-omo-agent/tools.ts` (`ALLOWED_AGENTS` includes `librarian`).
- Public docs: `code-yeongyu-oh-my-opencode.mintlify.app/api/agents/librarian`.

---

## 2. Explore

### Purpose
**Internal** codebase search and contextual grep. Answers "Where is X?", "Which file has Y?", "Find the code that does Z". Designed for **fast, parallel** internal exploration. Differentiation from Librarian: Explore stays inside the local repo, Librarian goes outside it.

> "Contextual grep for codebases. Answers 'Where is X?', 'Which file has Y?', 'Find the code that does Z'. Fire multiple in parallel for broad searches. Specify thoroughness: 'quick' for basic, 'medium' for moderate, 'very thorough' for comprehensive analysis."
> — `src/agents/explore.ts:33-36`

### Prompt shape
Stored in `src/agents/explore.ts` (119 lines, 95 LOC) — **the shortest of the three agent files** and the shortest prompt. Structure:

- Lines 1-5: imports + `MODE = "subagent"`.
- Lines 7-22: `EXPLORE_PROMPT_METADATA` — note `cost: "FREE"` (the only FREE-rating agent) and explicit `avoidWhen` array (the only one of the three with this).
- Lines 24-32: `createExploreAgent(model)` — applies restrictions AND a 5-tool allowlist of LSP/ast_grep tools: `["lsp_symbols", "lsp_goto_definition", "lsp_find_references", "lsp_diagnostics", "ast_grep_search"]`. This is **the only agent** in the support tier with a positive tool grant (everything else is restricted).
- Lines 33-43: `AgentConfig` return.
- Lines 44-116: system prompt template literal.

Prompt sections: mission → `<analysis>`-wrapped intent analysis requirement → **mandatory** 3+ parallel tool calls in first action → required `<results>` / `<answer>` / `<next_steps>` XML block → Success Criteria (absolute paths, completeness, actionability) → Failure Conditions → Constraints (read-only, no emojis) → Tool Strategy table (semantic=LSP, structural=ast_grep, text=grep, file=glob, history=git).

Key inline detail: a `<results>` block is enforced as the *closing* of every response (`explore.ts:55-67`), making Explore's output parseable by the orchestrator.

### Triggers
Invoked by:
- **Sisyphus** — `keyTrigger: "2+ modules involved → fire `explore` background"` (`explore.ts:11`).
- **Hephaestus** and other workers doing internal research.
- **Direct invocation** — `@explore` mention, `task` tool, or `call_omo_agent` (librarian + explore are the only two allowed `subagent_type` values in `call_omo_agent` per `src/tools/call-omo-agent/tools.ts:30-32`).

### Model
Default: `github-copilot|xai/grok-code-fast-1` (per `docs/reference/features.md` and `docs/guide/installation.md`). Fallback chain: `grok-code-fast-1` → `opencode-go/minimax-m2.7-highspeed` → `opencode/minimax-m2.7` → `claude-haiku-4-5` → `gpt-5-nano`.

Per **agent-model-matching** (`docs/guide/installation.md`): "Speed is everything. Exact runtime chain from `src/shared/model-requirements.ts`." Warning: "Explore → Opus: **Massive cost waste. Explore needs speed, not intelligence.**" Metadata `cost: "FREE"` (`explore.ts:9`) reflects this — Explore is the only "FREE"-tier agent in the support group.

### When to use
Explicit `useWhen` (`explore.ts:16-19`):
- "Multiple search angles needed"
- "Unfamiliar module structure"
- "Cross-layer pattern discovery"

Public docs add: "2+ modules involved → fire explore in background". The recommended pattern is to launch 2-5 explore agents **in parallel** with different angles (search-history, search-pattern, find-symbol, etc.).

### When NOT to use
Explicit `avoidWhen` — **the only support agent with this section populated** (`explore.ts:20-23`):
- "You know exactly what to search"
- "Single keyword/pattern suffices"
- "Known file location"

Public docs also call out: "Never use for external libraries — Use Librarian agent instead." Other restrictions: read-only (cannot create/modify files), no emojis, no file creation. **Team Mode**: hard-rejected, same as Librarian (`docs/guide/team-mode.md`).

### Source location
- Agent definition: `src/agents/explore.ts:1-119` (current `dev` branch).
- Registry entry: `src/agents/builtin-agents.ts:39` (`explore: createExploreAgent`).
- Metadata export: `src/agents/builtin-agents.ts:56`.
- `call_omo_agent` allowlist: `src/tools/call-omo-agent/tools.ts:30-32` (librarian + explore only).
- Public docs: `code-yeongyu-oh-my-opencode.mintlify.app/api/agents/explore`.

---

## 3. Multimodal-Looker

### Purpose
**Visual content specialist.** Interprets media files (PDFs, images, diagrams) that the standard `read` tool cannot parse. Saves context tokens by extracting only the requested slice of a media file rather than dumping raw contents to the main agent.

> "Analyze media files (PDFs, images, diagrams) that require interpretation beyond raw text. Extracts specific information or summaries from documents, describes visual content. Use when you need analyzed/extracted data rather than literal file contents."
> — `src/agents/multimodal-looker.ts:19-22`

### Prompt shape
Stored in `src/agents/multimodal-looker.ts` (60 lines, 48 LOC) — **the shortest agent file in the entire codebase**. Structure:

- Lines 1-5: imports + `MODE = "subagent"`.
- Lines 7-12: `MULTIMODAL_LOOKER_PROMPT_METADATA` — `category: "utility"`, `cost: "CHEAP"`, `triggers: []` (empty — Multimodal-Looker is *not* in the metadata-driven Sisyphus delegation table).
- Lines 14-17: `createMultimodalLookerAgent(model)` — applies `createAgentToolAllowlist(["read"])` — **the only allowlist (vs. denylist) in the support tier and one of the strictest in omo overall**.
- Lines 18-30: `AgentConfig` return.
- Lines 30-58: system prompt template literal (concise, ~1 KB).

Prompt sections: "you interpret media files that cannot be read as plain text" mission → critical rule "**the file or image is already attached to the message. Analyze the attachment directly. Never call tools, never spawn other agents, and never try to load the file by path**" (lines 32-33) → When to use / When NOT to use lists → 4-step workflow → per-medium guidance (PDFs, images, diagrams) → 4 response rules.

Key inline detail: the prompt explicitly forbids tool use and agent delegation, so the "tools" it has are purely virtual (only `read` of the attached attachment). This is unique among the 11 agents.

### Triggers
Invoked by:
- **The `look_at` tool** — the *only* entry point in practice. The tool (`src/tools/look-at/tools.ts`) takes `file_path` or `image_data` + a `goal` string, creates a child session of the multimodal-looker agent, and attaches the file as a file part. `LOOK_AT_DESCRIPTION` in `src/tools/look-at/constants.ts` is the user-facing description.
- **The `task` tool** with `subagent_type: "multimodal-looker"`.
- **NOT** in `ALLOWED_AGENTS` for `call_omo_agent` (`src/tools/call-omo-agent/tools.ts:30-32` allows only `explore` and `librarian`).
- **Not** in the metadata-driven Sisyphus delegation table (`triggers: []` in `multimodal-looker.ts:11`).

### Model
**Yes — Multimodal-Looker specifically requires a multimodal-capable (vision) model.** The `look_at` tool enforces this at runtime via `isVisionCapableResolvedModel()` in `src/tools/look-at/tools.ts:42-51` and `isVisionCapableAgentModel()` in `src/tools/look-at/multimodal-agent-metadata.ts:31-46` — the tool will refuse to run and return `"Error: No vision-capable multimodal-looker model available"` if the resolved model isn't in `visionCapableModelsCache` (populated from `provider.*.models[*].modalities.input: ["image"]` declarations in user config, per `src/plugin-handlers/provider-config-handler.ts:30-37`).

Default chain (per `docs/guide/installation.md` Agent-Model Matching table):
- Primary: `openai|opencode/gpt-5.4` (variant `medium`)
- Fallback 1: `opencode-go/kimi-k2.5`
- Fallback 2: `zai-coding-plan/glm-4.6v`
- Fallback 3: `openai|github-copilot|opencode/gpt-5-nano`

This is the **only** agent in omo whose model selection is gated by capability detection rather than simple override — see PR #2686 (March 2026) and commit `85151f7` for the vision-capability guard. The recently-merged PR #4209 (May 2026, commit `bfc5078`) further "trusts" user-configured multimodal-looker models as vision-capable even when the provider config doesn't declare `modalities.input: ["image"]` — to unblock models like `zhipuai-coding-plan/glm-5.1` that are vision-capable in practice but not advertised in the provider schema.

Public docs note that with **Z.ai only** (`bunx oh-my-opencode install --zai-coding-plan=yes`), Multimodal-Looker is configured as `zai-coding-plan/glm-4.6v` — the only documented Z.ai vision model.

### When to use
Explicit in-prompt list (`multimodal-looker.ts:36-40`):
- "Media files that need visual or document interpretation"
- "Extracting specific information or summaries from documents"
- "Describing visual content in images or diagrams"
- "When analyzed/extracted data is needed, not raw file contents"

Public docs enumerate: PDF analysis, image interpretation, diagram analysis, specific data extraction, context-token optimization.

### When NOT to use
Explicit in-prompt `When NOT to use you` list (`multimodal-looker.ts:41-44`):
- "Source code or plain text files needing exact contents"
- "Files that need editing afterward"
- "Simple file reading where no interpretation is needed"

Public docs add: "Don't use for critical exact data — If precision is critical, verify manually" (vision models may misread). **Tool restrictions:** allowlist of only `read` — cannot use `write`, `edit`, `bash`, `grep`, `glob`, `task`, or any other tool. **Team Mode:** hard-rejected (`docs/guide/team-mode.md`).

### Source location
- Agent definition: `src/agents/multimodal-looker.ts:1-60` (current `dev` branch).
- Registry entry: `src/agents/builtin-agents.ts:40` (`"multimodal-looker": createMultimodalLookerAgent`).
- Metadata export: `src/agents/builtin-agents.ts:57`.
- Tool that invokes it: `src/tools/look-at/tools.ts` and constants at `src/tools/look-at/constants.ts:3-6`.
- Vision-capability gate: `src/tools/look-at/multimodal-agent-metadata.ts:31-46` + `src/tools/look-at/tools.ts:42-51`.
- Provider config vision detection: `src/plugin-handlers/provider-config-handler.ts:30-37, 60-87`.
- Public docs: `code-yeongyu-oh-my-opencode.mintlify.app/api/agents/multimodal-looker`.

---

## Cross-cutting notes

- **Metadata-driven Sisyphus prompt:** All three agents export `*_PROMPT_METADATA` (`src/agents/types.ts:38-65`) so Sisyphus can build its Delegation Table, Tool Selection, and Key Triggers sections dynamically. **Multimodal-Looker is the odd one out** — its `triggers: []` and absence from Sisyphus's documented `@-mention` examples reflect that it's a *tool-driven* agent (called via `look_at`), not a *delegation-driven* agent like Librarian and Explore.
- **`call_omo_agent` is a narrower entry point than `task`:** only `explore` and `librarian` are in `ALLOWED_AGENTS` (`src/tools/call-omo-agent/tools.ts:30-32`). To use Multimodal-Looker programmatically, agents must use the `task` tool with `subagent_type: "multimodal-looker"` or call `look_at` directly.
- **Team Mode:** all three are in the hard-reject list (`docs/guide/team-mode.md`). The reject reason: "cannot write mailbox state". The `delegate-task` tool is the recommended substitute.
- **Tool restriction philosophies:**
  - **Librarian & Explore:** denylist of mutating/delegating tools (`write`, `edit`, `apply_patch`, `task`, `call_omo_agent`). Explore additionally has an *allowlist* of 5 LSP/ast_grep tools.
  - **Multimodal-Looker:** pure allowlist of `read` only.
  - All three have `temperature: 0.1` for deterministic, factual output.

### Honest gaps
- The exact default model for each agent has shifted across omo releases (4-5 variants seen in different docs/commits: `gpt-5.3-codex`, `gpt-5.4`, `minimax-m2.7`, `gemini-3-flash`, `zai-coding-plan/glm-5`, `kimi-k2.5-free`). The `dev` branch source as of fetch is the most authoritative current default, but the public docs and the install-time configurator are the canonical source for what a given user actually gets.
- Line numbers in this doc are based on the file headers reported by the GitHub UI (e.g. "320 lines, 247 loc" for `librarian.ts`); the content was verified against the raw file via `raw.githubusercontent.com` and the line ranges correspond to the file as of fetch.
- The `AGENT_MODEL_REQUIREMENTS` table has been extracted out of the plugin to a separate `@oh-my-opencode/model-core` package (`src/shared/model-requirements.ts:1-5` is now a re-export). The exact fallback chain is resolved at runtime; the docs reflect the *expected* chain.
- Multimodal-Looker's prompt has `triggers: []`, which means it is not in the metadata-driven Sisyphus delegation table — its invocation is *de facto* driven by the `look_at` tool description and the `task` tool's `subagent_type` mechanism. The lack of a `keyTrigger` is intentional, not an oversight.

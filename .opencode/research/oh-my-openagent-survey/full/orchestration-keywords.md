# Orchestration Keywords & Dispatch — oh-my-openagent

**Repo:** [`code-yeongyu/oh-my-openagent`](https://github.com/code-yeongyu/oh-my-openagent) (`dev` branch). The user-facing surface for orchestration is split between two independent dispatch paths: **inline keywords** that mutate the user's prompt before it reaches the model (e.g. `ulw`, `ultrawork`, `hyperplan`) and **slash commands** that OpenCode resolves to a separate command template (e.g. `/start-work`, `/ralph-loop`). They never overlap — the keyword detector explicitly skips messages that begin with a slash.

---

## 1. `ulw` / `ultrawork` — the magic keyword

### What it does
`ulw` (or its long form `ultrawork`) is the canonical "Type three letters. Walk away." trigger. Detecting it in the user's first message activates **Ultrawork Mode**: a model-tuned system-prompt body is prepended to the prompt, a TUI toast fires, and (when a `max` variant is configured) the runtime variant is preserved so the orchestrator runs at its highest reasoning tier. The injected prompt forces parallel exploration, strict todo tracking, and use of the full delegate-task / category system. See [`docs/guide/orchestration.md` — *Hephaestus vs Sisyphus + ultrawork*](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/orchestration.md).

### How it is parsed
The detector is a single case-insensitive word-boundary regex registered in the `KEYWORD_DETECTORS` array:

```ts
// src/hooks/keyword-detector/constants.ts:42-46
{
  type: "ultrawork",
  pattern: /\b(ultrawork|ulw)\b/i,
  message: getUltraworkMessage,
}
```

Source: [`src/hooks/keyword-detector/constants.ts:42`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/constants.ts).

Before matching, `removeCodeBlocks()` strips fenced ``` ``` ``` blocks and `` `inline` `` spans so the keyword is **not** triggered when quoted ([`detector.ts:14-16`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/detector.ts)).

### Where the keyword is matched in the prompt pipeline
The hook is `createKeywordDetectorHook()` ([`src/hooks/keyword-detector/hook.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/hook.ts)), wired to OpenCode's `chat.message` lifecycle event. Logic flow ([`hook.ts:54-200+`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/hook.ts)):

1. `extractPromptText(parts)` — concatenate real user text parts.
2. Skip if `isSystemDirective` or `looksLikeSlashCommand` (`/^\s*\/[a-zA-Z][\w-]*(?:\s|$)/`, `detector.ts:21`).
3. Skip if `isNonOmoAgent(currentAgent)` — i.e. OpenCode's built-in *Builder* or *Plan* agents (`ultrawork/source-detector.ts:30-35`).
4. `detectKeywordsWithType(cleanText, agentName, modelID, disabledKeywords, enabledExpansions)`.
5. `isPlannerAgent` (prometheus/planner/plan) ⇒ strip `ultrawork`/`hyperplan` (Prometheus *is* the planner; double-injection would loop).
6. Subagent / background-task sessions ⇒ skip entirely.
7. Non-main sessions ⇒ only `ultrawork` and `hyperplan-ultrawork` are allowed to propagate.
8. `filterAlreadyInjectedKeywords` — prevents re-injection on retry messages.
9. Fires `tui.showToast` ("Ultrawork Mode Activated — Maximum precision engaged. All agents at your disposal.") with `variant: "max"` vs. "Runtime variant preserved" depending on `getRuntimeVariant(input, output.message)` (`hook.ts:170-187`).
10. Injects `${allMessages}\n\n---\n\n${originalText}` into the first real user text part.

### What state does it set
- **No persistent file state.** Ultrawork is purely a per-message prompt transform.
- **Per-session memo:** `defaultModeUltraworkInjectedSessions: Set<string>` (`hook.ts:23`) tracks "default-mode" injections so they fire only once per main session.
- **Runtime variant:** when `message.variant === "max"` the toast advertises "Maximum precision engaged"; otherwise it advertises "Runtime variant preserved" (the existing variant is honored, not forced).
- **Model-aware body selection** is delegated to `getUltraworkMessage(agentName, modelID)` in [`src/hooks/keyword-detector/ultrawork/index.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/ultrawork/index.ts), which switches on `getUltraworkSource()` ([`ultrawork/source-detector.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/ultrawork/source-detector.ts)) and returns one of four bodies loaded via Bun's `.md` text loader from `packages/prompts-core/prompts/ultrawork/`:
  - `planner.md` — planner agents (prometheus / planner / plan)
  - `gpt.md` — when `isGptModel(modelID)`
  - `gemini.md` — when `isGeminiModel(modelID)`
  - `default.md` — Claude and everything else

---

## 2. Other notable inline keywords

All inline keywords live in the same detector loop with the same guard rails. From [`constants.ts:7-58`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/hooks/keyword-detector/constants.ts) and the `KeywordTypeSchema` in [`src/config/schema/keyword-detector.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/config/schema/keyword-detector.ts):

| Keyword | Pattern | Effect |
|---|---|---|
| `ultrawork` / `ulw` | `/\b(ultrawork\|ulw)\b/i` | Full orchestration mode (above). |
| Search mode | `SEARCH_PATTERN` (`search/default.ts`) | Web/doc search focus. |
| Analyze mode | `ANALYZE_PATTERN` (`analyze/default.ts`) | Deep analysis prompt. |
| Team mode | `/\bteam[\s_-]?mode\b/i` (`team/default.ts:11`) | Forces orchestration via `team_*` tools; reminds user to enable `team_mode.enabled` if tools are absent. |
| Hyperplan | `HYPERPLAN_PATTERN` (`hyperplan/default.ts`) | Loads `hyperplan` skill; adversarial 5-agent plan critique. |
| `hyperplan-ultrawork` combo | `/\b(?:hpp\|hyperplan)\s+(?:ulw\|ultrawork)\b\|\b(?:ulw\|ultrawork)\s+(?:hpp\|hyperplan)\b/i` (`constants.ts:18-19`) | Combo banner + skill load + routed ultrawork body. Standalone `ultrawork` and `hyperplan` are suppressed when the combo fires (`suppressComboStandalones`, `hook.ts:25-29`). |

Combo gate: if `ultrawork` *or* `hyperplan` is in `disabled_keywords`, `hyperplan-ultrawork` is auto-disabled too (`detector.ts:55-57`).

There is **no `/compact` or `/clear`** keyword in OmO — those are OpenCode's own native built-ins and OmO does not intercept them. The orchestration-relevant compaction logic instead lives in the `preemptive-compaction` hook, not the keyword surface.

---

## 3. Slash commands (the full registry)

OmO ships its built-in slash commands as a static registry in [`src/features/builtin-commands/commands.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/builtin-commands/commands.ts). The union type lives in [`src/features/builtin-commands/types.ts:3`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/builtin-commands/types.ts):

```ts
export type BuiltinCommandName =
  | "ralph-loop" | "cancel-ralph" | "ulw-loop"
  | "refactor"   | "start-work"   | "stop-continuation"
  | "handoff"    | "remove-ai-slops" | "hyperplan"
```

| Command | Source template | What it does |
|---|---|---|
| `/init-deep` | (separate hook; produces hierarchical `AGENTS.md` files) | Project knowledge-base bootstrap. |
| `/ralph-loop` | `templates/ralph-loop.ts` → `RALPH_LOOP_TEMPLATE` | Self-referential dev loop until task done; args `"task" [--completion-promise=…] [--max-iterations=N] [--strategy=reset\|continue]`. |
| `/ulw-loop` | `templates/ralph-loop.ts` → `ULW_LOOP_TEMPLATE` | Ralph loop fused with ultrawork mode. |
| `/cancel-ralph` | `templates/ralph-loop.ts` → `CANCEL_RALPH_TEMPLATE` | Tears down an active Ralph loop. |
| `/refactor` | `templates/refactor.ts` | LSP + AST-grep + codemap refactor pipeline. Appends `REFACTOR_TEAM_MODE_ADDENDUM` when `teamModeEnabled`. |
| `/start-work` | `templates/start-work.ts` | Reads `.omo/plans/*.md` produced by Prometheus, resumes from `.omo/boulder.json` if present, switches the session agent to **Atlas** (or falls back to **Sisyphus** when atlas is unregistered, via `resolveStartWorkAgent`, `commands.ts:18-24`). Injects `$SESSION_ID` / `$TIMESTAMP` placeholders. |
| `/stop-continuation` | `templates/stop-continuation.ts` | Halts ralph loop + todo continuation + boulder for the current session. |
| `/handoff` | `templates/handoff.ts` | Emits a portable session-context summary for resuming in a new session. |
| `/remove-ai-slops` | `templates/remove-ai-slops.ts` | Cleans AI-generated code smells from branch diff. Appends team-mode addendum when enabled. |
| `/hyperplan` | `templates/hyperplan.ts` | Adversarial multi-agent planning (5 hostile members cross-critique, lead synthesizes). |

Loading happens in `loadBuiltinCommands(disabledCommands, options)` ([`commands.ts:130-149`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/builtin-commands/commands.ts)): each definition is filtered against `disabled_commands` from user config, then merged with `.opencode/commands/*` and Claude-Code plugin commands by the `claude-code-command-loader`. Disable via:

```jsonc
{ "disabled_commands": ["init-deep", "start-work"] }
```

(see `docs/reference/configuration.md` — *Commands*).

---

## 4. Relationship between keywords and the workflow loop

T9 covers the loop body. From a dispatch-mechanism standpoint, the keyword/command split is the *entry point* into the loop:

```
┌──── User input ──────────────────────────────────────┐
│  Begins with "/"  ──► OpenCode native slash dispatch │
│                       → builtin-commands template    │
│                       → optionally switches agent    │
│                         (e.g. /start-work → Atlas)   │
│                                                      │
│  Otherwise         ──► chat.message hook             │
│                       → keyword-detector.detect()    │
│                       → prepend mode prompt to msg   │
│                       → showToast()                  │
│                       → model receives the augmented │
│                         prompt; ordinary loop runs   │
└──────────────────────────────────────────────────────┘
```

Inline keywords are **prompt augmentation** — they do not change which agent receives the message, only what the model sees. Slash commands are **template + optional agent override** — `start-work` sets `agent: "atlas"` directly in its `CommandDefinition` (`commands.ts:80`). Ultrawork mode and Ralph loops can be composed (`/ulw-loop` is literally a Ralph template with the ultrawork directive baked in).

`getMainSessionID()` / `subagentSessions` (`hook.ts:7-12`, `hook.ts:104-114`) constrain keyword injection so the loop's *subagent* turns are not re-augmented; this is what allows the ultrawork body to be injected exactly once and then carried implicitly through the delegation tree.

---

## 5. Opt-in flags and their interaction with keywords

### `keyword_detector`
Schema in [`src/config/schema/keyword-detector.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/config/schema/keyword-detector.ts):

```ts
export const KeywordTypeSchema = z.enum([
  "ultrawork","search","analyze","team","hyperplan","hyperplan-ultrawork",
])

export const KeywordDetectorConfigSchema = z.object({
  enabled_expansions: z.array(KeywordTypeSchema).optional(),
  disabled_keywords:  z.array(KeywordTypeSchema).optional(),
})
```

`disabled_keywords` is a blocklist; `enabled_expansions` is an allowlist — if set, only the listed keyword types fire (`detector.ts:58-71`).

### `default_mode`
[`src/config/schema/default-mode.ts`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/config/schema/default-mode.ts):

```ts
DefaultModeConfigSchema = z.object({
  ultrawork:  z.boolean().default(false),   // inject ultrawork prompt on session start
  ralph_loop: z.boolean().default(false),   // auto-/ralph-loop on session start
})
```

When `default_mode.ultrawork === true`, the hook injects the ultrawork prompt automatically on the first turn even with **no** keyword in the user message (`hook.ts:120-141`), and `defaultModeUltraworkInjectedSessions` guarantees one-shot. Combining `default_mode.ultrawork` + `default_mode.ralph_loop` is the documented "fully autonomous" recipe.

### `team_mode` — the high-blast-radius opt-in
Off by default. From [`src/features/team-mode/AGENTS.md`](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/src/features/team-mode/AGENTS.md):

```jsonc
{
  "team_mode": {
    "enabled": false,                     // gate — restart required
    "tmux_visualization": false,
    "max_parallel_members": 4,            // 1..8
    "max_members": 8,
    "max_messages_per_run": 10000,
    "max_wall_clock_minutes": 120,
    "max_member_turns": 500,
    "message_payload_max_bytes": 32768,
    "recipient_unread_max_bytes": 262144,
    "mailbox_poll_interval_ms": 3000
  }
}
```

Interaction with the keyword surface:
- The `team` keyword body (`team/default.ts` → `TEAM_MODE_PROMPT`) explicitly *instructs the user* to set `team_mode.enabled: true` if they discover the `team_*` tools missing — i.e. the keyword always fires, but only becomes useful once the gate is open.
- `team_mode.enabled` is also consulted at command-load time: `loadBuiltinCommands(..., { teamModeEnabled })` appends `REFACTOR_TEAM_MODE_ADDENDUM` and `REMOVE_AI_SLOPS_TEAM_MODE_ADDENDUM` to the relevant slash-command templates so they prefer the team_* tool family when enabled (`commands.ts:31-44`).
- `/hyperplan` is the slash-command counterpart that *requires* `team_mode.enabled` (5 hostile members are spawned via `team_create`). The `hyperplan` skill (loaded by the `hyperplan` keyword) issues the same requirement.

### Other relevant opt-ins
- `disabled_hooks: ["keyword-detector"]` — flat-out turns the entire dispatch layer off (`docs/reference/configuration.md`).
- `sisyphus_agent.planner_enabled` (default `true`) and `sisyphus_agent.replace_plan` (default `true`) gate whether Prometheus exists and whether OpenCode's native `plan` agent is swapped for it; this is what makes `@plan` and Tab → Prometheus equivalent.
- `disabled_commands: [...]` per-command kill switch as listed above.

# oh-my-openagent — Orchestration Extension Points

Survey of skills, hooks, plugin architecture, and MCPs in `code-yeongyu/oh-my-openagent` (npm: `oh-my-opencode`, dual-published as `oh-my-openagent` during rename).

---

## 1. Skills System

**Custom implementation, not OpenCode's native one.** oh-my-openagent ships its own skill loader at `src/features/opencode-skill-loader/` (25 files, ~3.2k LOC) and registers a custom `skill` tool that **replaces** OpenCode's native `SkillTool`. The two are interoperable on the filesystem (the loader scans the same conventional paths) but the runtime is omO's.

Recent evidence this is *not* a passthrough: PR #3560 fixed a critical bug where omO's replacement `skill` tool shadowed native skill discovery, breaking every other OpenCode plugin that registered skills via `config.skills.paths` (e.g. `superpowers` with 14 skills). The fix added `src/features/opencode-skill-loader/opencode-config-skill-paths.ts` to merge `config.skills.paths` into the loader's discovery.

### Discovery scopes (priority order)

1. Project: `.opencode/skills/*/SKILL.md`
2. OpenCode (built-in): `src/features/builtin-skills/`
3. User: `~/.config/opencode/skills/*/SKILL.md`
4. Global / Claude-compat: `.claude/skills/`, `~/.claude/skills/`, `.agents/skills/`, `~/.agents/skills/`
5. `config.skills.paths` (OpenCode native, added in #3560, lowest priority)

### Format

`SKILL.md` with YAML frontmatter. omO extends the [OpenCode frontmatter spec](https://opencode.ai/docs/skills/) with extra fields:

```yaml
---
name: my-skill            # required, kebab-case
description: short text   # required
mcpServers:               # embedded MCPs (omO extension)
  playwright:
    command: npx
    args: ["@playwright/mcp@latest"]
allowedTools:             # glob-style tool restrictions
  - "Bash(agent-browser:*)"
  - "Read"
providersGating:          # restrict to specific model providers
  - anthropic
---
```

OpenCode's native spec only recognizes `name`, `description`, `license`, `compatibility`, `metadata`. omO reads the rest and routes them to its own runtime.

### Built-in skills (6)

`src/features/builtin-skills/skills/` — implemented as `BuiltinSkill` TypeScript objects, not raw `SKILL.md` files:

| Skill | Source | Notes |
|-------|--------|-------|
| `git-master` | `src/features/builtin-skills/skills/git-master.ts` | 1111 LOC, three modes (COMMIT/REBASE/HISTORY_SEARCH) |
| `playwright` | `src/features/builtin-skills/skills/playwright.ts:3` | 312 LOC, ships `@playwright/mcp@latest` via `mcpConfig` |
| `agent-browser` | `src/features/builtin-skills/skills/playwright.ts:17` | 296 LOC, Vercel CLI alternative |
| `playwright-cli` | `src/features/builtin-skills/skills/playwright-cli.ts` | 268 LOC, lightweight CLI wrapper |
| `dev-browser` | `src/features/builtin-skills/dev-browser/SKILL.md` | 221 LOC, dev patterns |
| `frontend-ui-ux` | `src/features/builtin-skills/skills/frontend-ui-ux.ts:3` | 79 LOC, designer persona |

Selection between browser providers is gated by `browser_automation_engine` config.

### Loading

Loaded on demand by the `skill` tool (omO's, not OpenCode's). The tool enumerates available skills in its description and the LLM calls `skill(name="...")` to inject content + spin up any embedded MCP servers via `SkillMcpManager`. The `skill_mcp` tool is a sibling that proxies calls to those embedded servers.

Disable with `disabled_skills: ["playwright", ...]` in `oh-my-openagent.jsonc`.

---

## 2. Hooks System

**Custom, deeply integrated.** omO implements 46–59 lifecycle hooks (base 46 + 7–13 with `team_mode.enabled`) across 5 tiers, composed in `src/plugin/hooks/create-*-hooks.ts` factories. They hook OpenCode's 8–10 public lifecycle events and run as part of the plugin's own code — there is no user-facing "drop a hook file in `.opencode/hooks/`" surface.

### Tiers (from `src/hooks/AGENTS.md`)

| Tier | File | Count | Events |
|------|------|-------|--------|
| Session | `src/plugin/hooks/create-session-hooks.ts` | 23–24 | `chat.message`, `chat.params`, `session.idle`, `session.error`, `session.created`, `session.compacted` |
| Tool-Guard | `src/plugin/hooks/create-tool-guard-hooks.ts` | 10–14 | `tool.execute.before`, `tool.execute.after` |
| Transform | `src/plugin/hooks/create-transform-hooks.ts` | 4–5 | `experimental.chat.messages.transform` |
| Continuation | `src/plugin/hooks/create-continuation-hooks.ts` | 7 | `session.idle`, `event` |
| Skill | `src/plugin/hooks/create-skill-hooks.ts` | 2 | `chat.message` |

Team-mode adds: +1 Tool-Guard (`team-tool-gating`), +2 Transform (`team-mode-status-injector`, `team-mailbox-injector`), +4 direct event handlers in `src/plugin/event.ts`.

### Notable built-ins (selection, ~50 total)

- **Pre-tool** (`tool.execute.before`): `write-existing-file-guard`, `bash-file-read-guard`, `webfetch-redirect-guard`, `prometheus-md-only` (planner read-only), `rules-injector`, `directory-agents-injector` (auto-disabled on OpenCode 1.1.37+ — native AGENTS.md support), `question-label-truncator`.
- **Post-tool** (`tool.execute.after`): `comment-checker` (slop-comment AST detection, in `src/hooks/comment-checker/`), `tool-output-truncator` (2000 lines / 51200 bytes), `hashline-read-enhancer` (annotates Read with `LINE#ID` content hashes), `json-error-recovery`, `edit-error-recovery`, `delegate-task-retry`, `empty-task-response-detector`.
- **Session**: `todo-continuation-enforcer` ("boulder" — exponential backoff 30s→×2→5min pause), `atlas` (master orchestrator with 7 gates including 5s cooldown), `session-recovery` (30 files ~1800 LOC), `anthropic-context-window-limit-recovery` (31 files ~2232 LOC), `preemptive-compaction`, `ralph-loop` (max 100 iterations, persisted at `.sisyphus/ralph-loop.local.md`).
- **Model/runtime** (`chat.params`): `think-mode`, `model-fallback` (chain: Claude → OpenAI → Gemini → Copilot → OpenCode Zen → Z.ai → Kimi), `anthropic-effort`, `runtime-fallback` (separate reactive system).
- **Transform** (`messages.transform`): `claude-code-hooks` (compatibility shim, `src/hooks/claude-code-hooks/`), `keyword-detector` (1665 LOC — detects `ultrawork`/`ulw`, `search`, `analyze`, `prove-yourself`, `team`, `hyperplan`), `thinking-block-validator`, `context-injector`.

### User hooks

**No first-class user hook loader.** Users can:

1. Toggle built-ins via `disabled_hooks: ["comment-checker", "ralph-loop", ...]` in `oh-my-openagent.jsonc` (any of ~50 names; see config ref).
2. Configure the `claude-code-hooks` hook, which reads `~/.claude/settings.json` and maps Claude Code hook events (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`) onto omO's internal pipeline. Claude Code's hook format (commands, JSON matchers) is the de facto user extension surface.
3. Toggle the whole Claude Code compat layer per-axis via `claude_code: { hooks: false, ... }` in plugin config.

The `disabled_hooks` schema lives in `src/config/schema/hooks.ts` (`HookNameSchema`).

---

## 3. Plugin Architecture

The "plugin" in omO's name **is itself an OpenCode plugin**, plus the runtime it brings along. The npm package `oh-my-opencode` (legacy name, still published) is dual-published as `oh-my-openagent` during the rename transition.

### Package & entry point

`package.json` (`oh-my-opencode@4.7.5`):

- `"main": "./dist/index.js"`, `"type": "module"`, ESM only
- `exports`: `.` → `dist/index.js`, `./server` → `dist/index.js`, `./schema.json` → `dist/oh-my-opencode.schema.json`
- `bin`: `oh-my-opencode`, `oh-my-openagent`, `omo`, `lazycodex-ai`, `lazycodex-ai` (all point to `bin/oh-my-opencode.js`)
- 12 platform optional deps (`oh-my-opencode-darwin-arm64`, `...-linux-x64-musl`, `...-windows-x64`, etc.)
- Peer dep: `zod ^4.0.0`

`src/index.ts` is a thin re-export:

```typescript
import type { PluginModule } from "@opencode-ai/plugin"
import { createPluginModule } from "./testing/create-plugin-module"
const pluginModule: PluginModule = createPluginModule()
export default pluginModule
```

Plugin shape is `{ id, server }` matching OpenCode's `PluginModule` type from `@opencode-ai/plugin`. `server(input, options)` returns the 10 OpenCode hook handlers.

### Loader

OpenCode's plugin loader (per [opencode.ai/docs/plugins](https://opencode.ai/docs/plugins/)) resolves the package. Since recent OpenCode builds, the installer (per PR #2980) writes a **managed `file://`** plugin entry — `file:///.../node_modules/oh-my-opencode/dist/index.js` — into `opencode.json`, and tracks the version in the config dir's `package.json` dependencies. Legacy package-name entries (`"oh-my-opencode"`) still load with a warning. OpenCode runs `bun install` at startup to fetch deps into `~/.cache/opencode/node_modules/`.

### 7-step init pipeline (`pluginModule.server`)

1. `installAgentSortShim()` — patches `Array.prototype.toSorted`/`.sort` to enforce canonical agent order Sisyphus → Hephaestus → Prometheus → Atlas
2. `initConfigContext()` — sets the `opencode` vs `openagent` layout flag
3. `detectExternalSkillPlugin()` — warns on conflicts with other skill plugins
4. `injectServerAuthIntoClient()` — auth headers into shared SDK client
5. `loadPluginConfig()` — JSONC parse → user/project merge → Zod v4 validate → migrate
6. `initializeOpenClaw()` — if `openclaw` config present
7. `checkTeamModeDependencies()` — if `team_mode.enabled`
8. `createManagers()` — `TmuxSessionManager`, `BackgroundManager`, `SkillMcpManager`, `ConfigHandler`
9. `createTools()` — `SkillContext` + `AvailableCategories` + `ToolRegistry` (16 tool dirs → 20–39 tools, config-gated)
10. `createHooks()` — 5-tier composition: Session + ToolGuard + Transform + Continuation + Skill
11. `createPluginInterface()` — 10 OpenCode hook handlers → `PluginInterface`

### 10 OpenCode hook handlers

| Handler | OpenCode event | Purpose |
|---------|----------------|---------|
| `config` | `config` | 6-phase pipeline: provider → plugin-components → agents → tools → MCPs → commands |
| `tool` | `tool` | Register 20–39 tools (gated: team-mode +12, task-system +4, hashline +1, interactive_bash +1, look_at +1) |
| `chat.message` | `chat.message` | First-message variant, session setup, keyword detection |
| `chat.params` | `chat.params` | Anthropic effort, think mode, runtime fallback override |
| `chat.headers` | `chat.headers` | Copilot `x-initiator` header injection |
| `event` | `event` | Session lifecycle (created/deleted/idle/error), openclaw dispatch, runtime fallback |
| `tool.execute.before` | `tool.execute.before` | Pre-tool guards (see §2) |
| `tool.execute.after` | `tool.execute.after` | Post-tool hooks (see §2) |
| `experimental.chat.messages.transform` | `experimental.chat.messages.transform` | Context injection, thinking/tool-pair validation, keyword detection |
| `experimental.session.compacting` | `experimental.session.compacting` | Context + todo preservation across compaction |

The `config` handler is the heart: it merges the plugin's components (agents, tools, MCPs, commands) into OpenCode's config object every time. Everything users see (11 agents, 26 tools, 3 MCPs, slash commands) is *added by the plugin via the `config` hook*, not loaded from a separate manifest.

### Config schema

`src/config/schema/` — 32 Zod v4 files. Top-level: `OhMyOpenCodeConfigSchema`.

- **File locations** (precedence: closer project wins → user → defaults):
  - Project: `.opencode/oh-my-openagent.json[c]` (legacy: `oh-my-opencode.json[c]`), walked from `pwd` up to `$HOME`
  - User: `~/.config/opencode/oh-my-openagent.json[c]` (mac/linux), `%APPDATA%\opencode\oh-my-openagent.json[c]` (Windows)
  - JSONC: comments + trailing commas
  - Schema URL: `https://raw.githubusercontent.com/code-yeongyu/oh-my-openagent/dev/assets/oh-my-opencode.schema.json`
- **Merge rules**: `agents`, `categories`, `claude_code` deep-merge; `disabled_*` arrays = set union; everything else override; `mcp_env_allowlist` is **user-only** for security
- **Fields** (excerpt): `agents` (11 overridable × 21 fields), `categories` (8 built-in + custom), `disabled_agents/hooks/mcps/skills/commands/tools` arrays, 19 feature configs (`background_task`, `tmux`, `git_master`, `comment_checker`, `notification`, `sisyphus_agent`, `sisyphus.tasks`, `team_mode`, `claude_code`, `runtime_fallback`, `model_capabilities`, `hashline_edit`, `experimental`, etc.)
- **CLI install**: `bunx oh-my-openagent install` is a TUI (Commander.js + `@clack/prompts`) that walks the user through provider/subscription choices and writes `opencode.json` + `~/.config/opencode/oh-my-openagent.jsonc`. Flags: `--platform=opencode|codex|both`, `--claude=yes|no|max20`, `--openai=`, `--gemini=`, `--copilot=`, `--opencode-zen=`, `--zai-coding-plan=`, `--opencode-go=`, `--kimi-for-coding=`, `--vercel-ai-gateway=`, `--codex-autonomous`, `--no-tui`, `--skip-auth`. Re-running is idempotent.

### What's a "plugin" vs "skill" vs "hook" vs "command"

| Concept | Format | Where it lives | What it adds | Who can add |
|---------|--------|----------------|--------------|-------------|
| **Plugin** | npm package with `PluginModule` default export | `node_modules/`, registered in `opencode.json` `plugin` array | Top-level agents, tools, MCPs, commands, hooks | Anyone (npm publish) |
| **Skill** | `SKILL.md` w/ YAML frontmatter | `.opencode/skills/`, `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/`, or `src/features/builtin-skills/` | On-demand prompt injection + embedded MCP servers + scoped tool permissions | Anyone (file drop) |
| **Hook** | TypeScript function returning event handlers | `src/hooks/{name}/`, registered in `src/plugin/hooks/create-*-hooks.ts` | Lifecycle interception (pre/post-tool, session, transform) | Contributors only (no public loader) — except via Claude Code `settings.json` compat |
| **Command** | Markdown template | `.opencode/commands/`, `~/.config/opencode/commands/`, `~/.claude/commands/`, or `src/features/builtin-commands/templates/` | `/slash-commands` (e.g. `/init-deep`, `/start-work`, `/ralph-loop`) | Anyone (file drop) |
| **Agent** | `createXXXAgent` factory | `src/agents/`, `src/agents/builtin-agents/` | Specialized persona with own model + prompt | Config override only for built-ins; new agents = contributors |

Claude Code "plugins" (the marketplace thing) are a separate axis: enabled via `claude_code.plugins` compat toggle. Per the config ref, `claude_code: { mcp, commands, skills, agents, hooks, plugins }` toggles each compat layer independently.

---

## 4. MCPs

**Three-tier architecture**, each tier with its own loader and lifecycle.

| Tier | Source | Loader | Mechanism |
|------|--------|--------|-----------|
| 1. Built-in | `src/mcp/` | `createBuiltinMcps()` (factory) | 3 remote HTTP, always on |
| 2. Claude Code | `.mcp.json` (project + user) | `claude-code-mcp-loader` (5 files) | stdio or HTTP, `${VAR}` and `${VAR:-default}` env expansion, allowlist via `mcp_env_allowlist` (user-only) |
| 3. Skill-embedded | `SKILL.md` YAML frontmatter + optional `mcp.json` | `SkillMcpManager` (10 files) | stdio or HTTP, per-session lifecycle keyed by `${sessionID}:${skillName}:${serverName}`, OAuth 2.0 + PKCE + Dynamic Client Registration (RFC 7591) |

### Built-in MCPs (always on unless disabled)

| Name | URL | Auth | Tools | Source |
|------|-----|------|-------|--------|
| `websearch` | `https://mcp.exa.ai/mcp` (default) or `https://mcp.tavily.com/mcp/` | Optional `EXA_API_KEY` or `TAVILY_API_KEY` | `websearch_web_search_exa` | `src/mcp/websearch.ts:11` |
| `context7` | `https://mcp.context7.com/mcp` | Optional `CONTEXT7_API_KEY` | `context7_resolve-library-id`, `context7_query-docs`, `context7_get-library-docs` | `src/mcp/context7.ts:1` |
| `grep_app` | `https://mcp.grep.app` | None | `grep_app_searchGitHub` (query, language, repo, useRegexp) | `src/mcp/grep-app.ts:1` |

Disable any of them via `disabled_mcps: ["websearch", "context7", "grep_app"]` in `oh-my-openagent.jsonc`. The config doc also lists `lsp` and `ast_grep` as built-ins (loaded via the `lsp` MCP server, configured by `.opencode/lsp.json`).

### Skill-embedded MCPs

A skill can ship its own MCP server. Two equivalent ways to declare it:

```yaml
# In SKILL.md frontmatter
mcpServers:
  my-server:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-postgres"]
    env: { DATABASE_URL: "${DATABASE_URL}" }
```

```json
// In a sibling mcp.json (no dot prefix — note: mcp.json not .mcp.json)
{
  "mcpServers": { "my-server": { "command": "npx", "args": ["..."] } }
}
```

`loadMcpJsonFromDir()` in `src/features/opencode-skill-loader/skill-mcp-config.ts:1` hardcodes `"mcp.json"` — flagged in issue #3021 as undocumented but the convention is now stable after the fix.

`SkillMcpManager` (per-session, per-skill) handles:
- stdio client (`stdio-client.ts`): `command`, `args`, `env`
- HTTP client (`http-client.ts`): `url`, `headers`, `oauth`
- OAuth handler (`oauth-handler.ts`): PKCE + DCR step-up
- Cleanup (`cleanup.ts`): `disconnectSession(sessionID)`, `disconnectAll()` on session end
- Env cleaner (`env-cleaner.ts`): strips dangerous env vars before passing to child processes

### User-facing install

1. **Built-ins**: zero install; toggle via `disabled_mcps`. Switch websearch provider via `websearch.provider: "exa" | "tavily"`.
2. **Claude Code MCPs**: drop a `.mcp.json` at project root (or `~/.claude/.mcp.json` for user). `${VAR}` env vars expand at load; add to `mcp_env_allowlist` (user-config only) to grant access.
3. **Skill-embedded**: create a skill folder with `SKILL.md` (frontmatter `mcpServers:`) and optionally a `mcp.json`. The skill's MCP starts on `skill` tool invocation and tears down on session end.
4. **OAuth tier-3**: `bunx oh-my-opencode mcp-oauth login <server-url>` and `mcp-oauth status`.
5. **Health check**: `bunx oh-my-opencode doctor` validates built-in connectivity, `.mcp.json` validity, env-var presence, and skill-MCP config (`src/cli/doctor/checks/tools-mcp.ts`).

### Tool permissions

Per-agent allow/deny for MCP tools via the standard OpenCode permission map:

```jsonc
{
  "agents": {
    "librarian": { "permission": { "grep_app_*": "allow", "websearch_*": "allow" } },
    "sisyphus":  { "permission": { "grep_app_*": false } }
  }
}
```

---

## Cross-references

- Repo: <https://github.com/code-yeongyu/oh-my-openagent> (npm: `oh-my-opencode`, alias `oh-my-openagent`)
- Docs: <https://code-yeongyu-oh-my-opencode.mintlify.app/>
- OpenCode native (for comparison): <https://opencode.ai/docs/skills>, <https://opencode.ai/docs/plugins>
- Relevant issues/PRs: #3021 (skill-mcp sessionID bug), #3560 (skill-loader shadowing native skills), #2980 (managed `file://` plugin registration)

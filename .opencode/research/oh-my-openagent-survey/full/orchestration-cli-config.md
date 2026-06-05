# oh-my-openagent — CLI & Configuration Survey

Repo: `code-yeongyu/oh-my-openagent` (renamed from `oh-my-opencode`, dual-published during transition). Installed via `bunx oh-my-openagent@latest install` or `npx oh-my-opencode install`. Versions surveyed: docs `dev` branch, latest npm `4.4.0–4.7.5` (May–Jun 2026).

> **Naming gotcha.** The published npm package and CLI binary are still named `oh-my-opencode`; `oh-my-openagent` is the new primary name (dual-published). The short alias `omo` ships in the package but the maintainer warns *not* to invoke `bunx omo` — that resolves to an unrelated npm package. A separate `lazycodex-ai` package is a thin alias to the Codex "Light" edition installer. Source: `docs/guide/installation.md:21-29`, `docs/reference/cli.md:9-13`.

---

## 1. CLI commands

The published CLI is a single compiled binary exposed under three bin entries (`docs/reference/cli.md:9-13`):

| Bin | Notes |
|---|---|
| `oh-my-opencode` | legacy primary |
| `oh-my-openagent` | renamed primary (preferred) |
| `omo` | short alias — **do not invoke directly** |
| `lazycodex-ai` | Codex-Light-only alias; defaults `--platform=codex` |

### 1.1 Command reference (Ultimate/OpenCode)

| Command | What it does | Source |
|---|---|---|
| `install` | Interactive TUI setup wizard (`@clack/prompts`). Walks the user through subscription flags, writes plugin registration, generates `oh-my-openagent.jsonc`/`.json` into the OpenCode config dir, prints `opencode auth login` hints. | `docs/reference/cli.md:46-89` |
| `uninstall` / `cleanup` | Removes managed Codex Light state (`~/.codex/plugins/cache/sisyphuslabs`, marketplace snapshot, hook-state, agent TOMLs). Reports project-owned artifacts but does not delete them. `--platform codex` required when invoked via the shared `omo` CLI. | `docs/reference/cli.md:91-110` |
| `doctor` | 6-category health check: **System** (binary ≥ 1.4.0, plugin reg), **Config** (JSONC + Zod), **TUI Plugin**, **Tools** (ast-grep, LSP, gh, comment-checker), **Models** (cache, per-agent resolution, fallback chain), **Team Mode**. Exit: `0` ok, `1` errors, `2` warnings. Flags: `--status`, `--verbose`, `--json`. | `docs/reference/cli.md:112-128`, `docs/guide/installation.md:287-288` |
| `run <message>` | Non-interactive OpenCode session runner. Exits only when all todos complete/cancel **and** all background child sessions are idle. Flags: `-a/--agent`, `-m/--model <provider/model>`, `-d/--directory`, `-p/--port`, `--attach <url>`, `--on-complete <cmd>`, `--json`, `--no-timestamp`, `--verbose`, `--session-id`. Agent resolution order: `--agent` → `OPENCODE_DEFAULT_AGENT` → `default_run_agent` in plugin config → `Sisyphus`. | `docs/reference/cli.md:130-167` |
| `get-local-version` | Prints installed plugin version + npm latest + update hint. Flags: `-d/--directory`, `--json`. | `docs/reference/cli.md:169-179` |
| `refresh-model-capabilities` | Refreshes local `models.dev` snapshot. Flags: `-d`, `--source-url`, `--json`. Configured via `model_capabilities.{enabled, auto_refresh_on_start, refresh_timeout_ms, source_url}`. | `docs/reference/cli.md:181-204` |
| `boulder` | Inspects Sisyphus `boulder.json` work-state (active plan, per-task timers, session lineage). | `docs/reference/cli.md:25-26` |
| `version` | Print CLI version. | `docs/reference/cli.md:206-212` |
| `mcp oauth <login\|logout\|status> [server-name]` | Tier-3 MCP OAuth flow with PKCE + Dynamic Client Registration. Flags: `--server-url` (required for login/logout), `--client-id`, `--scopes`. | `docs/reference/cli.md:214-238` |

All commands exit `0` on success, `1` on failure; `run`, `install`, `doctor`, `get-local-version`, `refresh-model-capabilities`, `mcp oauth` return explicit numeric codes (`docs/reference/cli.md:240-246`).

### 1.2 `install` flag matrix

`install` accepts these options (`docs/reference/cli.md:46-89`, `docs/guide/installation.md:189-194`):

| Flag | Allowed values | Effect |
|---|---|---|
| `--no-tui` | — | Non-interactive (requires all options supplied) |
| `--platform` | `opencode` (default), `codex`, `both` | Selects Ultimate vs Light |
| `--claude` | `no` / `yes` / `max20` | Anthropic subscription mode |
| `--openai` | `no` / `yes` | OpenAI/ChatGPT subscription |
| `--gemini` | `no` / `yes` | Gemini integration |
| `--copilot` | `no` / `yes` | GitHub Copilot subscription |
| `--opencode-zen` | `no` / `yes` | OpenCode Zen access |
| `--opencode-go` | `no` / `yes` | OpenCode Go (GLM-5.1, Kimi K2.5/K2.6, MiniMax) |
| `--zai-coding-plan` | `no` / `yes` | Z.ai Coding Plan |
| `--kimi-for-coding` | `no` / `yes` | Kimi for Coding |
| `--vercel-ai-gateway` | `no` / `yes` | Vercel AI Gateway |
| `--codex-autonomous` / `--no-codex-autonomous` | — | Sets Codex `approval_policy=never`, `sandbox_mode=danger-full-access`, `network_access=enabled` (Light only) |
| `--skip-auth` | — | Skip `opencode auth login` hints |

Subscription flags are **rejected** under `--platform=codex` (Light doesn't write OpenCode model config). Global installation (`npm i -g`, `bun add -g`) is *not* officially supported — always invoke via `bunx`/`npx` (`docs/guide/installation.md:74-78`).

### 1.3 Where the CLI is defined

The published package compiles a single CLI; the source is split across `src/cli/`, `src/commands/`, and `src/hooks/auto-update-checker/`. The npm `bin` field exposes `oh-my-opencode` / `oh-my-openagent` / `omo` / `lazycodex-ai` (per `package.json`, not fetched in this survey). The postinstall script (`postinstall.mjs`) validates the platform-binary package and the OpenCode version (see §5).

---

## 2. Configuration file

### 2.1 Locations & merge order

`docs/reference/configuration.md:21-43` defines the precedence:

```
<cwd up to $HOME>/.opencode/oh-my-openagent.json[c]   (walked, closer wins)
                ↓ merged onto
~/.config/opencode/oh-my-openagent.json[c]              (user)
                ↓ falls back to
defaults
```

- **macOS/Linux:** `~/.config/opencode/oh-my-openagent.json[c]` (legacy `oh-my-opencode.json[c]` still recognised).
- **Windows:** `%APPDATA%\opencode\oh-my-openagent.json[c]`.
- `.jsonc` is preferred over `.json` in the same directory.
- `mcp_env_allowlist` is **user-only**; walked configs cannot extend it.
- During the rename, detection checks `oh-my-opencode` before `oh-my-openagent`, so a legacy `oh-my-opencode.*` file wins if both exist.

Schema URL for editor autocomplete: `https://raw.githubusercontent.com/code-yeongyu/oh-my-openagent/dev/assets/oh-my-opencode.schema.json` (file is 100+ KB; see `assets/oh-my-opencode.schema.json`).

### 2.2 Merge rules (`docs/reference/configuration.md:319-329`)

| Field group | Rule |
|---|---|
| `agents`, `categories`, `claude_code` | Deep-merged recursively (prototype-pollution safe) |
| `disabled_*` arrays | Set union (concat + dedupe) |
| `mcp_env_allowlist` | User-only |
| Everything else | Override (replace) |

### 2.3 Top-level schema (built from `assets/oh-my-opencode.schema.json` + `docs/reference/configuration.md`)

| Key | Type | Purpose |
|---|---|---|
| `$schema` | string | URL for editor validation |
| `agents` | object | Override per-agent: `sisyphus`, `hephaestus`, `prometheus`, `oracle`, `librarian`, `explore`, `multimodal-looker`, `metis`, `momus`, `atlas`, `sisyphus-junior` |
| `categories` | object | Override task categories (`visual-engineering`, `ultrabrain`, `deep`, `artistry`, `quick`, `unspecified-low`, `unspecified-high`, `writing`) |
| `disabled_agents` / `disabled_mcps` / `disabled_skills` / `disabled_hooks` / `disabled_commands` / `disabled_tools` / `disabled_providers` | string[] | Disable built-ins |
| `agent_order` | string[] (≤64) | Tab cycling order; unknown/duplicate names ignored |
| `agent_definitions` | string[] | Extra agent definition file paths |
| `default_run_agent` | string | Default agent for `omo run` (resolution order in §1.1) |
| `background_task` | object | Concurrency controls (`defaultConcurrency`, `staleTimeoutMs`, `providerConcurrency`, `modelConcurrency`) |
| `sisyphus_agent` | object | Master switch (`disabled`, `default_builder_enabled`, `planner_enabled`, `replace_plan`) |
| `sisyphus.tasks` | object | Task storage (`storage_path`, `task_list_id`, `claude_code_compat`) |
| `team_mode` | object | Team Mode opt-in (`enabled`, `max_parallel_members` 1-8, `max_members` 1-8, `tmux_visualization`, timeouts) |
| `skills` | object | Custom skills (`sources`, `enable`, `disable`, per-skill config) |
| `model_capabilities` | object | `enabled`, `auto_refresh_on_start`, `refresh_timeout_ms`, `source_url` |
| `runtime_fallback` | bool\|object | API-error fallback switching (see §3) |
| `hashline_edit` | bool | Hash-anchored `edit` tool (`LINE#ID`) |
| `experimental` | object | `task_system`, `auto_resume`, `aggressive_truncation`, `dynamic_context_pruning`, etc. |
| `tmux` | object | Tmux pane layout for background agents |
| `git_master` | object | Commit footer / co-author toggles |
| `comment_checker` | object | `custom_prompt` (uses `{{comments}}` placeholder) |
| `notification` | object | `force_enable` |
| `browser_automation_engine` | object | `provider: playwright` (default) or `agent-browser` |
| `openclaw` | object | Outbound notification dispatchers (Discord/Telegram/HTTP/shell) |
| `mcp_env_allowlist` | string[] | Env-var names MCPs may read (user-only) |
| `new_task_system_enabled` | bool | Legacy alias for `experimental.task_system` |

Per-agent keys (from the schema): `model`, `fallback_models` (string|array of strings|objects), `variant`, `category`, `skills`, `temperature`, `top_p`, `prompt`, `prompt_append` (both accept `file://` URIs), `tools`, `disable`, `description`, `mode` (`subagent`/`primary`/`all`), `color`, `displayName`, `permission` (`edit`, `bash`, `webfetch`, `task`, `doom_loop`, `external_directory` — each `ask`/`allow`/`deny`), `maxTokens`, `thinking` (Anthropic extended thinking), `reasoningEffort`, `textVerbosity`, `providerOptions`, `ultrawork`, `compaction`, plus `allow_non_gpt_model` for `hephaestus`.

`disabled_skills` enum: `playwright`, `agent-browser`, `dev-browser`, `frontend-ui-ux`, `git-master`, `review-work`, `remove-ai-slops`, `init-deep`, `security-research`, `security-review`, `team-mode` (`assets/oh-my-opencode.schema.json:49-66`).
`disabled_commands` enum: `ralph-loop`, `ulw-loop`, `cancel-ralph`, `refactor`, `start-work`, `stop-continuation`, `remove-ai-slops`, `hyperplan` (`assets/oh-my-opencode.schema.json:91-103`).

---

## 3. Model provider setup

### 3.1 Authentication (Ultimate)

Provider auth runs through **OpenCode's own** `opencode auth login` flow, not a separate OmO command (`docs/guide/installation.md:225-262`):

```bash
opencode auth login
# Interactive: Provider → select e.g. Anthropic
# Interactive: Login method → Claude Pro/Max (OAuth) or API key
# Complete sign-in in browser
```

Per-provider notes:
- **Anthropic:** `opencode auth login` → Claude Pro/Max OAuth.
- **Google Gemini (Antigravity):** Add `opencode-antigravity-auth@latest` to `plugin` in `opencode.json`; supports up to 10 Google accounts with automatic load-balancing. Models use a `variant` system: `google/antigravity-gemini-3-pro` with `low`/`high`, etc. (`docs/guide/installation.md:234-249`).
- **GitHub Copilot:** Acts as a fallback provider; no special install, just `--copilot=yes` to the installer.
- **Z.ai / OpenCode Zen / OpenCode Go / Kimi / Vercel:** Selected via install-time subscription flags, then configured per their own `opencode` provider flow.

### 3.2 Model capability refresh

A bundled `models.dev` snapshot drives capability detection. Refresh via `bunx oh-my-openagent refresh-model-capabilities` (§1) or set `model_capabilities.auto_refresh_on_start: true` (`docs/reference/cli.md:181-204`, `docs/reference/configuration.md` §Model Capabilities).

### 3.3 Presets (default model families)

The install-time subscription interview produces per-agent provider chains documented in `docs/guide/installation.md:316-444`. Key examples:

| Agent | Default primary | Fallback chain (first hop → tail) |
|---|---|---|
| **Sisyphus** | `anthropic/claude-opus-4-7 (max)` | `opencode-go/kimi-k2.6` → `kimi-for-coding/k2p5` → `opencode\|moonshotai\|.../kimi-k2.5` → `openai\|github-copilot\|opencode/gpt-5.5 (medium)` → `zai-coding-plan\|opencode/glm-5` → `opencode/big-pickle` |
| **Hephaestus** | `openai/gpt-5.5 (medium)` | no fallback (GPT-native) |
| **Oracle** | `openai/gpt-5.5 (high)` | `google/gemini-3.1-pro (high)` → `anthropic/claude-opus-4-7 (max)` → `opencode-go/glm-5.1` |
| **Momus** | `openai/gpt-5.5 (xhigh)` | `anthropic/claude-opus-4-7 (max)` → `google/gemini-3.1-pro (high)` → `opencode-go/glm-5.1` |
| **Explore / Librarian** | `openai/gpt-5.4-mini-fast` | `opencode-go/qwen3.5-plus` → `vercel/minimax-m2.7-highspeed` → `opencode-go\|vercel/minimax-m3` → `opencode-go\|vercel/minimax-m2.7` → `anthropic\|vercel/claude-haiku-4-5` → `openai\|vercel/gpt-5.4-nano` |
| **Atlas** | `anthropic/claude-sonnet-4-6` | `opencode-go/kimi-k2.6` → `openai/gpt-5.5 (medium)` → `opencode-go/minimax-m3` → `opencode-go/minimax-m2.7` |

Categories route independently: `visual-engineering` → `gemini-3.1-pro (high)`, `ultrabrain` → `gpt-5.5 (xhigh)`, `writing` → `kimi-for-coding/k2p5`, etc. (`docs/reference/configuration.md` §Category Provider Chains).

### 3.4 Runtime fallback

```json
{
  "runtime_fallback": {
    "enabled": true,
    "retry_on_errors": [429, 500, 502, 503, 504],
    "max_fallback_attempts": 3,
    "cooldown_seconds": 60,
    "timeout_seconds": 30,
    "notify_on_fallback": true
  }
}
```

Default `retry_on_errors` is `[429, 500, 502, 503, 504]`; users on proxy APIs add `[400, 401, 403, 404]` for instant escalation (`docs/reference/configuration.md` §Runtime Fallback).

---

## 4. Telemetry

Anonymous telemetry is on by default, following the same opt-out posture as `cmux` (`docs/legal/privacy-policy.md:2-3`).

### 4.1 Events

| Event | Fired by | Reason | Trigger |
|---|---|---|---|
| `omo_daily_active` | Main plugin + `oh-my-openagent run` | n/a | Plugin loads or `run` invoked |
| `omo_codex_daily_active` | Codex Light adapter | `install_completed` / `session_start` | Installer finishes / Codex `SessionStart` hook |

Both fire **at most once per UTC day per machine** using a SHA-256-hashed installation identifier derived from the local hostname — the raw hostname is never transmitted (`docs/legal/privacy-policy.md:18-20`, `docs/reference/codex-telemetry.md:7-21`).

The Privacy Policy states the *main* plugin event is `oh_my_openagent_daily_active` (`docs/legal/privacy-policy.md:16`, `docs/guide/installation.md:530-538`), while the CLI reference uses `omo_daily_active` — likely a legacy name; the schema reference at the npm landing page confirms `oh_my_openagent_daily_active` (`docs/guide/installation.md:535`). The CLI-level alias may map to the same event.

### 4.2 Properties collected (Codex)

From `docs/reference/codex-telemetry.md:25-37`: `platform`, `product_name`, `package_name`, `package_version`, `runtime`, `runtime_version`, `source`, `reason`, `day_utc`, `$os`, `$os_version`, `os_arch`, `os_type`, `cpu_count`, `cpu_model`, `total_memory_gb`, `locale`, `timezone`, `shell`, `ci`, `terminal`, `$process_person_profile: false`. **Not** collected: prompt contents, chat transcripts, source files, repository contents, file paths, access tokens, API keys, raw hostnames, git remotes, usernames, emails, runtime error diagnostics.

### 4.3 Local state & opt-out

- **Main plugin dedup state:** stored in the OpenCode cache dir (`XDG_CACHE_HOME/opencode/` or `%LOCALAPPDATA%\opencode\`) per `src/hooks/auto-update-checker/constants.ts:11-19`.
- **Codex dedup state:** `$XDG_DATA_HOME/omo-codex/posthog-activity.json` (default `~/.local/share/omo-codex/posthog-activity.json`); stores `{"lastActiveDayUTC": "2026-06-03"}` (`docs/reference/codex-telemetry.md:39-49`).

**Opt-out env vars** (`docs/legal/privacy-policy.md:31-39`, `docs/reference/configuration.md` §Environment Variables):

| Var | Effect |
|---|---|
| `OMO_DISABLE_POSTHOG=1` | Disable **all** PostHog (main + Codex) |
| `OMO_SEND_ANONYMOUS_TELEMETRY=0` | Same as above |
| `OMO_CODEX_DISABLE_POSTHOG=1` | Disable only `omo_codex_daily_active` |
| `OMO_CODEX_SEND_ANONYMOUS_TELEMETRY=0` | Same as above |
| `POSTHOG_API_KEY` | Override project key |
| `POSTHOG_HOST` | Override ingestion host (default `https://us.i.posthog.com`) |

When disabled, "the PostHog client is a no-op and no telemetry network call is made" (`docs/reference/codex-telemetry.md:60-64`). Telemetry is best-effort: hook errors never block session startup.

PostHog is the only first-party analytics endpoint; npm and GitHub are listed for distribution only (`docs/legal/privacy-policy.md:42-46`).

---

## 5. Update mechanism

### 5.1 How the user upgrades

1. **Re-run install with the same flags.** `bunx oh-my-openagent@latest install --no-tui --platform=opencode --claude=yes ...` — the installer is **idempotent** (`docs/guide/installation.md:215-217`).
2. **Postinstall script detects stale state.** `postinstall.mjs` runs after every `npm install`:
   - Invariants cached: `MIN_OPENCODE_VERSION = "1.4.0"` (`postinstall.mjs:19`).
   - **Cache invalidation** (`postinstall.mjs:99-114`): removes any `~/.cache/opencode/oh-my-openagent@*` or `~/.cache/opencode/oh-my-opencode@*` directory, so OpenCode re-extracts the plugin tarball on next run.
   - **Platform-binary resolution** (`postinstall.mjs:127-139`): iterates candidates like `@oh-my-openagent/darwin-arm64`, `@oh-my-openagent/linux-x64-baseline`, etc. via `bin/platform.js:getPlatformPackageCandidates` and `getBinaryPath`.
   - **Version-mismatch detection** (`postinstall.mjs:140-150`): calls `bin/version-mismatch.ts:detectPlatformBinaryMismatch`; on mismatch prints:
     ```
     Fix: npm install -g oh-my-openagent@<mainVersion> @oh-my-openagent/<plat>@<mainVersion>
     ```
3. **In-session update check.** Hook `auto-update-checker` fires on `session.created`, fetches `https://registry.npmjs.org/-/package/oh-my-openagent/dist-tags` with a 5 s timeout, compares against installed version, and surfaces a startup toast (`src/hooks/auto-update-checker/constants.ts:1-7`, `AGENTS.md`). Cache is file-based in the OpenCode cache dir; `invalidatePackage()` purges bun.lock + node_modules + specifier cache when a forced refresh is needed.
4. **Channels:** `extractChannel()` maps dist-tags (`latest`, `next`, `beta`) and prerelease tags (`alpha`, `beta`, `rc`, `canary`, `next`) to per-channel throttles, so beta users don't get nagged to upgrade to `latest` (`src/hooks/auto-update-checker/version-channel.ts`).
5. **Manual check:** `bunx oh-my-openagent get-local-version` returns installed version + latest from npm + upgrade hint.

### 5.2 Codex (Light) upgrade

Re-run `npx lazycodex-ai install` — also idempotent, recomputes SHA256 hook trust hashes (`docs/guide/installation.md:84-89, 320-323`).

### 5.3 Detecting a stale install

- The `startup-toast` sub-feature of `auto-update-checker` shows a toast when npm latest > installed. Disable just the toast (keep the check) by adding `startup-toast` to `disabled_hooks` (`docs/reference/configuration.md` §Hooks).
- `postinstall.mjs` only *warns* — it does not abort — so a stale install survives but prints the version-mismatch fix command on next `npm install`.

---

## Source map

- CLI command list & flags — `docs/reference/cli.md`
- Config schema (machine) — `assets/oh-my-opencode.schema.json`
- Config reference (human) — `docs/reference/configuration.md`
- Install flow & provider setup — `docs/guide/installation.md`
- Telemetry details — `docs/reference/codex-telemetry.md`, `docs/legal/privacy-policy.md`
- Auto-update hook overview — `src/hooks/auto-update-checker/AGENTS.md`, `src/hooks/auto-update-checker/constants.ts`
- Postinstall / version check — `postinstall.mjs`
- npm package metadata — `https://www.npmjs.com/package/oh-my-openagent` (4.4.0–4.7.5, SUL-1.0 license, ~573k monthly downloads)

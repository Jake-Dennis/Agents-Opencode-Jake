# Jake's Opencode Agents — Knowledge Graph Edition

A collection of 13 specialized AI agents orchestrated by a **conductor**, backed by a persistent **graphify** knowledge graph. Drop into any project to get parallel multi-agent workflows with full audit trails.

## What is this?

This is a reusable `opencode.json` agent collection. It provides:

- **1 Conductor** — orchestrator that plans, dispatches, tracks, reviews, and documents
- **1 Planner** — read-only analysis (Tab-switchable primary)
- **11 subagents** — `builder`, `architect`, `reviewer`, `tester`, `docs`, `debugger`, `refactor`, `git`, `explorer`, `security`, `perf`
- **2 custom commands** — `/setup-project` (one-time init) and `/build` (run all plans)
- **graphify MCP** — persistent knowledge graph that survives across sessions

## Use in your own project

**Works on Windows, Mac, and Linux.** Choose your platform:

### Quick Start (all platforms)

```bash
# 1. Clone the repo
git clone https://github.com/Jake-Dennis/Agents-Opencode-Jake.git
cd Agents-Opencode-Jake

# 2. Run setup (choose your platform)
# Windows:
setup.bat
# Mac/Linux:
./setup.sh

# 3. Open in OpenCode
opencode .
/graphify .
```

**One command does it all:** copies AGENTS.md, merges the 13 agents into opencode.json, installs the pre-commit hook, creates .opencode structure, builds the knowledge graph.

The `/graphify` skill auto-refreshes whenever you re-run the installer.

For a **global install** (available in every project), use `global-setup.bat` (Windows) or `./global-setup.sh` (Mac/Linux). See [INSTALL.md](INSTALL.md) for the complete guide.

### Other scripts

| Script | Purpose |
|--------|---------|
| `setup.bat` / `setup.sh` | Install agents locally for this project |
| `uninstall.bat` / `uninstall.sh` | Remove local setup |
| `global-setup.bat` / `global-setup.sh` | Install agents globally — merges `opencode.json` into `~/.config/opencode/opencode.jsonc`, symlinks the skill. Supports `--unattended`, `--dry-run`, `--force`. |
| `uninstall-global.bat` / `uninstall-global.sh` | Surgically remove global install (uses install manifest). Supports `--unattended`, `--dry-run`. |

### Global install

`global-setup.bat` installs the *entire* project family into
`%USERPROFILE%\.config\opencode\opencode.jsonc` (idempotent merge) and
symlinks the `graphify-agent-workflow` skill — available to all opencode
projects on the machine. The merge covers every top-level key the
project ships:

- 13 agents (`agent.<name>`)
- 3 scalars (`default_agent`, `model`, `small_model`)
- `skills.paths` (union + dedupe)
- `instructions` (union + dedupe, plus the repo's `AGENTS.md`)
- `command` (slash commands like `/setup-project`, `/build`)
- `mcp` (graphify MCP server)
- `provider` + `enabled_providers` (project's AI provider config)
- `permission` (project's permission policy)
- `$schema` (the schema URL pointer)

The installer writes a manifest at
`%USERPROFILE%\.config\opencode\.opencode-jake-installed.json` so the
uninstaller can surgically remove every contribution and restore the
user's pre-install values for `provider` and `permission` from a
snapshot. See
[.opencode/plans/plan-003-full-global-install.md](.opencode/plans/plan-003-full-global-install.md)
for the full per-key policy.

Non-interactive: `global-setup.bat --unattended` or `set GLOBAL_SETUP_YES=1 && global-setup.bat`. Also supports `--dry-run` and `--force`.

### Auto-refresh graphify

Re-running `global-setup.bat` checks the pip version of `graphify` against the installed stamp at `~/.config/opencode/skills/graphify/.graphify_version`. When pip is ahead, it prompts `graphify A.B.C installed, pip has X.Y.Z. Refresh? (Y/n):` (default `Y`) and runs `pip install --user --upgrade graphifyy` followed by `python -m graphify install --platform opencode`. `--unattended` auto-upgrades; `--dry-run` previews without changes.

Verify: `opencode agent list` should show all 13 agents and `/help` should list `/setup-project` and `/build`. Undo: `uninstall-global.bat --unattended` (uses the install manifest for clean removal, preserves your other config).

### Option — copy `opencode.json` only

```bash
# In your project root:
cp /path/to/Agents-Opencode-Jake/opencode.json .
# Add the docs path to your opencode.json instructions:
#   "instructions": ["path/to/Agents-Opencode-Jake/AGENTS.md"]
```

## First-time setup (in any project)

Run `/setup-project` in opencode — it does everything:

1. Detects project type and language
2. Initializes git repo if missing
3. Runs `/graphify .` to build the knowledge graph
4. Creates `.opencode/` structure (plans, decisions, todo, work-log)
5. Creates a `.gitignore` (graphify-out, node_modules, .env, etc.)
6. Creates a starter `README.md` if missing

## Per-session resume

The conductor automatically checks `.opencode/todo.md` on startup and asks if you want to continue unfinished work.

## The conductor's 14-step workflow

1. **Clarify** — understand the request
2. **Graphify** — query the knowledge graph for context
3. **Plan** — break into dependency layers, save to `.opencode/plans/plan-NNN-title.md`
4. **Todo** — write checklist to todowrite + `.opencode/todo.md`
5. **Dispatch** — run independent tasks in parallel via `@mention`
6. **Track** — mark tasks in_progress / completed
7. **Review** — `@reviewer` checks every output
8. **Verify** — re-read plan, double-check every task against actual code/files/tests
9. **Archive** — move verified-complete plans to `.opencode/plans/completed/`
10. **Document** — work-log, ADRs, project docs, graphify rationale
11. **Sync todo** — persist unfinished work
12. **Graphify update** — `/graphify . --update`
13. **Git** — stage, draft commit, ask to push
14. **Report** — summary to user

## Documentation artifacts

| File | Purpose |
|---|---|
| `.opencode/work-log.md` | Append-only log of every work cycle |
| `.opencode/todo.md` | Persistent task checklist (cross-session) |
| `.opencode/jobs.md` | Live subagent progress tracking (auto-managed) |
| `.opencode/plans/plan-NNN-title.md` | Active implementation plans |
| `.opencode/plans/completed/plan-NNN-title.md` | Verified completed plans (history) |
| `.opencode/decisions/adr-NNN-title.md` | Architecture Decision Records |
| `.opencode/agents/<name>.md` | Externalized agent prompts |
| `graphify-out/` | Knowledge graph data (auto-managed) |

## Models

**No project-level model is set.** The `model` key is intentionally absent from `opencode.json` so that whatever model you select in the OpenCode UI at runtime is used for all agents. This avoids locking the project to a specific model that becomes stale.

Each agent has a `fallback_model` that's used if the primary is unavailable:

- **Fallback:** `opencode/deepseek-v4-flash-free` (all 13 agents)

To pin a specific model, add `"model": "provider/model-name"` to `opencode.json`. The test `test_all_agents_inherit_top_level_model` will then verify that any per-agent `model` overrides match the top-level key, and that `fallback_model` differs from the primary.

## Agent prompts

All 13 agent prompts are externalized to `.opencode/agents/<name>.md` files. The `opencode.json` registry references them via `{file:./.opencode/agents/<name>.md}`, keeping the config file scannable. Shared prompt sections (honesty, consult before acting, use your tools, live progress tracking) are inline in each `.md` file for now — a future improvement may extract them into shared includes.

## Commands

| Command | What it does |
|---|---|
| `/setup-project` | One-time project init: detect stack, git init, graphify build, create .opencode structure, .gitignore, README |
| `/build` | Execute ALL plans to completion in a loop: build, test, verify, archive |
| `/status` | Show current project status: active plans, tests, knowledge graph health, blocked items |

## Subagent cheat sheet

| `@agent` | When to use |
|---|---|
| `@builder` | Direct code implementation |
| `@architect` | System design, data models, API contracts |
| `@reviewer` | Code review, QA, quality check |
| `@tester` | Unit/integration/E2E test writing |
| `@docs` | Documentation, README, API docs |
| `@debugger` | Bug diagnosis and fixing |
| `@refactor` | Code cleanup, readability improvements |
| `@git` | Git operations, commits, PRs |
| `@explorer` | Fast read-only codebase search |
| `@security` | Vulnerability scanning, security audit |
| `@perf` | Performance profiling and optimization |

## Troubleshooting

- **Skill version mismatch warning** — re-run `global-setup.bat` (or `setup.bat`) to refresh the graphify skill + plugin. The installer auto-detects the mismatch and prompts to upgrade.

## License

MIT — see [LICENSE](LICENSE) for full text.

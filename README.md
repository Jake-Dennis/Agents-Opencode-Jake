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

### Option A — clone and symlink

```bash
git clone https://github.com/Jake-Dennis/Agents-Opencode-Jake.git
cd your-project

# On Windows — local setup (per-project)
setup.bat

# On Windows — global setup (all projects)
global-setup.bat

# On Windows — uninstall
uninstall.bat          # removes local setup
uninstall-global.bat   # removes global setup

# On macOS/Linux
#   mkdir -p .opencode
#   ln -s ../Agents-Opencode-Jake/.opencode/skills .opencode/skills
# Copy opencode.json into your project root
```

### Option B — use the `dist/` folder (easiest copy)

The `dist/` folder contains everything in one place — just copy it into your project:

```cmd
xcopy /E /I path\to\Agents-Opencode-Jake\dist\* your-project\
cd your-project
setup.bat
```

Then merge the `"agent"` block from `dist/opencode.json` into your project's config (or use it as-is). See `dist/README.md` for details.

### Option C — copy `opencode.json` only

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
| `.opencode/plans/plan-NNN-title.md` | Active implementation plans |
| `.opencode/plans/completed/plan-NNN-title.md` | Verified completed plans (history) |
| `.opencode/decisions/adr-NNN-title.md` | Architecture Decision Records |
| `graphify-out/` | Knowledge graph data (auto-managed) |

## Models

All agents use a fallback chain:

- **Primary:** `opencode/minimax-m3-free`
- **Fallback:** `opencode/big-pickle`

## Commands

| Command | What it does |
|---|---|
| `/setup-project` | One-time project init: detect stack, git init, graphify build, create .opencode structure, .gitignore, README |
| `/build` | Execute ALL plans to completion in a loop: build, test, verify, archive |

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

## License

MIT — see [LICENSE](LICENSE) for full text.

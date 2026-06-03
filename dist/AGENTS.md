# Jake's Opencode Agents — Knowledge Graph Edition

A collection of specialized agents orchestrated by a conductor, backed by a persistent knowledge graph (graphify).

## Quick start

```bash
# 1. Clone this repo into your project or symlink the agents
git clone https://github.com/JakeP/Agents-Opencode-Jake
cd your-project
opencode .
```

### First-time setup in any project

Run `/setup-project` — it does everything:
1. Detects project type and language
2. Initializes git repo if missing
3. Runs `/graphify .` to build the knowledge graph
4. Creates `.opencode/` structure (plans, decisions, todo, work-log)
5. Creates a `.gitignore` (graphify-out, node_modules, .env, etc.)
6. Creates a starter `README.md` if missing

### Per-session resume

The conductor automatically checks `.opencode/todo.md` on startup and asks if you want to continue unfinished work.

## Agents

### Primary (Tab-switchable)

| Agent | Default | Permission | Role |
|-------|---------|------------|------|
| `conductor` | Yes | Full | Orchestrator — plans, delegates, documents, commits |
| `planner` | Tab key | edit:deny | Planning-only, no code changes |

### Subagents (@mention)

| Agent | When to use |
|-------|-------------|
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

## Models

All agents use `opencode/deepseek-v4-flash-free` for both primary and fallback:

- **Model:** `opencode/deepseek-v4-flash-free`
- **Fallback:** `opencode/deepseek-v4-flash-free`
- **Reasoning effort:** `max` (set in `provider.opencode.options`)

## Commands

| Command | What it does |
|---------|-------------|
| `/setup-project` | One-time project init: detect stack, git init, graphify build, create .opencode structure, .gitignore, README |
| `/build` | Execute ALL plans to completion in a loop: build, test, verify, archive — never stops until every plan is done |

## Workflow

The conductor follows a 14-step workflow for every task:

1. **Clarify** — understand the request
2. **Graphify** — query the knowledge graph for context
3. **Plan** — break into dependency layers, save to `.opencode/plans/plan-NNN-title.md`
4. **Todo** — write checklist to todowrite + `.opencode/todo.md`
5. **Dispatch** — run independent tasks in parallel via @mention
6. **Track** — mark tasks in_progress / completed
7. **Review** — @reviewer checks every output
8. **Verify** — re-read plan, double-check every task against actual code/files/tests
9. **Archive** — move verified-complete plans to `.opencode/plans/completed/`
10. **Document** — work-log, ADRs, project docs, graphify rationale
11. **Sync todo** — persist unfinished work
12. **Graphify update** — `/graphify . --update`
13. **Git** — stage, draft commit, ask to push
14. **Report** — summary to user
15. **Resume** — check for unfinished work on next session start

## Documentation artifacts

| File | Purpose |
|------|---------|
| `.opencode/work-log.md` | Append-only log of every work cycle |
| `.opencode/todo.md` | Persistent task checklist (cross-session) |
| `.opencode/plans/plan-NNN-title.md` | Active implementation plans |
| `.opencode/plans/completed/plan-NNN-title.md` | Verified completed plans (history) |
| `.opencode/decisions/adr-NNN-title.md` | Architecture Decision Records |
| `graphify-out/` | Knowledge graph data (auto-managed) |

## Using in other projects

Add to your project's `opencode.json`:

```json
{
  "instructions": ["path/to/Agents-Opencode-Jake/AGENTS.md"]
}
```

Or copy/symlink the `.opencode/` directory into your project.

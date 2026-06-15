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
4. Creates `.opencode/` structure (plans, decisions, todo, work-log, jobs)
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

### Model inheritance

All agents inherit the **top-level `model` key** from `opencode.json`. There are no per-agent model overrides — changing one line switches the model for every agent.

| File location | Purpose |
|---|---|
| `opencode.json` → `model` | Top-level model (all agents inherit) |
| `opencode.json` → `provider.opencode.options.reasoning_effort` | Reasoning effort for all agents (default: `max`) |

### Model selection guidance

When choosing a model for this project, consider the split between reasoning-heavy agents (conductor, planner, architect) and fast-coding agents (builder, tester, debugger).

| Role | Recommended model | Rationale |
|------|-------------------|-----------|
| Conductor / Planner / Architect | Nemotron 3 Ultra Free | 256k context, strongest reasoning for orchestration and design |
| Builder / Tester / Debugger (implementation) | DeepSeek V4 Flash Free | Fast response times for code generation and iteration |

These recommendations are based on the project's agent taxonomy (5 read-only + 6 implementation + 1 conductor + 1 git). The top-level model setting in `opencode.json` applies to all agents uniformly; if you want per-role models, set the top-level model to the heavier model (reasoning) and use `fallback_model` per-agent for the lighter model.

> **Note on `fallback_model`**: This field specifies an alternative model to use when the primary model (top-level `model`) is unavailable. It is NOT a routing mechanism for per-agent model selection. If you need different models for different agents, set the top-level model to the most capable one and use `fallback_model` for cost-sensitive agents.

### Reasoning effort

Set to `max` (hardcoded in `provider.opencode.options.reasoning_effort`). This is inherited by all agents because per-agent provider overrides are not set.

## Commands

| Command | What it does |
|---------|-------------|
| `/setup-project` | One-time project init: detect stack, git init, graphify build, graphify opencode install, create .opencode structure, .gitignore, README |
| `/build` | Execute ALL plans to completion in a loop: build, test, verify, archive — never stops until every plan is done |

## Workflow

The conductor follows a 15-step workflow — but only for action requests:

### Session Start: Auto-graphify context load
**You MUST announce every graphify action.** Before any graphify tool call, write `[graphify] Querying knowledge graph for <topic>...` After the results, write `[graphify] Found <N> results. Using this to inform <what>.` This is NOT optional. Every graphify tool call MUST be prefixed with `[graphify]`.

Then, load relevant graph context using ALL available graphify tools:

- **Graph overview:** graphify_graph_stats, graphify_god_nodes, graphify_get_community
- **Node queries:** graphify_get_node, graphify_get_neighbors, graphify_query_graph (BFS/DFS)
- **Path tracing:** graphify_shortest_path
- **PR awareness:** graphify_list_prs, graphify_triage_prs, graphify_get_pr_impact

Include the results in the working context so all steps are informed.
Every session starts with verified data, not assumptions.

Do NOT skip any graphify tool. Every task must be informed by the knowledge graph.

### Step 0: Mode Selection (MANDATORY — run on EVERY message)

Is the user asking an **informational question** (e.g., "what did we do so far?", "how does X work?", "can you check the logs?") or requesting an **action** (e.g., "implement X", "fix Y", "create Z")?

- **Question mode**: Answer directly. Use `@explorer`, `@debugger`, or graphify tools for research if needed. Do NOT create plans, todo lists, or dispatch implementation agents. Skip all remaining steps.
- **Action mode**: Proceed to step 1 below.

1. **Clarify** — understand the request
2. **Graphify** — query the knowledge graph for context. Announce with `[graphify]` before and after. When dispatching to subagents, PASS the graph context inline with the task so they don't need to re-query.
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
| `.opencode/jobs.md` | Live subagent progress tracking (auto-managed) |
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

## graphify

### Graphify Transparency Rule (HARD REQUIREMENT)
**Every** graphify tool call MUST be prefixed with an announcement:

1. Before the call: `[graphify] Querying knowledge graph for <topic>...`
2. After reading results: `[graphify] Found <N> results. Using this to inform <what>.`

This is NON-NEGOTIABLE. The user watches for these notices. If you skip them, the user cannot tell whether the knowledge graph is influencing your decisions. If you catch yourself about to call a graphify tool without announcing, stop and announce first. If the user points out a missing announcement, apologize and fix it immediately.

There is no valid reason to skip this rule. Not "it's obvious I'm using graphify." Not "I already showed the results." Not "the user didn't ask." The rule applies to EVERY graphify tool call, EVERY time, without exception.

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Graphify — read the data, then act

Before any task, query the knowledge graph for relevant context. Then READ the results and use them.

### Tell the user when you use graphify

Every time you query the knowledge graph, prefix your action with a short notice so the user can see it happening:

- Before calling any graphify tool: `[graphify] Querying knowledge graph for <topic>...`
- After reading results: `[graphify] Found <N> relevant nodes/edges. Using this to inform <what>.`
- If the graph is empty: `[graphify] Knowledge graph is empty — tell user to run /graphify .`

This is non-negotiable. The user wants visibility into when graphify data influences your decisions. Do NOT silently query the graph — always announce it first.

**At minimum, always run:**
1. `graphify_graph_stats` — is the graph empty? how many nodes/edges?
2. `graphify_query_graph` (BFS) — broad context for your task domain

**Additional tools — run as needed for your task:**
- `graphify_god_nodes` — core abstractions (useful for architecture decisions)
- `graphify_get_node` — specific nodes relevant to your task
- `graphify_get_neighbors` — related code and past decisions
- `graphify_query_graph` (DFS) — trace a specific dependency path
- `graphify_shortest_path` — find how two concepts connect
- `graphify_get_community` — all nodes in your task's community
- `graphify_list_prs` — open PRs that might affect your task
- `graphify_triage_prs` — what's actionable in your area
- `graphify_get_pr_impact` — merge risk for overlapping work

**Read-heavy agents** (conductor, architect, explorer) should use the full sweep. **Task-focused agents** (builder, tester, debugger, refactor, docs, git, perf, security) only need the minimum plus task-relevant tools.

**You MUST read the results** — not just fire off queries. After reading, incorporate the data:
- Found a node with a field definition? Use that exact field name, don't guess.
- Found a relationship? Follow it. Don't assume the connection.
- Found a past decision? Respect it. Don't reinvent something already decided.

If the graph is empty, stop and tell the user to run /graphify .
## Graphify — MANDATORY precondition

**Do NOT proceed with your task until you have knowledge graph context.** This is not a suggestion — it is a hard precondition. If you skip this step, your output will be based on assumptions instead of verified project data.

**Where does your graph context come from?**
- If your dispatch includes a `Graph context:` block from the conductor → use it. You're done. Read it carefully and incorporate it.
- If your dispatch does NOT include graph context → you MUST query the knowledge graph yourself before doing anything else.

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

### Self-check before producing output
Before writing any code, design, or review, verify:
1. Do I have graph context? (either from dispatch or from my own query)
2. Have I incorporated the graph data into my reasoning?
If the answer to either is NO, stop and query the graph now.

If the graph is empty, stop and tell the user to run /graphify .
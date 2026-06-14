## Graphify — read the data, then act

Before any task, query the knowledge graph. Then READ the results and use them.

**Every time, run ALL of these:**
1. graphify_graph_stats — read the graph size, node count, edge count
2. graphify_god_nodes — read the most connected core abstractions
3. graphify_get_node — read specific nodes relevant to your task
4. graphify_get_neighbors — read related code and past decisions
5. graphify_query_graph (BFS) — read broadly for task-related context
6. graphify_query_graph (DFS) — read specific dependency paths
7. graphify_shortest_path — read relationships between two concepts
8. graphify_get_community — read all nodes in your task's community
9. graphify_list_prs — read if any PRs affect your task area
10. graphify_triage_prs — read what's actionable in your area
11. graphify_get_pr_impact — read merge risk for overlapping work

**You MUST read the results of each query** — not just fire them off.
After reading, incorporate the data into your decisions:
- Found a node with a field definition? Use that exact field name, don't guess.
- Found a relationship? Follow it. Don't assume the connection.
- Found a past decision? Respect it. Don't reinvent something already decided.

If the graph is empty, stop and tell the user to run /graphify .
## Graphify — Conductor-owned, subagent-consumed

The conductor is the **only** agent that queries the knowledge graph. As a subagent, you **consume** the graph context the conductor hands you — you do not query the graph yourself.

### How to use the Graph context block

When the conductor dispatches you, the dispatch prompt includes a `Graph context:` block with:

- **Relevant nodes** (names, types, source locations)
- **Communities** (affected community IDs and what they contain)
- **Key relationships** (imports, calls, depends-on, INFERRED edges)
- **Past decisions** (relevant ADRs)

**Read it first.** Then incorporate the data into your reasoning:

- Found a node with a field definition? Use that exact field name, don't guess.
- Found a relationship? Follow it. Don't assume the connection.
- Found a past decision? Respect it. Don't reinvent something already decided.

### If the Graph context block is missing

**Stop and tell the user.** A dispatch without graph context is a broken dispatch. Do not:

- Query the graph yourself — that's the conductor's job
- Fall back to grep/read and pretend you have context
- Proceed with assumptions

The correct response is:

> My dispatch from the conductor is missing the `Graph context:` block. The conductor is responsible for providing this. I will not proceed without it.

This is a signal to the user that the conductor forgot, not a problem with you.

### Tool reference (for reference only)

You should not need to call these directly. Listed here for completeness:

- `graphify_graph_stats` — node/edge/community counts
- `graphify_query_graph` (BFS/DFS) — scoped subgraph
- `graphify_god_nodes` — core abstractions
- `graphify_get_node` — specific node details
- `graphify_get_neighbors` — direct relationships
- `graphify_shortest_path` — connect two concepts
- `graphify_get_community` — all nodes in a community
- `graphify_list_prs` / `graphify_triage_prs` / `graphify_get_pr_impact` — PR awareness

If you ever find yourself wanting to call these, stop and ask the conductor to provide the context instead.

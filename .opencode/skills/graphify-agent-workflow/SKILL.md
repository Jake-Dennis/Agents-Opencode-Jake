---
name: graphify-agent-workflow
description: Auto-triggered when a conductor agent or subagent needs to query the knowledge graph before making changes. Use ONLY when graphify knowledge graph context is relevant to the current task.
---

# Graphify Agent Workflow

This skill activates when any agent needs to interact with the project's persistent knowledge graph.

## Querying the graph

Use the `graphify` MCP server tools to query the knowledge graph:

- `query_graph` — BFS traversal from relevant nodes (broad context)
- `get_node` — Get details about a specific node
- `get_neighbors` — Find connected nodes
- `get_community` — Get all nodes in a community
- `god_nodes` — Find the most connected nodes (key concepts)
- `shortest_path` — Find connections between two concepts
- `graph_stats` — Get graph overview statistics

## Updating the graph

After file changes, run `/graphify . --update` to incrementally extract new relationships from changed files. This is fast (no full re-scan) and captures newly discovered relationships.

## When a graph doesn't exist

If `graphify-out/graph.json` doesn't exist or is empty, suggest running `/graphify .` to build the initial graph. For fresh projects, this gives the agents a shared understanding of the codebase.

## Rationale nodes

When making architectural decisions, record them as rationale in the graph so future queries can reference why something was done a particular way.

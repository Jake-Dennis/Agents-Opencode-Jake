#!/usr/bin/env python3
"""Refine the graphify knowledge graph with schema-instance + value constraints.

Implements Plan 001 Layer 3 tasks #14 and #15:

* Task #14 — Schema-Instance Pattern
    - Create a template node ``AgentConfigSchema`` (file_type: ``rationale``,
      source_file: ``opencode.schema.json``).
    - Add 6 ``has_field`` edges: ``AgentConfigSchema`` -> each of the six
      schema fields (``description``, ``mode``, ``model``, ``fallback_model``,
      ``permission``, ``prompt``).
    - Add one ``instance_of`` edge per agent (13 total) connecting the agent's
      graph node to ``AgentConfigSchema``.

* Task #15 — Model Value Constraints
    - Create 3 value nodes: ``value_minimax_m3_free``, ``value_big_pickle``,
      ``value_opencode``.
    - For every agent, add a ``has_value_model`` edge (agent -> value) and a
      ``has_value_fallback_model`` edge (agent -> value), sourced from the
      actual ``model`` / ``fallback_model`` values in ``opencode.json``.

The script is idempotent: re-running it will not create duplicate nodes or
edges. After saving, it performs a verification BFS from ``value_big_pickle``
to confirm the new edges are queryable.

Usage::

    python scripts/refine-graph.py

The script does NOT re-run graphify clustering. The user can re-cluster
afterwards (e.g. with ``/graphify . --update``) to refresh community numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
GRAPH_PATH = REPO / "graphify-out" / "graph.json"
CFG_PATH = REPO / "opencode.json"

SCHEMA_SOURCE = "opencode.schema.json"
CONFIG_SOURCE = "opencode.json"

# The six fields defined by opencode.schema.json#/$defs/agentEntry
SCHEMA_FIELDS = ["description", "mode", "model", "fallback_model", "permission", "prompt"]

# value-string -> (node-id, node-label)
VALUE_NODES: dict[str, tuple[str, str]] = {
    "opencode/minimax-m3-free": ("value_minimax_m3_free", "opencode/minimax-m3-free"),
    "opencode/big-pickle":      ("value_big_pickle",      "opencode/big-pickle"),
    "opencode":                 ("value_opencode",        "opencode (provider)"),
}


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _find_field_node(graph: dict[str, Any], field: str) -> str | None:
    """Find the best graph node representing the given schema field.

    Preference order:
      1. ``agents_opencode_jake_opencode_schema_properties_<field>`` (the
         schema-extracted canonical field node).
      2. Any node whose ``label`` exactly matches ``field``.
    """
    canonical = f"agents_opencode_jake_opencode_schema_properties_{field}"
    for n in graph["nodes"]:
        if n["id"] == canonical:
            return canonical
    for n in graph["nodes"]:
        if n.get("label") == field:
            return n["id"]
    return None


def _find_agent_node(graph: dict[str, Any], agent_name: str) -> str | None:
    """Find the graph node for an agent.

    Looks for the canonical ``agents_opencode_jake_opencode_agent_<name>``
    node first, then falls back to any node whose label equals the agent name
    and whose file_type is ``code`` or ``rationale``.
    """
    canonical = f"agents_opencode_jake_opencode_agent_{agent_name}"
    for n in graph["nodes"]:
        if n["id"] == canonical:
            return canonical
    for n in graph["nodes"]:
        if (n.get("label") == agent_name
                and n.get("file_type") in ("code", "rationale")):
            return n["id"]
    return None


def _add_node(graph: dict[str, Any], *, node_id: str, label: str,
              source_file: str, community: int = 0) -> bool:
    """Add a new node if it does not already exist. Returns True if added."""
    if any(n["id"] == node_id for n in graph["nodes"]):
        print(f"  [skip] node {node_id!r} already exists")
        return False
    graph["nodes"].append({
        "id": node_id,
        "label": label,
        "file_type": "rationale",
        "source_file": source_file,
        "source_location": "L0",
        "community": community,
        "norm_label": label.lower(),
    })
    print(f"  [add]  node {node_id!r} (label={label!r})")
    return True


def _add_edge(graph: dict[str, Any], *, source: str, target: str,
              relation: str, confidence: str, confidence_score: float,
              source_file: str, source_location: str,
              weight: float = 1.0) -> bool:
    """Add a new edge if no edge with the same (source, target, relation) exists."""
    for e in graph["links"]:
        if (e["source"] == source and e["target"] == target
                and e["relation"] == relation):
            print(f"  [skip] edge {source!r} -[{relation}]-> {target!r} already exists")
            return False
    graph["links"].append({
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "source_file": source_file,
        "source_location": source_location,
        "weight": weight,
    })
    print(f"  [add]  edge {source!r} -[{relation}]-> {target!r}")
    return True


def _bfs_levels(graph: dict[str, Any], start_id: str, max_hops: int
                ) -> dict[int, list[str]]:
    """Undirected BFS from ``start_id`` up to ``max_hops`` depth.

    Returns ``{depth: [node_id, ...]}`` for depths 0..max_hops (missing depths
    mean the frontier was empty).
    """
    if start_id not in {n["id"] for n in graph["nodes"]}:
        raise KeyError(f"start_id {start_id!r} not in graph")

    # Build undirected adjacency (graph is small enough for in-memory)
    adj: dict[str, set[str]] = {n["id"]: set() for n in graph["nodes"]}
    for e in graph["links"]:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])

    levels: dict[int, list[str]] = {0: [start_id]}
    visited = {start_id}
    frontier = {start_id}
    for depth in range(1, max_hops + 1):
        new_frontier: set[str] = set()
        for node in frontier:
            for nb in adj.get(node, ()):
                if nb not in visited:
                    visited.add(nb)
                    new_frontier.add(nb)
        if not new_frontier:
            break
        levels[depth] = sorted(new_frontier)
        frontier = new_frontier
    return levels


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    print(f"Loading {GRAPH_PATH} ...")
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))

    n_nodes_before = len(graph["nodes"])
    n_edges_before = len(graph["links"])
    print(f"Before: {n_nodes_before} nodes, {n_edges_before} edges")
    print(f"  hyperedges: {len(graph.get('hyperedges', []))}")
    print(f"  communities referenced: "
          f"{len({n.get('community') for n in graph['nodes'] if n.get('community') is not None})}")

    # ── Task #14 — Schema-Instance Pattern ────────────────────────────────────
    print()
    print("=" * 70)
    print("Task #14 — Schema-Instance Pattern")
    print("=" * 70)

    print("\n[14.1] Creating AgentConfigSchema template node ...")
    _add_node(graph,
              node_id="AgentConfigSchema",
              label="AgentConfigSchema",
              source_file=SCHEMA_SOURCE,
              community=0)

    print("\n[14.2] Adding 6 has_field edges ...")
    fields_resolved = 0
    for field in SCHEMA_FIELDS:
        target = _find_field_node(graph, field)
        if target is None:
            print(f"  [warn] could not find a graph node for field {field!r}")
            continue
        _add_edge(graph,
                  source="AgentConfigSchema",
                  target=target,
                  relation="has_field",
                  confidence="INFERRED",
                  confidence_score=0.95,
                  source_file=SCHEMA_SOURCE,
                  source_location="$defs/agentEntry.properties",
                  weight=1.0)
        fields_resolved += 1
    print(f"  Resolved {fields_resolved}/{len(SCHEMA_FIELDS)} fields")

    print("\n[14.3] Adding 13 instance_of edges from each agent ...")
    agents = list(cfg["agent"].keys())
    agents_resolved = 0
    for agent_name in agents:
        agent_node = _find_agent_node(graph, agent_name)
        if agent_node is None:
            print(f"  [warn] could not find graph node for agent {agent_name!r}")
            continue
        _add_edge(graph,
                  source=agent_node,
                  target="AgentConfigSchema",
                  relation="instance_of",
                  confidence="INFERRED",
                  confidence_score=0.95,
                  source_file=SCHEMA_SOURCE,
                  source_location=f"agent.{agent_name}",
                  weight=1.0)
        agents_resolved += 1
    print(f"  Resolved {agents_resolved}/{len(agents)} agents")

    # ── Task #15 — Model Value Constraints ────────────────────────────────────
    print()
    print("=" * 70)
    print("Task #15 — Model Value Constraints")
    print("=" * 70)

    print("\n[15.1] Creating value nodes ...")
    for value_key, (nid, lbl) in VALUE_NODES.items():
        _add_node(graph,
                  node_id=nid,
                  label=lbl,
                  source_file=CONFIG_SOURCE,
                  community=0)

    print("\n[15.2] Adding has_value_model / has_value_fallback_model edges ...")
    value_edges = 0
    fallback_agents: list[str] = []
    for agent_name, agent_cfg in cfg["agent"].items():
        agent_node = _find_agent_node(graph, agent_name)
        if agent_node is None:
            print(f"  [warn] no graph node for agent {agent_name!r}, skipping value edges")
            continue

        model = agent_cfg.get("model")
        fallback = agent_cfg.get("fallback_model")

        if model in VALUE_NODES:
            vid, _ = VALUE_NODES[model]
            _add_edge(graph,
                      source=agent_node,
                      target=vid,
                      relation="has_value_model",
                      confidence="EXTRACTED",
                      confidence_score=1.0,
                      source_file=CONFIG_SOURCE,
                      source_location=f"agent.{agent_name}.model",
                      weight=1.0)
            value_edges += 1
        else:
            print(f"  [warn] model {model!r} for {agent_name!r} not in value map")

        if fallback in VALUE_NODES:
            vid, _ = VALUE_NODES[fallback]
            _add_edge(graph,
                      source=agent_node,
                      target=vid,
                      relation="has_value_fallback_model",
                      confidence="EXTRACTED",
                      confidence_score=1.0,
                      source_file=CONFIG_SOURCE,
                      source_location=f"agent.{agent_name}.fallback_model",
                      weight=1.0)
            value_edges += 1
            if vid == "value_big_pickle":
                fallback_agents.append(agent_name)
        else:
            print(f"  [warn] fallback {fallback!r} for {agent_name!r} not in value map")
    print(f"  Added {value_edges} value edges across {len(agents)} agents")

    # ── Save ──────────────────────────────────────────────────────────────────
    n_nodes_after = len(graph["nodes"])
    n_edges_after = len(graph["links"])
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Nodes:  {n_nodes_before:>4} -> {n_nodes_after:>4}  (delta = +{n_nodes_after - n_nodes_before})")
    print(f"Edges:  {n_edges_before:>4} -> {n_edges_after:>4}  (delta = +{n_edges_after - n_edges_before})")
    print(f"  Expected after re-cluster: 17 -> 7 communities (per plan 001)")

    print(f"\nWriting {GRAPH_PATH} ...")
    GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print("Done.")

    # ── Verification: BFS from value_big_pickle ───────────────────────────────
    print()
    print("=" * 70)
    print("Verification: BFS from value_big_pickle (depth 2)")
    print("=" * 70)
    levels = _bfs_levels(graph, "value_big_pickle", 2)
    for depth in sorted(levels.keys()):
        nodes = levels[depth]
        agent_like = [n for n in nodes if "_agent_" in n]
        print(f"\nDepth {depth}: {len(nodes)} nodes "
              f"({len(agent_like)} agent-nodes)")
        if depth == 1:
            for n in agent_like:
                label = next((x.get("label", "?") for x in graph["nodes"]
                              if x["id"] == n), "?")
                print(f"  - {n}  (label={label!r})")
            print(f"\n=> {len(agent_like)} agents reachable in 1 hop "
                  f"via has_value_fallback_model")

    return 0


if __name__ == "__main__":
    sys.exit(main())

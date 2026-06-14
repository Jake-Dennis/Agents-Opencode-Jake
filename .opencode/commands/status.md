---
description: Show current project status — active plans, completed plans, test results, knowledge graph health, and any blocked items.
---

Read the following files and report a structured status summary:

1. **Active plans:** List all `.md` files in `.opencode/plans/` that are NOT in `completed/`. For each, read the title and count incomplete tasks (`- [ ]` vs `- [x]`).
2. **Completed plans:** Count files in `.opencode/plans/completed/`.
3. **Work log:** Read the last 20 lines of `.opencode/work-log.md` for recent activity.
4. **Todo:** Read `.opencode/todo.md` for any unfinished items.
5. **Tests:** Run `python -m pytest tests/ --co -q` to list collected tests (no execution, just count). If the user asks, run `python -m pytest tests/ -v --tb=short` for full results.
6. **Knowledge graph:** Check if `graphify-out/graph.json` exists and report its size. If it exists, run `python -c "import json; g=json.load(open('graphify-out/graph.json')); print(f'Nodes: {len(g.get(\"nodes\", []))}, Edges: {len(g.get(\"edges\", []))}')"` to report node/edge counts.
7. **Blocked items:** Scan `.opencode/todo.md` for any lines containing "blocked", "deferred", or "upstream".

Output a structured summary in this format:

```
## Project Status

### Plans
- Active: N plans (list titles)
- Completed: N plans

### Tests
- Collected: N tests

### Knowledge Graph
- Nodes: N, Edges: N
- Size: XMb

### Blocked Items
- (list or "None")

### Recent Activity
- (last 3 work-log entries)
```
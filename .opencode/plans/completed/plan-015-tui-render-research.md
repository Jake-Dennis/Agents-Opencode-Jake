# TUI Render Research: jobs.md Live Progress in the OpenCode TUI

## Goal

Research how to render `.opencode/jobs.md` live-progress data in the OpenCode TUI (terminal UI that manages agents). The TUI currently shows agent chat history and files; adding a live-progress panel would give the user real-time visibility into subagent activity without switching to a separate editor tab.

## Current State

- OpenCode TUI (accessed via `opencode .`) shows: chat log, agent selector (tab), and file tree
- The TUI reads `opencode.json` for agent definitions
- `.opencode/jobs.md` contains structured entries with Status, Current step, and Sub-steps
- The jobs.md format is designed for machine readability: `## [<plan-id>] @<agent>` headers, key-value metadata

## Approach Options

### Option A: TUI Plugin / MCP Server

OpenCode supports MCP (Model Context Protocol) servers that can add panels to the TUI. An MCP server could:

1. Watch `.opencode/jobs.md` for changes (file watcher)
2. Parse entries and surface them as a panel
3. Show: agent name, status, current step, sub-steps

**Pros:** Non-invasive, aligns with OpenCode's architecture
**Cons:** Requires MCP server development, no documented TUI panel API yet

### Option B: Headless Renderer (CLI tool)

A CLI tool (`opencode-jobs`) that reads jobs.md and renders it to the terminal:

```
┌─────────────────────────────────────────────────────┐
│  Live Progress (2 dispatches active)                 │
├─────────────────────────────────────────────────────┤
│  plan-015 @builder - Add variant field...           │
│  ● complete  (2 min ago)  [✓✓✓]                     │
│                                                     │
│  plan-015 @tester - Hypothesis tests                 │
│  ◌ in_progress  (30s ago)  [✓✓∼]                    │
│  Current: Writing property test assertions           │
│                                                     │
│  3 archived entries today                              │
└─────────────────────────────────────────────────────┘
```

**Pros:** Simple, no TUI dependency, works in any terminal
**Cons:** Not integrated into the TUI session

### Option C: Markdown Preview Extension

Many editors (VS Code, etc.) support markdown preview with extensions. A custom previewer for `jobs.md` could:

- Render entries as cards
- Color-code status (green=complete, yellow=in_progress, red=failed)
- Collapse completed entries

**Pros:** Works with existing tools
**Cons:** Not OpenCode-specific

## Recommendation

**Start with Option C (Markdown preview enhancement)** and **Option B (CLI tool)** as a secondary output:

1. Create `scripts/jobs-status.py` — a CLI tool that outputs a terminal-friendly summary of jobs.md. This is useful immediately and requires no TUI API knowledge.
2. Enhance `jobs.md` with HTML comments or structured data that markdown previewers can render
3. Monitor OpenCode's MCP documentation for TUI panel APIs — when available, build Option A

## Implementation Sketch for jobs-status.py

```python
# scripts/jobs-status.py
import sys
from pathlib import Path
# Parse jobs.md entries
# Count by status
# Show each entry with agent, status, latest step
# Exit 2 if any entry has Status: failed
# Exit 1 if any entry has Status: in_progress for > 1 hour
# Exit 0 if all complete
```

## Open Questions

1. Does OpenCode's TUI support custom panels via MCP? (Current docs: MCP is for external tools, not TUI widgets)
2. Is there a `--watch` mode for jobs.md that could feed into a TUI refresh?
3. What's the priority: user-facing TUI or CI-pipeline visible status?

## References

- `.opencode/jobs.md` — live progress file
- `.opencode/plans/completed/plan-013-live-progress-tracking.md` — design doc
- OpenCode MCP documentation

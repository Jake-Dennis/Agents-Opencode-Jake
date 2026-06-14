---
description: Initialize a new project: build knowledge graph, create .opencode structure (plans, decisions, todo, work-log, jobs), init git, set up .gitignore
---

Run the project setup workflow: (1) detect project type and language, (2) initialize git repo if missing, (3) run /graphify . to build the knowledge graph, (4) run `graphify opencode install` to install the graphify plugin (AGENTS.md section + tool.execute.before hook), (5) create .opencode/plans/, .opencode/plans/completed/, .opencode/decisions/, .opencode/todo.md, .opencode/work-log.md, AND .opencode/jobs.md (the live-progress file for subagents — auto-managed, do not edit by hand) if they don't exist, (6) create a sensible .gitignore (including graphify-out/, node_modules/, .env, build artifacts, etc.), (7) create an initial README.md if missing with project name and setup instructions, (8) report the full setup summary to the user.

NOTE on the 3-file split (post-plan-013): `.opencode/todo.md` and `.opencode/work-log.md` are owned by the conductor agent; `.opencode/jobs.md` is owned by the 11 write-capable subagents. All three files are part of the standard `.opencode/` skeleton and must be created at setup time so the agents have a place to write.

---
description: Initialize a new project: build knowledge graph, create .opencode structure, init git, set up .gitignore
---

Run the project setup workflow: (1) detect project type and language, (2) initialize git repo if missing, (3) run /graphify . to build the knowledge graph, (4) create .opencode/plans/, .opencode/plans/completed/, .opencode/decisions/, .opencode/todo.md, .opencode/work-log.md if they don't exist, (5) create a sensible .gitignore (including graphify-out/, node_modules/, .env, build artifacts, etc.), (6) create an initial README.md if missing with project name and setup instructions, (7) report the full setup summary to the user.

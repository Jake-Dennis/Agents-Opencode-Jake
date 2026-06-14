## Project identity

This is the **Agents-Opencode-Jake** project — a collection of 13 specialized agents orchestrated by a conductor, backed by a persistent knowledge graph (graphify).

### Key facts
- **Language:** Python test suite (pytest 8.x), JSON config, Markdown prompts, Windows .bat installers
- **Config:** `opencode.json` is the single source of truth for agent definitions (13 agents)
- **Prompts:** All agent prompts are externalized to `.opencode/agents/<name>.md` with `{file:}` includes for shared sections
- **Shared sections:** `.opencode/agents/shared/` contains reusable prompt sections (honesty, consult, tools, graphify, etc.)
- **Tests:** ~201 tests using pytest. Naming convention: `test_T_XX_<description>` for structural tests, `test_<feature>` for integration tests
- **Run tests:** `python -m pytest tests/ -x -q --ignore=tests/test_agents_runtime.py`
- **Run a single test file:** `python -m pytest tests/test_X.py -v`
- **Run a single test:** `python -m pytest tests/test_X.py -v -k test_name`
- **Verification:** `python scripts/verify-plan.py <plan-file>` mechanically checks plans (7 checks)
- **Graphify:** Knowledge graph MCP at `graphify-out/graph.json` — always query before making changes
- **Install scripts:** 4 .bat files with tricky batch syntax (delayed expansion, `::` inside parens) — use the `batch-quoting` skill when editing
- **Test fixtures:** `conftest.py` provides `repo_path`, `cfg`, `schema`, `agent_names`, `conductor_prompt`
- **`{file:}` resolution:** Agent prompts use `{file:}` includes (e.g. `{file:./.opencode/agents/shared/honesty.md}`) that are resolved at runtime by opencode
- **Agent registry:** All 13 agents must stay in sync between `opencode.json`, `AGENT-ROLES.md`, and the `.opencode/agents/` prompt files. The agent-registry sync check (#7 in verify-plan.py) catches drift.

### Architecture
- **Conductor** dispatches all subagents via @mention — no subagent dispatches another subagent
- **Read-only agents** (planner, architect, reviewer, explorer, security) can only edit `.opencode/jobs.md`
- **Write agents** (builder, tester, debugger, refactor, perf, docs) can edit source files
- **Git agent** can only run `git *` bash commands
- **Knowledge graph** must be queried before every task — never assume, always verify with graphify tools
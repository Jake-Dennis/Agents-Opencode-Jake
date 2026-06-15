# Installation Guide

Complete installation instructions for Agents-Opencode-Jake on Windows, Mac, and Linux.

## What is Agents-Opencode-Jake?

A collection of 13 specialized AI agents (conductor, builder, debugger, tester, reviewer, etc.) orchestrated by a conductor, backed by a persistent knowledge graph (graphify). Install once globally, use in every project.

## Quick Start

### Prerequisites

All platforms need:
- **Python 3.10+** ([python.org](https://www.python.org/downloads/))
- **Git** ([git-scm.com](https://git-scm.com/downloads))
- **OpenCode CLI** — install via the official script:
  ```bash
  curl -fsSL https://opencode.ai/install | bash
  ```
- **uv** (recommended for Python package management):
  ```bash
  # Mac/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  
  # Windows (PowerShell)
  irm https://astral.sh/uv/install.ps1 | iex
  ```

### One-Time Global Install

**Windows (PowerShell or cmd):**
```cmd
cd C:\path\to\Agents-Opencode-Jake
global-setup.bat
```

**Mac/Linux (bash):**
```bash
cd /path/to/Agents-Opencode-Jake
./global-setup.sh
```

This installs:
- 13 agent .md files to `~/.config/opencode/agents/`
- 5 skill directories to `~/.config/opencode/skills/` (as symlinks)
- Merged configuration into `~/.config/opencode/opencode.jsonc`
- Graphify plugin and skill
- Manifest at `~/.config/opencode/.opencode-jake-installed.json`

**Non-interactive mode:**
```bash
# Windows
global-setup.bat --unattended

# Mac/Linux
./global-setup.sh --unattended
```

**Dry run (preview without changes):**
```bash
# Windows
global-setup.bat --dry-run

# Mac/Linux
./global-setup.sh --dry-run
```

### Verify Install

```bash
opencode agent list
```

You should see all 13 agents: architect, builder, conductor, debugger, docs, explorer, git, perf, planner, refactor, reviewer, security, tester.

## Platform-Specific Notes

### Windows

- **Python:** Use `python` (not `python3`) — Windows doesn't have `python3` by default
- **Permissions:** No admin needed — `global-setup.bat` works without elevation
- **Symlinks:** Uses NTFS junctions (no admin required)
- **Line endings:** Scripts handle CRLF/LF automatically

### Mac

- **Python:** Use `python3` (Mac ships with Python 2 as `python`)
- **Permissions:** No sudo needed — installs to `~/.config/opencode/`
- **Symlinks:** Native Unix symlinks via `ln -s`
- **Shell:** Tested with bash 3.2+ (default on macOS)

### Linux

- **Python:** Use `python3` (most distros ship with Python 3)
- **Permissions:** No sudo needed — installs to `~/.config/opencode/`
- **Symlinks:** Native Unix symlinks via `ln -s`
- **Distros tested:** Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch (current)

## Per-Project Setup

If you want to install into a specific project (not globally), use `setup.sh` / `setup.bat`:

```bash
# From the project directory
/path/to/Agents-Opencode-Jake/setup.sh

# Or with global-setup already done, just add the graph
opencode .
/graphify .
```

## Use the Agents in Any Project (self-contained bundle)

The agent prompts are designed to be **fully portable**. Each agent's `.md` file is a single self-contained unit — no broken `{file:...}` references, no missing dependencies.

The agents detect their environment on every session start and operate in one of two modes:

| Mode | When | Behavior |
|---|---|---|
| **Dispatch mode** | env exposes a `task` / `delegate` / `@mention` tool | Conductor dispatches to real subagents in parallel; subagent boundaries are a hard contract |
| **Single-agent mode** | no dispatch tool detected | Conductor plays all roles (builder, reviewer, tester, etc.) sequentially using the subagent `.md` files as checklists; honest self-review |

The conductor announces its mode in the first response, so the user always knows what to expect.

### Option A: Use the pre-built bundle (easiest)

The `dist/agents/` directory contains 13 self-contained agent files plus a `MANIFEST.md`. Copy them to your target project:

```bash
# Build the bundle (idempotent)
python scripts/build-self-contained-bundle.py

# Copy what you need
cp dist/agents/conductor.md /path/to/your/project/.opencode/agents/
cp dist/agents/builder.md    /path/to/your/project/.opencode/agents/
# ... or copy all 13:
cp -r dist/agents/*.md /path/to/your/project/.opencode/agents/
```

This works in any opencode build, any AI client that reads `.md` agent prompts, and any environment. No `global-setup` required, no graphify required, no skill symlinks required.

### Option B: Use global-setup (full feature set)

The standard `global-setup.sh` / `global-setup.bat` install also produces self-contained agents (via `resolve_includes.py`) and adds the graphify skill, plugin, and merged config. Use this when you want the full knowledge-graph-backed workflow.

### Verifying a bundle install

The 5 tests in `tests/test_bundle.py` assert:
- The bundle script exists
- All 13 agents are produced
- Each bundled file has zero remaining `{file:...}` references
- The bundle includes a `MANIFEST.md`
- Each bundled file is strictly larger than its source (proves inlining happened)

Run: `python -m pytest tests/test_bundle.py -v`

## Building the Knowledge Graph

After install, build the knowledge graph for your project:

```bash
opencode .
/graphify .
```

This creates `graphify-out/` with:
- `graph.html` — interactive visualization
- `GRAPH_REPORT.md` — audit report
- `graph.json` — raw graph data

The knowledge graph enables 71.5x token reduction when querying the codebase (vs reading raw files).

## Uninstall

**Global uninstall:**
```bash
# Windows
uninstall-global.bat

# Mac/Linux
./uninstall-global.sh
```

**Per-project uninstall:**
```bash
# Windows
uninstall.bat

# Mac/Linux
./uninstall.sh
```

Both are surgical — they only remove what was installed, preserving your other config.

## Updating

To update to the latest version:

```bash
cd /path/to/Agents-Opencode-Jake
git pull

# Re-run the installer (idempotent)
./global-setup.sh  # or global-setup.bat on Windows
```

The installer detects version mismatches and auto-upgrades graphify.

## Troubleshooting

### Python not found

```bash
# Check Python version
python3 --version  # Mac/Linux
python --version   # Windows

# Install if missing
# Mac: brew install python@3.12
# Linux: sudo apt install python3 python3-pip
# Windows: download from python.org
```

### Permission denied on Mac/Linux

```bash
# Make scripts executable
chmod +x global-setup.sh uninstall-global.sh setup.sh uninstall.sh

# If ~/.config/opencode/ has permission issues
chmod -R u+rw ~/.config/opencode/
```

### Symlink fails on Windows

Windows requires admin privileges for symlinks, but `global-setup.bat` uses NTFS junctions which don't need admin. If junctions fail, the script falls back to copying.

### Graphify MCP not starting

The graphify Python package must be importable. The installer auto-installs it, but you can install manually:

```bash
uv tool install graphifyy
# or
pip install --user graphifyy
```

Then verify:
```bash
python -c "import graphify; print(graphify.__version__)"
```

### Agents not showing up

1. Check the manifest exists: `ls ~/.config/opencode/.opencode-jake-installed.json`
2. Verify agents are installed: `ls ~/.config/opencode/agents/`
3. Re-run the installer (idempotent)
4. Check OpenCode version: `opencode --version`

### More help

- [OpenCode docs](https://opencode.ai/docs)
- [Graphify docs](https://github.com/safishamsi/graphify)
- [GitHub issues](https://github.com/JakeP/Agents-Opencode-Jake/issues)

## Advanced

### Custom install location

Set `OPENCODE_CONFIG_DIR` environment variable to use a different config directory:

```bash
export OPENCODE_CONFIG_DIR="$HOME/.my-opencode-config"
./global-setup.sh
```

### Multiple machines

The installer is idempotent — safe to run on multiple machines. Each machine gets its own `~/.config/opencode/` install. Use the same git clone on each machine.

### CI/CD

Add to your CI pipeline:

```yaml
# GitHub Actions example
- name: Install Agents-Opencode-Jake
  run: |
    git clone https://github.com/JakeP/Agents-Opencode-Jake
    cd Agents-Opencode-Jake
    ./global-setup.sh --unattended
```

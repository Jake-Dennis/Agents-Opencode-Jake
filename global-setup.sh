#!/bin/bash
# Agents-Opencode-Jake — Global Installer (Mac/Linux)
# Ported from global-setup.bat — same logic, Unix idioms

set -e

# --- Parse flags ---
UNATTENDED=""
DRY_RUN=""
FORCE=""

for arg in "$@"; do
    case "$arg" in
        --unattended) UNATTENDED=1 ;;
        --dry-run)    DRY_RUN=1 ;;
        --force)      FORCE=1 ;;
    esac
done

[ "$GLOBAL_SETUP_YES" = "1" ] && UNATTENDED=1
[ "$GLOBAL_SETUP_DRY_RUN" = "1" ] && DRY_RUN=1
[ "$GLOBAL_SETUP_FORCE" = "1" ] && FORCE=1

# --- Paths ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/opencode"
AGENTS_DIR="$CONFIG_DIR/agents"
SKILLS_DIR="$CONFIG_DIR/skills"
GLOBAL_CONFIG="$CONFIG_DIR/opencode.jsonc"
MANIFEST="$CONFIG_DIR/.opencode-jake-installed.json"
PROJECT_CONFIG="$REPO_DIR/opencode.json"
MERGE_HELPER="$REPO_DIR/.opencode/scripts/opencode_jsonc_merge.py"

# --- Resolve Python ---
PY=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$(command -v "$candidate")"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "  [ERROR] Python not found. Please install Python 3.10+ or set PATH."
    exit 5
fi

echo "============================================"
echo " Agents-Opencode-Jake — Global Installer"
echo "============================================"
echo
echo "  Repo:    $REPO_DIR"
echo "  Config:  $CONFIG_DIR"
echo
echo "  WARNING: This installs agents and skills globally"
echo "  for ALL opencode projects on this machine."
echo "  Run setup.sh instead for local/per-project setup."
[ "$DRY_RUN" = "1" ] && echo "  [DRY-RUN] no files will be written."
[ "$FORCE" = "1" ] && echo "  [FORCE]   existing agent entries will be overwritten."
echo

# --- Confirmation prompt ---
if [ "$UNATTENDED" = "1" ]; then
    echo "  [UNATTENDED] proceeding without prompt."
    echo
else
    read -p "  Continue with global install? (y/N): " CONFIRM
    if [ "$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')" != "y" ]; then
        echo "  Aborted."
        exit 0
    fi
    echo
fi

# ---- Step 1: Ensure config directories exist ----
echo "[1/5] Ensuring global config directories exist..."
mkdir -p "$AGENTS_DIR" "$SKILLS_DIR"
echo "  Dirs: $AGENTS_DIR, $SKILLS_DIR"
echo

# ---- Step 2: Agent files (copy directly) ----
echo "[2/5] Copying agent files..."
AGENT_MD_COUNT=$(find "$REPO_DIR/.opencode/agents" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
HAS_AGENT_KEY=0
if grep -q '"agent":' "$PROJECT_CONFIG" 2>/dev/null; then
    HAS_AGENT_KEY=1
fi

if [ "$AGENT_MD_COUNT" -gt 0 ]; then
    # Remove any existing junction or stale files
    if [ -d "$AGENTS_DIR/Agents-Opencode-Jake" ]; then
        rm -rf "$AGENTS_DIR/Agents-Opencode-Jake"
    fi
    # Remove stale .md files from previous installs
    find "$AGENTS_DIR" -maxdepth 1 -name "*.md" -type f -delete 2>/dev/null
    if [ -d "$AGENTS_DIR/shared" ]; then
        rm -rf "$AGENTS_DIR/shared"
    fi
    # Copy only the agent .md files (not shared/)
    AGENT_MD_COUNT=0
    for src_file in "$REPO_DIR/.opencode/agents"/*.md; do
        if [ -f "$src_file" ]; then
            cp "$src_file" "$AGENTS_DIR/$(basename "$src_file")"
            AGENT_MD_COUNT=$((AGENT_MD_COUNT + 1))
        fi
    done
    echo "  [OK] copied $AGENT_MD_COUNT agent .md files to $AGENTS_DIR"
    # Resolve {file:} includes
    if [ -f "$REPO_DIR/.opencode/scripts/resolve_includes.py" ]; then
        if "$PY" "$REPO_DIR/.opencode/scripts/resolve_includes.py" "$AGENTS_DIR" "$AGENTS_DIR" --repo-root "$REPO_DIR" >/dev/null 2>&1; then
            echo "  [OK] resolved shared includes for all agents"
        else
            echo "  [WARN] include resolution returned error"
        fi
    else
        echo "  [WARN] resolve_includes.py not found — agents may not work in other projects"
    fi
    AGENT_J_RESULT="copied"
elif [ "$HAS_AGENT_KEY" = "1" ]; then
    echo "  [INFO] No .opencode/agents/*.md files — agents are in opencode.json,"
    echo "         will merge into global config."
    AGENT_J_RESULT="skip"
else
    echo "  [ERROR] Nothing to install. Repo has no .opencode/agents/*.md files"
    echo "           and no \"agent\": key in opencode.json."
    exit 1
fi
echo

# ---- Step 3: Skill symlinks ----
echo "[3/5] Skill symlinks..."
SKILL_COUNT=0
for skill_dir in "$REPO_DIR/.opencode/skills"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        link_path="$SKILLS_DIR/$skill_name"
        # Remove existing symlink or directory
        if [ -L "$link_path" ] || [ -d "$link_path" ]; then
            rm -rf "$link_path"
        fi
        if ln -s "$skill_dir" "$link_path" 2>/dev/null; then
            echo "  [OK] skill symlink: $link_path -> $skill_dir"
        else
            echo "  [WARN] skill symlink failed, copying instead..."
            cp -R "$skill_dir" "$link_path"
            echo "  [OK] skill copied: $link_path"
        fi
        SKILL_COUNT=$((SKILL_COUNT + 1))
    fi
done
[ "$SKILL_COUNT" = "0" ] && echo "  [INFO] No skill directories to link"
echo

# ---- Step 4a: Ensure graphify is installed ----
echo "[4a/5] Checking graphify Python package..."
if "$PY" -c "import graphify" >/dev/null 2>&1; then
    echo "  [OK] graphify importable by $PY"
else
    echo "  [INSTALL] graphify not importable; running pip install --user graphifyy"
    "$PY" -m pip install --user graphifyy 2>&1 | grep -v "already satisfied" | grep -v "^$" || true
    if "$PY" -c "import graphify" >/dev/null 2>&1; then
        echo "  [OK] graphify installed"
    else
        echo "  [FALLBACK] trying pip install --user --force-reinstall graphifyy"
        "$PY" -m pip install --user --force-reinstall graphifyy 2>&1 | grep -v "already satisfied" | grep -v "^$" || true
        if "$PY" -c "import graphify" >/dev/null 2>&1; then
            echo "  [OK] graphify installed via --force-reinstall"
        else
            echo "  [WARN] graphify install failed. The MCP config in your global"
            echo "         opencode.jsonc references graphify, but the package is"
            echo "         not importable. Run manually: pip install --user --force-reinstall graphifyy"
        fi
    fi
fi
echo

# ---- Step 4b: Refresh graphify skill + plugin ----
echo "[4b/5] Checking graphify version..."
REFRESH_HELPER="$REPO_DIR/.opencode/scripts/graphify_refresh.py"
if [ ! -f "$REFRESH_HELPER" ]; then
    echo "  [WARN] refresh helper not found: $REFRESH_HELPER"
else
    REFRESH_ARGS="--stamp-path $CONFIG_DIR/skills/graphify/.graphify_version"
    [ "$UNATTENDED" = "1" ] && REFRESH_ARGS="$REFRESH_ARGS --unattended"
    [ "$DRY_RUN" = "1" ] && REFRESH_ARGS="$REFRESH_ARGS --dry-run"
    [ "$FORCE" = "1" ] && REFRESH_ARGS="$REFRESH_ARGS --yes"
    "$PY" "$REFRESH_HELPER" $REFRESH_ARGS || echo "  [WARN] graphify version check returned non-zero; install continues."
fi
echo

# ---- Step 4: Merge into global opencode.jsonc ----
echo "[4/5] Merging into global opencode.jsonc..."
echo "  Python: $PY"

if [ ! -f "$MERGE_HELPER" ]; then
    echo "  [ERROR] Merge helper not found: $MERGE_HELPER"
    exit 6
fi

MERGE_ARGS="install --project $PROJECT_CONFIG --global $GLOBAL_CONFIG --manifest $MANIFEST"
[ "$FORCE" = "1" ] && MERGE_ARGS="$MERGE_ARGS --force"
[ "$DRY_RUN" = "1" ] && MERGE_ARGS="$MERGE_ARGS --dry-run"

if [ "$DRY_RUN" = "1" ]; then
    echo "  [DRY-RUN] would run:"
    echo "    $PY $MERGE_HELPER $MERGE_ARGS"
fi
"$PY" "$MERGE_HELPER" $MERGE_ARGS
MERGE_RC=$?
if [ "$MERGE_RC" != "0" ]; then
    echo "  [ERROR] merge helper failed with exit code $MERGE_RC"
    exit $MERGE_RC
fi
echo

# ---- Step 4c: Fix {file:...} paths ----
echo "[4c/5] Fixing agent file references for global config..."
if [ "$AGENT_J_RESULT" = "copied" ]; then
    "$PY" -c "
import sys
path = r'$GLOBAL_CONFIG'
with open(path, encoding='utf-8') as f:
    content = f.read()
content = content.replace('{file:./.opencode/agents/', '{file:./agents/')
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('  [OK] paths rewritten')
"
else
    echo "  [SKIP] agent files not available, paths left as-is"
fi
echo

# ---- Step 4d: Sync commands ----
CMD_COUNT=$(find "$REPO_DIR/.opencode/commands" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
if [ "$CMD_COUNT" -gt 0 ]; then
    echo "[4d/5] Syncing commands to global config..."
    "$PY" "$REPO_DIR/.opencode/scripts/sync_commands.py" "$REPO_DIR" "$GLOBAL_CONFIG" || true
    echo
fi

# ---- Step 4e: Copy skill files if symlink failed ----
echo "[4e/5] Verifying skill symlinks..."
for skill_dir in "$REPO_DIR/.opencode/skills"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        link_path="$SKILLS_DIR/$skill_name"
        if [ ! -f "$link_path/SKILL.md" ] && [ -f "$skill_dir/SKILL.md" ]; then
            echo "  Copying skill $skill_name..."
            rm -rf "$link_path"
            cp -R "$skill_dir" "$link_path"
        fi
    fi
done

# ---- Step 4f: Install graphify OpenCode plugin ----
echo "[4f/5] Installing graphify OpenCode plugin..."
if command -v graphify >/dev/null 2>&1; then
    if graphify opencode install >/dev/null 2>&1; then
        echo "  [OK] graphify plugin installed (AGENTS.md + tool.execute.before hook)"
    else
        echo "  [WARN] graphify opencode install failed — run it manually"
    fi
else
    echo "  [SKIP] graphify CLI not found — run 'uv tool install graphifyy' first"
fi
echo

# ---- Step 5: Final summary ----
echo "[5/5] Summary"
echo "============================================"
echo "  Global install complete!"
echo "============================================"
echo
if [ "$AGENT_J_RESULT" = "copied" ]; then
    echo "  Agents copied:     $AGENTS_DIR/ (13 agent .md files)"
    echo "                       Re-run global-setup.sh to refresh."
else
    echo "  Agents merged into: $GLOBAL_CONFIG"
fi
echo "  Skills linked: $SKILLS_DIR/graphify-agent-workflow"
echo "  Manifest:      $MANIFEST"
echo
echo "  Start using:  opencode ."
echo "  Verify:        opencode agent list"
echo "  Reinstall:     run global-setup.sh again (idempotent)"
echo "  Uninstall:     run uninstall-global.sh"
echo
exit 0

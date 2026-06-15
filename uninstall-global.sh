#!/bin/bash
# Agents-Opencode-Jake — Global Uninstaller (Mac/Linux)
# Ported from uninstall-global.bat

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

# --- Paths ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/opencode"
AGENTS_DIR="$CONFIG_DIR/agents"
SKILLS_DIR="$CONFIG_DIR/skills"
GLOBAL_CONFIG="$CONFIG_DIR/opencode.jsonc"
MANIFEST="$CONFIG_DIR/.opencode-jake-installed.json"
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
echo " Agents-Opencode-Jake — Global Uninstall"
echo "============================================"
echo
echo "  This will REMOVE Agents-Opencode-Jake from your"
echo "  global opencode configuration."
echo
echo "  Repo:   $REPO_DIR"
echo "  Config: $CONFIG_DIR"
echo
echo "  WARNING: This affects ALL opencode projects on this machine."
[ "$DRY_RUN" = "1" ] && echo "  [DRY-RUN] no files will be modified."
[ "$FORCE" = "1" ] && echo "  [FORCE]   removing symlinks even without a manifest."
echo

# --- Confirmation prompt ---
if [ "$UNATTENDED" = "1" ]; then
    echo "  [UNATTENDED] proceeding without prompt."
    echo
else
    read -p "  Continue with global uninstall? (y/N): " CONFIRM
    if [ "$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')" != "y" ]; then
        echo "  Aborted."
        exit 0
    fi
    echo
fi

# --- Check if installed ---
if [ ! -f "$MANIFEST" ] && [ "$FORCE" != "1" ]; then
    echo "  [INFO] No install manifest found at $MANIFEST"
    echo "         Nothing to uninstall. Use --force to remove symlinks anyway."
    exit 0
fi

# ---- Step 1: Remove agents ----
echo "[1/4] Removing agent files..."
if [ -d "$AGENTS_DIR" ]; then
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would remove agent .md files from $AGENTS_DIR"
    else
        find "$AGENTS_DIR" -maxdepth 1 -name "*.md" -type f -delete 2>/dev/null
        # Also remove junction-style subdirectory if it exists
        if [ -d "$AGENTS_DIR/Agents-Opencode-Jake" ]; then
            rm -rf "$AGENTS_DIR/Agents-Opencode-Jake"
        fi
        echo "  [OK] removed agent files from $AGENTS_DIR"
    fi
fi
echo

# ---- Step 2: Remove skill symlinks ----
echo "[2/4] Removing skill symlinks..."
for skill_name in graphify-agent-workflow batch-quoting opencode-config-merge plan-review verify-plan-gate; do
    link_path="$SKILLS_DIR/$skill_name"
    if [ -L "$link_path" ] || [ -d "$link_path" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "  [DRY-RUN] would remove: $link_path"
        else
            rm -rf "$link_path"
            echo "  [OK] removed: $link_path"
        fi
    fi
done
echo

# ---- Step 3: Run merge helper to remove from config ----
echo "[3/4] Removing from global opencode.jsonc..."
if [ -f "$MERGE_HELPER" ]; then
    REMOVE_ARGS="remove --global $GLOBAL_CONFIG --manifest $MANIFEST"
    [ "$FORCE" = "1" ] && REMOVE_ARGS="$REMOVE_ARGS --force"
    [ "$DRY_RUN" = "1" ] && REMOVE_ARGS="$REMOVE_ARGS --dry-run"
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would run:"
        echo "    $PY $MERGE_HELPER $REMOVE_ARGS"
    fi
    "$PY" "$MERGE_HELPER" $REMOVE_ARGS || echo "  [WARN] merge helper remove returned non-zero"
    # Remove manifest
    if [ "$DRY_RUN" != "1" ] && [ -f "$MANIFEST" ]; then
        rm -f "$MANIFEST"
        echo "  [OK] removed manifest"
    fi
else
    echo "  [WARN] merge helper not found: $MERGE_HELPER"
fi
echo

# ---- Step 4: Summary ----
echo "[4/4] Summary"
echo "============================================"
echo "  Global uninstall complete!"
echo "============================================"
echo
echo "  Removed: agent files, skill symlinks, config entries"
echo "  Config:  $GLOBAL_CONFIG"
echo
echo "  Verify:  opencode agent list"
echo "  Reinstall: run global-setup.sh"
echo
exit 0

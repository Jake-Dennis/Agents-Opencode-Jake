#!/bin/bash
# Agents-Opencode-Jake — Local Setup (Mac/Linux)
# Ported from setup.bat — installs into current project

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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(pwd)/"

echo "============================================"
echo " Agents-Opencode-Jake -- Install into project"
echo "============================================"
echo
echo "  Source: $SCRIPT_DIR"
echo "  Target: $TARGET_DIR"
[ "$DRY_RUN" = "1" ] && echo "  [DRY-RUN] no files will be written."
[ "$FORCE" = "1" ] && echo "  [FORCE]   overwriting existing files."
echo

# --- Confirmation ---
if [ "$UNATTENDED" = "1" ]; then
    echo "  [UNATTENDED] proceeding without prompt."
    echo
else
    read -p "  Continue with local install? (y/N): " CONFIRM
    if [ "$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')" != "y" ]; then
        echo "  Aborted."
        exit 0
    fi
    echo
fi

# ---- Step 1: Copy AGENTS.md ----
echo "[1/3] Copying AGENTS.md..."
if [ -f "$TARGET_DIR/AGENTS.md" ] && [ "$FORCE" != "1" ]; then
    echo "  [SKIP] AGENTS.md already exists (use --force to overwrite)"
else
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would copy AGENTS.md to $TARGET_DIR"
    else
        cp "$SCRIPT_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.md"
        echo "  [OK] copied AGENTS.md"
    fi
fi
echo

# ---- Step 2: Create .opencode structure ----
echo "[2/3] Creating .opencode structure..."
for dir in .opencode .opencode/agents .opencode/skills .opencode/commands .opencode/plans .opencode/plans/completed .opencode/decisions; do
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would create: $TARGET_DIR$dir"
    else
        mkdir -p "$TARGET_DIR$dir"
    fi
done
if [ "$DRY_RUN" != "1" ]; then
    echo "  [OK] created .opencode structure"
fi
echo

# ---- Step 3: Merge opencode.json ----
echo "[3/3] Merging opencode.json..."
if [ -f "$TARGET_DIR/opencode.json" ] && [ "$FORCE" != "1" ]; then
    echo "  [SKIP] opencode.json already exists (use --force to overwrite)"
else
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would copy opencode.json to $TARGET_DIR"
    else
        cp "$SCRIPT_DIR/opencode.json" "$TARGET_DIR/opencode.json"
        echo "  [OK] copied opencode.json"
    fi
fi
echo

echo "============================================"
echo "  Local install complete!"
echo "============================================"
echo
echo "  Next steps:"
echo "    1. cd $TARGET_DIR"
echo "    2. opencode ."
echo "    3. Run /graphify . to build knowledge graph"
echo
echo "  Uninstall: run uninstall.sh"
echo
exit 0

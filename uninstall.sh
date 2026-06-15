#!/bin/bash
# Agents-Opencode-Jake — Local Uninstall (Mac/Linux)
# Ported from uninstall.bat

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
echo " Agents-Opencode-Jake -- Uninstall from project"
echo "============================================"
echo
echo "  Target: $TARGET_DIR"
[ "$DRY_RUN" = "1" ] && echo "  [DRY-RUN] no files will be removed."
[ "$FORCE" = "1" ] && echo "  [FORCE]   removing without confirmation."
echo

# --- Confirmation ---
if [ "$UNATTENDED" = "1" ]; then
    echo "  [UNATTENDED] proceeding without prompt."
    echo
else
    read -p "  Continue with local uninstall? (y/N): " CONFIRM
    if [ "$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')" != "y" ]; then
        echo "  Aborted."
        exit 0
    fi
    echo
fi

# ---- Step 1: Remove files ----
echo "[1/2] Removing files..."
if [ -f "$TARGET_DIR/AGENTS.md" ]; then
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would remove AGENTS.md"
    else
        rm -f "$TARGET_DIR/AGENTS.md"
        echo "  [OK] removed AGENTS.md"
    fi
fi
echo

# ---- Step 2: Remove .opencode structure ----
echo "[2/2] Removing .opencode structure..."
if [ -d "$TARGET_DIR/.opencode" ]; then
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY-RUN] would remove $TARGET_DIR.opencode"
    else
        rm -rf "$TARGET_DIR/.opencode"
        echo "  [OK] removed .opencode"
    fi
fi
echo

echo "============================================"
echo "  Local uninstall complete!"
echo "============================================"
echo
echo "  Reinstall: run setup.sh"
echo
exit 0

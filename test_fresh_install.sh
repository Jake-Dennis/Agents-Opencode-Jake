#!/bin/bash
# test_fresh_install.sh — Validate global-setup.sh on a fresh machine
# This script backs up existing config, runs a full install, validates output, and restores.

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/opencode"
BACKUP_DIR="$HOME/.config/opencode.backup.$(date +%s)"
MANIFEST="$CONFIG_DIR/.opencode-jake-installed.json"

echo "============================================"
echo " Fresh Install Test (Mac/Linux)"
echo "============================================"
echo
echo "  This test will:"
echo "    1. Backup existing ~/.config/opencode/ to $BACKUP_DIR"
echo "    2. Run $REPO_DIR/global-setup.sh --unattended"
echo "    3. Verify all 13 agents are installed"
echo "    4. Verify skills are linked"
echo "    5. Verify manifest is written"
echo "    6. Run $REPO_DIR/uninstall-global.sh --unattended"
echo "    7. Restore the backup"
echo

read -p "  Continue? (y/N): " CONFIRM
if [ "$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')" != "y" ]; then
    echo "  Aborted."
    exit 0
fi

# --- Step 1: Backup existing config ---
echo
echo "[1/7] Backing up existing config..."
if [ -d "$CONFIG_DIR" ]; then
    mv "$CONFIG_DIR" "$BACKUP_DIR"
    echo "  [OK] backed up to $BACKUP_DIR"
else
    echo "  [INFO] no existing config to backup"
fi

# --- Step 2: Run global-setup.sh ---
echo
echo "[2/7] Running global-setup.sh..."
"$REPO_DIR/global-setup.sh" --unattended
SETUP_RC=$?
if [ "$SETUP_RC" != "0" ]; then
    echo "  [FAIL] global-setup.sh exited with code $SETUP_RC"
    echo "  Restoring backup..."
    rm -rf "$CONFIG_DIR"
    [ -d "$BACKUP_DIR" ] && mv "$BACKUP_DIR" "$CONFIG_DIR"
    exit 1
fi
echo "  [OK] global-setup.sh completed"

# --- Step 3: Verify agents ---
echo
echo "[3/7] Verifying agents installed..."
EXPECTED_AGENTS=("architect" "builder" "conductor" "debugger" "docs" "explorer" "git" "perf" "planner" "refactor" "reviewer" "security" "tester")
AGENT_COUNT=0
for agent in "${EXPECTED_AGENTS[@]}"; do
    if [ -f "$CONFIG_DIR/agents/$agent.md" ]; then
        AGENT_COUNT=$((AGENT_COUNT + 1))
    else
        echo "  [FAIL] missing agent: $agent.md"
    fi
done
if [ "$AGENT_COUNT" != "13" ]; then
    echo "  [FAIL] expected 13 agents, found $AGENT_COUNT"
    echo "  Restoring backup..."
    "$REPO_DIR/uninstall-global.sh" --unattended --force
    rm -rf "$CONFIG_DIR"
    [ -d "$BACKUP_DIR" ] && mv "$BACKUP_DIR" "$CONFIG_DIR"
    exit 1
fi
echo "  [OK] all 13 agents installed"

# --- Step 4: Verify skills ---
echo
echo "[4/7] Verifying skills linked..."
EXPECTED_SKILLS=("graphify-agent-workflow" "batch-quoting" "opencode-config-merge" "plan-review" "verify-plan-gate")
SKILL_COUNT=0
for skill in "${EXPECTED_SKILLS[@]}"; do
    if [ -d "$CONFIG_DIR/skills/$skill" ] || [ -L "$CONFIG_DIR/skills/$skill" ]; then
        SKILL_COUNT=$((SKILL_COUNT + 1))
    else
        echo "  [FAIL] missing skill: $skill"
    fi
done
if [ "$SKILL_COUNT" != "5" ]; then
    echo "  [FAIL] expected 5 skills, found $SKILL_COUNT"
    echo "  Restoring backup..."
    "$REPO_DIR/uninstall-global.sh" --unattended --force
    rm -rf "$CONFIG_DIR"
    [ -d "$BACKUP_DIR" ] && mv "$BACKUP_DIR" "$CONFIG_DIR"
    exit 1
fi
echo "  [OK] all 5 skills linked"

# --- Step 5: Verify manifest ---
echo
echo "[5/7] Verifying manifest written..."
if [ ! -f "$MANIFEST" ]; then
    echo "  [FAIL] manifest not found at $MANIFEST"
    echo "  Restoring backup..."
    "$REPO_DIR/uninstall-global.sh" --unattended --force
    rm -rf "$CONFIG_DIR"
    [ -d "$BACKUP_DIR" ] && mv "$BACKUP_DIR" "$CONFIG_DIR"
    exit 1
fi
echo "  [OK] manifest exists"

# --- Step 6: Run uninstall ---
echo
echo "[6/7] Running uninstall-global.sh..."
"$REPO_DIR/uninstall-global.sh" --unattended
UNINSTALL_RC=$?
if [ "$UNINSTALL_RC" != "0" ]; then
    echo "  [FAIL] uninstall-global.sh exited with code $UNINSTALL_RC"
    exit 1
fi

# Verify agents removed
if [ -d "$CONFIG_DIR/agents" ]; then
    REMAINING=$(find "$CONFIG_DIR/agents" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
    if [ "$REMAINING" != "0" ]; then
        echo "  [FAIL] $REMAINING agent files remain after uninstall"
        exit 1
    fi
fi
echo "  [OK] uninstall-global.sh completed"

# --- Step 7: Restore backup ---
echo
echo "[7/7] Restoring backup..."
if [ -d "$BACKUP_DIR" ]; then
    mv "$BACKUP_DIR" "$CONFIG_DIR"
    echo "  [OK] restored from $BACKUP_DIR"
else
    echo "  [INFO] no backup to restore"
fi

echo
echo "============================================"
echo "  Fresh install test PASSED!"
echo "============================================"
exit 0

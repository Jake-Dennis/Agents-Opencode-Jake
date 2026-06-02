#!/usr/bin/env bash
# =============================================================================
# scripts/install-hook.sh
# =============================================================================
# Installs the pre-commit hook from scripts/pre-commit into .git/hooks/pre-commit.
# Run once per clone:   bash scripts/install-hook.sh
#
# Idempotent — safe to re-run. The target is overwritten on each run.
# `chmod +x` is a no-op on Windows git bash but harmless to call.
# =============================================================================

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "ERROR: not inside a git repository."
    echo "Run this from the project root: bash scripts/install-hook.sh"
    exit 1
fi

SOURCE="$REPO_ROOT/scripts/pre-commit"
TARGET="$REPO_ROOT/.git/hooks/pre-commit"

if [[ ! -f "$SOURCE" ]]; then
    echo "ERROR: source hook not found: $SOURCE"
    exit 1
fi

cp "$SOURCE" "$TARGET"
# chmod is a no-op on Windows git bash; ignore failure silently there
chmod +x "$TARGET" 2>/dev/null || true

echo "Installed pre-commit hook: $TARGET"
echo ""
echo "The hook will run on every 'git commit' and block on failure."
echo "Test by making a commit. To bypass for a single commit: git commit --no-verify"

#!/bin/bash
# build-release.sh — Create release artifacts for Agents-Opencode-Jake
# Builds a .tar.gz with all installers and Python helpers

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Get version from git tag or use "dev"
VERSION="${1:-$(git describe --tags --abbrev=0 2>/dev/null || echo "dev")}"
VERSION="${VERSION#v}"  # Strip leading 'v' if present

RELEASE_NAME="agents-opencode-jake-v${VERSION}"
RELEASE_DIR="release/${RELEASE_NAME}"
TARBALL="release/${RELEASE_NAME}.tar.gz"

echo "============================================"
echo " Building release: ${RELEASE_NAME}"
echo "============================================"
echo

# --- Clean previous release ---
rm -rf release/
mkdir -p "$RELEASE_DIR"

# --- Copy files ---
echo "[1/3] Copying files..."

# Root-level installers and docs
cp global-setup.bat "$RELEASE_DIR/" 2>/dev/null || true
cp global-setup.sh "$RELEASE_DIR/"
cp uninstall-global.bat "$RELEASE_DIR/" 2>/dev/null || true
cp uninstall-global.sh "$RELEASE_DIR/"
cp setup.bat "$RELEASE_DIR/" 2>/dev/null || true
cp setup.sh "$RELEASE_DIR/"
cp uninstall.bat "$RELEASE_DIR/" 2>/dev/null || true
cp uninstall.sh "$RELEASE_DIR/"
cp AGENTS.md "$RELEASE_DIR/"
cp README.md "$RELEASE_DIR/"
cp INSTALL.md "$RELEASE_DIR/"
cp LICENSE "$RELEASE_DIR/" 2>/dev/null || true

# opencode.json
cp opencode.json "$RELEASE_DIR/"
cp opencode.schema.json "$RELEASE_DIR/" 2>/dev/null || true

# Python helpers
mkdir -p "$RELEASE_DIR/.opencode/scripts"
cp .opencode/scripts/*.py "$RELEASE_DIR/.opencode/scripts/"

# Agent files
mkdir -p "$RELEASE_DIR/.opencode/agents"
cp .opencode/agents/*.md "$RELEASE_DIR/.opencode/agents/"

# Shared sections
mkdir -p "$RELEASE_DIR/.opencode/agents/shared"
cp .opencode/agents/shared/*.md "$RELEASE_DIR/.opencode/agents/shared/"

# Skills
mkdir -p "$RELEASE_DIR/.opencode/skills"
for skill_dir in .opencode/skills/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        mkdir -p "$RELEASE_DIR/.opencode/skills/$skill_name"
        cp -R "$skill_dir"/* "$RELEASE_DIR/.opencode/skills/$skill_name/"
    fi
done

# Commands
mkdir -p "$RELEASE_DIR/.opencode/commands"
cp .opencode/commands/*.md "$RELEASE_DIR/.opencode/commands/"

# Make shell scripts executable
chmod +x "$RELEASE_DIR"/*.sh

echo "  [OK] copied all files"

# --- Create .gitignore for release ---
cat > "$RELEASE_DIR/.gitignore" <<'EOF'
# Release artifacts
__pycache__/
*.pyc
.DS_Store
EOF

# --- Create tarball ---
echo
echo "[2/3] Creating tarball..."
cd release
tar -czf "${RELEASE_NAME}.tar.gz" "${RELEASE_NAME}"
echo "  [OK] created ${RELEASE_NAME}.tar.gz"

# --- Generate checksums ---
echo
echo "[3/3] Generating checksums..."
cd release
sha256sum "${RELEASE_NAME}.tar.gz" > "${RELEASE_NAME}.tar.gz.sha256"
echo "  [OK] checksums written"

# --- Summary ---
echo
echo "============================================"
echo " Release built successfully!"
echo "============================================"
echo
echo "  Artifacts:"
echo "    release/${RELEASE_NAME}.tar.gz"
echo "    release/${RELEASE_NAME}.tar.gz.sha256"
echo
echo "  Size: $(du -h release/${RELEASE_NAME}.tar.gz | cut -f1)"
echo
echo "  Next steps:"
echo "    1. Test the tarball: tar -tzf release/${RELEASE_NAME}.tar.gz"
echo "    2. Create a GitHub release with these artifacts"
echo "    3. Tag the release: git tag v${VERSION}"
echo
ls -lh release/
exit 0

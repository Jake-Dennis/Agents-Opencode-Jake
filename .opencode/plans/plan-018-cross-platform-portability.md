# Plan 018: Make Project Portable Across Computers and Projects

## Goal
Make Agents-Opencode-Jake work on other computers (different machines) and in other projects (not just this repo). Currently only Windows .bat installers exist; need Mac/Linux support, clear distribution mechanism, and validation on fresh machines.

## Context
User request: "i need this project to work on other computers and project not just this one"
Current state: 4 Windows .bat files (global-setup, uninstall-global, setup, uninstall) + Python helpers
Missing: Cross-platform shell scripts, distribution docs, fresh-machine validation

## Tasks

### Layer 1 — Cross-platform shell scripts (parallel, no deps)
- [ ] #1 - Create `global-setup.sh` (Mac/Linux equivalent of global-setup.bat) (assigned: @builder)
- [ ] #2 - Create `uninstall-global.sh` (Mac/Linux equivalent of uninstall-global.bat) (assigned: @builder)
- [ ] #3 - Create `setup.sh` (Mac/Linux equivalent of setup.bat) (assigned: @builder)
- [ ] #4 - Create `uninstall.sh` (Mac/Linux equivalent of uninstall.bat) (assigned: @builder)
- [ ] #5 - Add cross-platform detection in Python helpers (Path.home(), platform.system()) (assigned: @builder)

### Layer 2 — Distribution mechanism (parallel, no deps)
- [ ] #6 - Create `INSTALL.md` with step-by-step instructions for new users (assigned: @docs)
- [ ] #7 - Add `git clone` quick-start to README (assigned: @docs)
- [ ] #8 - Create release script (build .zip/.tar.gz with all installers) (assigned: @builder)
- [ ] #9 - Add GitHub release workflow (.github/workflows/release.yml) (assigned: @builder)

### Layer 3 — Fresh-machine validation (parallel, no deps)
- [ ] #10 - Create `test_fresh_install.sh` (validates global-setup works from scratch) (assigned: @tester)
- [ ] #11 - Create `test_fresh_install.bat` (Windows version) (assigned: @tester)
- [ ] #12 - Add CI matrix test (Ubuntu + macOS + Windows) (assigned: @tester)
- [ ] #13 - Document validation procedure in INSTALL.md (assigned: @docs)

### Layer 4 — Documentation and examples (depends on L1-L3)
- [ ] #14 - Update README with cross-platform install instructions (assigned: @docs)
- [ ] #15 - Create examples/cross-platform-setup.md (assigned: @docs)
- [ ] #16 - Add troubleshooting section for Mac/Linux-specific issues (assigned: @docs)
- [ ] #17 - Update .opencode/plans/README with plan-018 entry (assigned: @docs)

## Verification
- [ ] #1 - All 4 .sh scripts exist and are executable
- [ ] #2 - Python helpers work on Mac/Linux (Path.home(), platform detection)
- [ ] #3 - INSTALL.md has clear step-by-step for Windows, Mac, Linux
- [ ] #4 - Fresh install test passes on all 3 platforms
- [ ] #5 - CI matrix tests pass on Ubuntu + macOS + Windows
- [ ] #6 - Release workflow creates valid .zip/.tar.gz
- [ ] #7 - README updated with cross-platform instructions

## Deliverables
- 4 new shell scripts (global-setup.sh, uninstall-global.sh, setup.sh, uninstall.sh)
- INSTALL.md (comprehensive installation guide)
- Updated README.md
- test_fresh_install.sh and .bat
- CI matrix workflow
- Release workflow
- examples/cross-platform-setup.md
- Updated .opencode/plans/README.md

## Notes
- All shell scripts must use `#!/bin/bash` shebang
- Python helpers should use `pathlib.Path.home()` instead of `os.path.expanduser('~')`
- Use `ln -s` for symlinks on Mac/Linux (not junctions)
- Use `which python3` instead of `where python`
- Test on actual Mac/Linux via CI matrix

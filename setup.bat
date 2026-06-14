@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake -- Setup

:: --- Parse flags (args take precedence over env vars) ---
:: Accept %~1, %~2, %~3 as --unattended, --dry-run, --force. Env vars
:: SETUP_YES, SETUP_DRY_RUN, SETUP_FORCE also work.
set "UNATTENDED="
set "DRY_RUN="
set "FORCE="

for %%A in ("%~1" "%~2" "%~3") do (
    if /i "%%~A"=="--unattended" set "UNATTENDED=1"
    if /i "%%~A"=="--dry-run"   set "DRY_RUN=1"
    if /i "%%~A"=="--force"     set "FORCE=1"
)

if "%SETUP_YES%"=="1"      set "UNATTENDED=1"
if "%SETUP_DRY_RUN%"=="1"  set "DRY_RUN=1"
if "%SETUP_FORCE%"=="1"    set "FORCE=1"

:: --- Figure out where we are ---
set "SCRIPT_DIR=%~dp0"
set "TARGET_DIR=%CD%\"

echo ============================================
echo  Agents-Opencode-Jake -- Install into project
echo ============================================
echo.
echo  Running from: %SCRIPT_DIR%
echo  Installing to: %TARGET_DIR%
echo.

:: --- Verify payload files are nearby ---
if not exist "%SCRIPT_DIR%AGENTS.md" (
    echo  [ERROR] AGENTS.md not found next to setup.bat.
    echo  Make sure setup.bat is in the dist/ folder or repo root.
    pause
    exit /b 1
)
if not exist "%SCRIPT_DIR%opencode.json" (
    echo  [ERROR] opencode.json not found next to setup.bat.
    pause
    exit /b 1
)

:: ---- Step 1: Check Python ----
echo [1/7] Checking Python...

:: Resolve Python (try `python`, then `py`). Skip `python3` (MS Store stub).
set "PY="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY set "PY=%%P"
)
if not defined PY (
    for /f "delims=" %%P in ('where py 2^>nul') do (
        if not defined PY set "PY=%%P"
    )
)
if not defined PY (
    echo  [ERROR] Python not found. Please install Python 3.10+ or set PATH.
    pause
    exit /b 1
)
echo  Python: !PY!
!PY! --version
echo.

:: ---- Step 2: Install Python dependencies (only if missing) ----
:: Check each dependency via Python import. The pip distribution name for
:: graphify is `graphifyy` (typo-squat avoidance on PyPI) but the import
:: is `graphify`. We install only the missing ones; re-runs are a no-op.
echo [2/7] Checking Python dependencies...
set "MISSING_DEPS="
!PY! -c "import graphify" >nul 2>&1
if !errorlevel! neq 0 set "MISSING_DEPS=!MISSING_DEPS! graphifyy"
!PY! -c "import pytest" >nul 2>&1
if !errorlevel! neq 0 set "MISSING_DEPS=!MISSING_DEPS! pytest"
!PY! -c "import jsonschema" >nul 2>&1
if !errorlevel! neq 0 set "MISSING_DEPS=!MISSING_DEPS! jsonschema"
if "!MISSING_DEPS!"=="" (
    echo  All dependencies already installed.
) else (
    echo  [INSTALL] missing:!MISSING_DEPS!
    pip install !MISSING_DEPS! 2>&1 | findstr /V "already satisfied" | findstr /V "^$"
)
echo.

:: ---- Step 2b: Refresh graphify skill + plugin if pip is ahead of stamp ----
:: Calls the Python helper to compare the pip-installed graphifyy version
:: to the stamp at %USERPROFILE%\.config\opencode\skills\graphify\.graphify_version
:: and refresh the user-scope skill + project-scope plugin if pip is ahead.
:: The helper is idempotent and never aborts on failure -- if it returns
:: non-zero, we WARN and continue. See .opencode\plans\plan-004-design.md
:: and .opencode\decisions\adr-003-graphify-auto-refresh.md for the full contract.
echo [2b/7] Checking graphify version...
set "REFRESH_HELPER=%SCRIPT_DIR%.opencode\scripts\graphify_refresh.py"
if not exist "%REFRESH_HELPER%" (
    echo  [WARN] refresh helper not found: %REFRESH_HELPER%
    echo         Skipping graphify version check. Reinstall to recover.
) else (
    set "REFRESH_ARGS=--stamp-path %USERPROFILE%\.config\opencode\skills\graphify\.graphify_version"
    if "%UNATTENDED%"=="1" set "REFRESH_ARGS=!REFRESH_ARGS! --unattended"
    if "%DRY_RUN%"=="1"    set "REFRESH_ARGS=!REFRESH_ARGS! --dry-run"
    if "%FORCE%"=="1"      set "REFRESH_ARGS=!REFRESH_ARGS! --yes"
    "!PY!" "%REFRESH_HELPER%" !REFRESH_ARGS!
    if !errorlevel! neq 0 (
        echo  [WARN] graphify version check returned non-zero; install continues.
    )
)
echo.

:: ---- Step 3: Copy agent files into project ----
echo [3/7] Copying agent files...

:: AGENTS.md
copy /Y "%SCRIPT_DIR%AGENTS.md" "%TARGET_DIR%AGENTS.md" >nul
echo    AGENTS.md

:: scripts/
if not exist "%TARGET_DIR%scripts" mkdir "%TARGET_DIR%scripts"
if exist "%SCRIPT_DIR%scripts\verify-plan.py" (
    copy /Y "%SCRIPT_DIR%scripts\verify-plan.py" "%TARGET_DIR%scripts\verify-plan.py" >nul
    copy /Y "%SCRIPT_DIR%scripts\pre-commit" "%TARGET_DIR%scripts\pre-commit" >nul
    if exist "%SCRIPT_DIR%scripts\install-hook.sh" (
        copy /Y "%SCRIPT_DIR%scripts\install-hook.sh" "%TARGET_DIR%scripts\install-hook.sh" >nul
    )
    if exist "%SCRIPT_DIR%scripts\build_graph.py" (
        copy /Y "%SCRIPT_DIR%scripts\build_graph.py" "%TARGET_DIR%scripts\build_graph.py" >nul
    )
    if exist "%SCRIPT_DIR%scripts\archive-jobs.py" (
        copy /Y "%SCRIPT_DIR%scripts\archive-jobs.py" "%TARGET_DIR%scripts\archive-jobs.py" >nul
    )
    echo    scripts\ (verify-plan.py, archive-jobs.py, pre-commit, install-hook.sh, build_graph.py)
)

:: .opencode/scripts/ (merge helper, graphify_refresh)
if exist "%SCRIPT_DIR%.opencode\scripts\opencode_jsonc_merge.py" (
    if not exist "%TARGET_DIR%.opencode\scripts" mkdir "%TARGET_DIR%.opencode\scripts"
    copy /Y "%SCRIPT_DIR%.opencode\scripts\opencode_jsonc_merge.py" "%TARGET_DIR%.opencode\scripts\opencode_jsonc_merge.py" >nul
    if exist "%SCRIPT_DIR%.opencode\scripts\graphify_refresh.py" (
        copy /Y "%SCRIPT_DIR%.opencode\scripts\graphify_refresh.py" "%TARGET_DIR%.opencode\scripts\graphify_refresh.py" >nul
    )
    echo    .opencode\scripts\ (merge helper, graphify_refresh)
)

:: .opencode/agents/ (prompt source for {file:...} references)
if not exist "%TARGET_DIR%.opencode\agents" mkdir "%TARGET_DIR%.opencode\agents"
if exist "%SCRIPT_DIR%.opencode\agents\conductor.md" (
    copy /Y "%SCRIPT_DIR%.opencode\agents\*.md" "%TARGET_DIR%.opencode\agents\" >nul
    for /f %%F in ('dir /b "%SCRIPT_DIR%.opencode\agents\*.md" 2^>nul') do echo    .opencode\agents\%%F
)
echo.

:: .opencode/skills/
if not exist "%TARGET_DIR%.opencode\skills\graphify-agent-workflow" (
    mkdir "%TARGET_DIR%.opencode\skills\graphify-agent-workflow"
)
if exist "%SCRIPT_DIR%.opencode\skills\graphify-agent-workflow\SKILL.md" (
    copy /Y "%SCRIPT_DIR%.opencode\skills\graphify-agent-workflow\SKILL.md" "%TARGET_DIR%.opencode\skills\graphify-agent-workflow\SKILL.md" >nul
    echo    .opencode\skills\graphify-agent-workflow\SKILL.md
)
echo.

:: ---- Step 4: Merge or create opencode.json ----
echo [4/7] Configuring opencode.json...

if exist "%TARGET_DIR%opencode.json" (
    echo  Project already has opencode.json -- merging agent block...
    REM Single-line Python merge to avoid batch parenthesis issues
    "!PY!" -c "import json, sys; src = json.load(open(r'%SCRIPT_DIR%opencode.json', encoding='utf-8')); tgt_file = r'%TARGET_DIR%opencode.json'; tgt = json.load(open(tgt_file, encoding='utf-8')); tgt['agent'] = src['agent']; tgt['instructions'] = list(set(tgt.get('instructions', []) + ['AGENTS.md'])); tgt.setdefault('skills', {}).setdefault('paths', []); [tgt['skills']['paths'].append(p) for p in ['.opencode/skills'] if p not in tgt['skills']['paths']]; json.dump(tgt, open(tgt_file, 'w', encoding='utf-8'), indent=2, ensure_ascii=False); print('  Merged: agent block copied, instructions + skills paths added')"
) else (
    echo  No opencode.json found -- copying standalone config...
    copy /Y "%SCRIPT_DIR%opencode.json" "%TARGET_DIR%opencode.json" >nul
    echo  Created: opencode.json (standalone with all 13 agents)
)
echo.

:: ---- Step 5: Create .opencode structure ----
echo [5/7] Creating .opencode structure...
if not exist "%TARGET_DIR%.opencode\plans\completed" mkdir "%TARGET_DIR%.opencode\plans\completed"
if not exist "%TARGET_DIR%.opencode\decisions" mkdir "%TARGET_DIR%.opencode\decisions"
if not exist "%TARGET_DIR%.opencode\todo.md" type nul > "%TARGET_DIR%.opencode\todo.md"
if not exist "%TARGET_DIR%.opencode\work-log.md" (
    echo # Work Log > "%TARGET_DIR%.opencode\work-log.md"
    echo. >> "%TARGET_DIR%.opencode\work-log.md"
    echo Auto-generated by the conductor agent. >> "%TARGET_DIR%.opencode\work-log.md"
)
if not exist "%TARGET_DIR%.opencode\jobs.md" (
    REM Copy the canonical jobs.md format spec from the project so subagents
    REM have a place to write live progress. This is the 3-file split from
    REM plan-013: todo.md (conductor), work-log.md (conductor), jobs.md
    REM (11 write-capable subagents).
    if exist "%SCRIPT_DIR%.opencode\jobs.md" (
        copy /Y "%SCRIPT_DIR%.opencode\jobs.md" "%TARGET_DIR%.opencode\jobs.md" >nul
    ) else (
        REM Fallback: minimal placeholder so the file exists and subagents
        REM have a writable target. The conductor's first /build run will
        REM populate the format spec from a future plan.
        echo # Jobs (live progress) > "%TARGET_DIR%.opencode\jobs.md"
        echo. >> "%TARGET_DIR%.opencode\jobs.md"
        echo Auto-managed by subagents. Do not edit by hand. >> "%TARGET_DIR%.opencode\jobs.md"
    )
)
echo  .opencode structure ready.
echo.

:: ---- Step 6: Initialize git + ignore + hook ----
echo [6/7] Setting up git...
if not exist "%TARGET_DIR%.git" (
    git init
    echo  Git repository initialized.
) else (
    echo  Git repository already exists.
)
if not exist "%TARGET_DIR%.gitignore" (
    echo Creating .gitignore...
    (
        echo # Python
        echo __pycache__/
        echo *.pyc
        echo *.pyo
        echo *.egg-info/
        echo .eggs/
        echo dist/
        echo build/
        echo.
        echo # Node
        echo node_modules/
        echo .opencode/node_modules/
        echo.
        echo # opencode
        echo graphify-out/
        echo .opencode/plans/plan-*.md
        echo .opencode/reports/
        echo.
        echo # Environment
        echo .env
        echo .venv
        echo venv/
        echo.
        echo # OS
        echo Thumbs.db
        echo .DS_Store
        echo.
        echo # IDE
        echo .vscode/
        echo .idea/
        echo *.swp
        echo *.swo
    ) > "%TARGET_DIR%.gitignore"
    echo  .gitignore created.
) else (
    echo  .gitignore already exists.
)

:: Install pre-commit hook
if exist "%TARGET_DIR%scripts\pre-commit" (
    if exist "%TARGET_DIR%.git" (
        copy /Y "%TARGET_DIR%scripts\pre-commit" "%TARGET_DIR%.git\hooks\pre-commit" >nul 2>&1
        if !errorlevel! equ 0 (
            echo  Pre-commit hook installed.
        ) else (
            echo  [INFO] Could not install pre-commit hook.
        )
    )
)
echo.

:: ---- Step 7: Build knowledge graph ----
echo [7/7] Building knowledge graph...
call :build_knowledge_graph
echo.

:: ---- Step 8: Install graphify OpenCode plugin ----
echo [8/8] Installing graphify OpenCode plugin...
call :install_graphify_plugin
echo.

:: ---- Summary ----
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo  Copied to: %TARGET_DIR%
echo.
echo  What was installed:
echo    - AGENTS.md  (agent workflow docs)
echo    - opencode.json  (13 agent definitions)
echo    - .opencode\agents\  (conductor.md + agent prompts)
echo    - scripts\  (verify-plan.py, archive-jobs.py, pre-commit hook)
echo    - .opencode\  (skills, plans, decisions, todo)
echo    - .gitignore
echo    - Pre-commit hook
echo    - Knowledge graph
echo.
echo  Now run: opencode .
echo  Then:    /graphify .
echo.
pause
exit /b 0

:: ---- Knowledge graph build subroutine ----
:build_knowledge_graph
if not exist "%TARGET_DIR%scripts\build_graph.py" (
    echo  [WARN] build_graph.py not found, skipping graph build.
    goto :eof
)
"!PY!" "%TARGET_DIR%scripts\build_graph.py" "%TARGET_DIR%" >nul 2>&1
if errorlevel 1 goto :graph_fail
echo  Knowledge graph built: graphify-out\
goto :eof

:graph_fail
echo  [INFO] Graph build skipped (graphify may not support --depth).
echo  Run once opencode is open: /graphify .
goto :eof

:: ---- Graphify plugin installation subroutine ----
:install_graphify_plugin
where graphify >nul 2>&1
if !errorlevel! neq 0 (
    echo  [SKIP] graphify CLI not found — run 'uv tool install graphifyy' first
    goto :eof
)
graphify opencode install >nul 2>&1
if !errorlevel! equ 0 (
    echo  [OK] graphify plugin installed
) else (
    echo  [WARN] graphify opencode install failed — run it manually
)
goto :eof


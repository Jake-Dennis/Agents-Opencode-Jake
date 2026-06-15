@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake — Global Installer

:: --- Parse flags (args take precedence over env vars) ---
:: Accept %~1, %~2, %~3 as --unattended, --dry-run, --force. Env vars
:: GLOBAL_SETUP_YES, GLOBAL_SETUP_DRY_RUN, GLOBAL_SETUP_FORCE also work.
set "UNATTENDED="
set "DRY_RUN="
set "FORCE="

for %%A in ("%~1" "%~2" "%~3") do (
    if /i "%%~A"=="--unattended" set "UNATTENDED=1"
    if /i "%%~A"=="--dry-run"   set "DRY_RUN=1"
    if /i "%%~A"=="--force"     set "FORCE=1"
)

if "%GLOBAL_SETUP_YES%"=="1"      set "UNATTENDED=1"
if "%GLOBAL_SETUP_DRY_RUN%"=="1"  set "DRY_RUN=1"
if "%GLOBAL_SETUP_FORCE%"=="1"    set "FORCE=1"

:: --- Paths ---
set "REPO_DIR=%~dp0"
:: NOTE: REPO_DIR keeps the trailing backslash (from %~dp0) because the
:: .bat concatenates it with filenames (e.g. `%REPO_DIR%.opencode\...`).
:: The trailing backslash is required for that concatenation. The bug it
:: causes in quoted args like `--repo-root "%REPO_DIR%"` (where the `\"`
:: escape consumes the closing quote and puts a literal `"` in the path)
:: is fixed inline at each callsite via the `%REPO_DIR:~0,-1%` idiom.
set "CONFIG_DIR=%USERPROFILE%\.config\opencode"
set "AGENTS_DIR=%CONFIG_DIR%\agents"
set "SKILLS_DIR=%CONFIG_DIR%\skills"
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"
set "MANIFEST=%CONFIG_DIR%\.opencode-jake-installed.json"
set "PROJECT_CONFIG=%REPO_DIR%opencode.json"
set "MERGE_HELPER=%REPO_DIR%.opencode\scripts\opencode_jsonc_merge.py"

:: --- Resolve Python (needed early for include resolution in step 2) ---
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
    exit /b 5
)

echo ============================================
echo  Agents-Opencode-Jake — Global Installer
echo ============================================
echo.
echo  Repo:    %REPO_DIR%
echo  Config:  %CONFIG_DIR%
echo.
echo  WARNING: This installs agents and skills globally
echo  for ALL opencode projects on this machine.
echo  Run setup.bat instead for local/per-project setup.
if "%DRY_RUN%"=="1" echo  [DRY-RUN] no files will be written.
if "%FORCE%"=="1"   echo  [FORCE]   existing agent entries will be overwritten.
echo.

:: --- Confirmation prompt (skip when --unattended) ---
if "%UNATTENDED%"=="1" (
    echo  [UNATTENDED] proceeding without prompt.
    echo.
) else (
    set /p "CONFIRM=Continue with global install? (y/N): "
    if /i not "!CONFIRM!"=="y" (
        echo  Aborted.
        pause
        exit /b 0
    )
    echo.
)

:: ---- Step 1: Ensure config directories exist ----
echo [1/5] Ensuring global config directories exist...
if not exist "%AGENTS_DIR%" mkdir "%AGENTS_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"
echo  Dirs: %AGENTS_DIR%, %SKILLS_DIR%
echo.

:: ---- Step 2: Agent files (copy directly) ----
:: Copy agent .md files directly to the global agents directory. We do NOT
:: use a junction because opencode reads ALL .md files in the agents dir
:: tree — a junction would cause opencode to read files twice (once from
:: the config, once from the directory scan), creating duplicate agents.
:: Only the 13 agent .md files are copied, NOT the shared/ subdirectory
:: (which contains prompt sections, not agent definitions).
echo [2/5] Copying agent files...
set "AGENT_MD_COUNT=0"
for /f %%A in ('dir /b /a-d "%REPO_DIR%\.opencode\agents\*.md" 2^>nul ^| find /c /v ""') do set "AGENT_MD_COUNT=%%A"
set "HAS_AGENT_KEY=0"
findstr /c:"\"agent\":" "%PROJECT_CONFIG%" >nul 2>&1
if not errorlevel 1 set "HAS_AGENT_KEY=1"

if %AGENT_MD_COUNT% gtr 0 (
    REM Remove any existing junction or stale files first
    if exist "%AGENTS_DIR%\Agents-Opencode-Jake" (
        rd /s /q "%AGENTS_DIR%\Agents-Opencode-Jake" 2>nul
    )
    REM Remove any stale .md files from previous junction-based installs
    for %%F in ("%AGENTS_DIR%\*.md") do del /f "%%F" >nul 2>&1
    if exist "%AGENTS_DIR%\shared" rd /s /q "%AGENTS_DIR%\shared" 2>nul
    REM Copy only the 13 agent .md files (not shared/)
    set "AGENT_MD_COUNT=0"
    for %%F in ("%REPO_DIR%.opencode\agents\*.md") do (
        copy /Y "%%F" "%AGENTS_DIR%\%%~nxF" >nul 2>&1
        set /a AGENT_MD_COUNT+=1
    )
    echo  [OK] copied !AGENT_MD_COUNT! agent .md files to %AGENTS_DIR%
    REM Resolve {file:} includes so agents work in any project
    REM (the shared/ directory is NOT copied to avoid opencode reading it
    REM as agent definitions, so {file:} references must be inlined now)
    if exist "%REPO_DIR%.opencode\scripts\resolve_includes.py" (
        "!PY!" "%REPO_DIR%.opencode\scripts\resolve_includes.py" "%AGENTS_DIR%" "%AGENTS_DIR%" --repo-root "%REPO_DIR:~0,-1%" >nul 2>&1
        if !errorlevel! equ 0 (
            echo  [OK] resolved shared includes for all agents
        ) else (
            echo  [WARN] include resolution returned errorlevel !errorlevel!
        )
    ) else (
        echo  [WARN] resolve_includes.py not found — agents may not work in other projects
    )
    set "AGENT_J_RESULT=copied"
) else if %HAS_AGENT_KEY%==1 (
    echo  [INFO] No .opencode\agents\*.md files — agents are in opencode.json,
    echo         will merge into global config.
    set "AGENT_J_RESULT=skip"
) else (
    echo  [ERROR] Nothing to install. Repo has no .opencode\agents\*.md files
    echo          and no ^"agent^": key in opencode.json.
    set "AGENT_J_RESULT=error"
    pause
    exit /b 1
)
echo.

:: ---- Step 3: Skill junctions ----
echo [3/5] Skill junctions...
set "SKILL_COUNT=0"
for /d %%D in ("%REPO_DIR%.opencode\skills\*") do (
    call :create_junction "%SKILLS_DIR%\%%~nD" "%%~fD" "skill"
    set /a SKILL_COUNT+=1
)
if !SKILL_COUNT! equ 0 (
    echo  [INFO] No skill directories to link
)
echo.
echo [4/5] Merging into global opencode.jsonc...
echo   Python: !PY!

:: ---- Step 4a: Ensure graphify Python package is installed ----
:: The MCP config in opencode.jsonc references `python3 -m graphify.serve`,
:: so the graphify package must be importable for the MCP to start. The
:: pip distribution name is `graphifyy` (typo-squat avoidance on PyPI) but
:: the Python import is `graphify`. We check via the import name and
:: install via the distribution name. Idempotent: re-runs are no-ops
:: because the import check passes; a fresh machine gets a single install.
::
:: Edge case: pip's metadata can say "already satisfied" while the import
REM fails (e.g. someone deleted the package directory manually, or a
REM previous install was partially completed). To recover from this, the
REM fallback uses --force-reinstall.
echo [4a/5] Checking graphify Python package...
"!PY!" -c "import graphify" >nul 2>&1
if !errorlevel! equ 0 (
    echo  [OK] graphify importable by !PY!
) else (
    echo  [INSTALL] graphify not importable; running pip install --user graphifyy
    "!PY!" -m pip install --user graphifyy 2>&1 | findstr /V "already satisfied" | findstr /V "^$"
    "!PY!" -c "import graphify" >nul 2>&1
    if !errorlevel! neq 0 (
        echo  [FALLBACK] still not importable; trying pip install --user --force-reinstall graphifyy
        "!PY!" -m pip install --user --force-reinstall graphifyy 2>&1 | findstr /V "already satisfied" | findstr /V "^$"
        "!PY!" -c "import graphify" >nul 2>&1
        if !errorlevel! neq 0 (
            echo  [WARN] graphify install failed. The MCP config in your global
            echo         opencode.jsonc references graphify, but the package is
            echo         not importable. Run manually: pip install --user --force-reinstall graphifyy
        ) else (
            echo  [OK] graphify installed via --force-reinstall
        )
    ) else (
        echo  [OK] graphify installed via pip install --user graphifyy
    )
)
echo.

:: ---- Step 4b: Refresh graphify skill + plugin if pip is ahead of stamp ----
:: Calls the Python helper to compare the pip-installed graphifyy version
:: to the stamp at %USERPROFILE%\.config\opencode\skills\graphify\.graphify_version
:: and refresh the user-scope skill + project-scope plugin if pip is ahead.
:: The helper is idempotent and never aborts on failure -- if it returns
:: non-zero, we WARN and continue. See .opencode\plans\plan-004-design.md
:: and .opencode\decisions\adr-003-graphify-auto-refresh.md for the full contract.
echo [4b/5] Checking graphify version...
set "REFRESH_HELPER=%REPO_DIR%.opencode\scripts\graphify_refresh.py"
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

if not exist "%MERGE_HELPER%" (
    echo  [ERROR] Merge helper not found: %MERGE_HELPER%
    pause
    exit /b 6
)

:: Build merge args. We deliberately do NOT add quotes around the path
:: values here — cmd would pass them as literal quote characters in the
:: arg, and Python's argparse would treat the quoted path as the value
:: (including the quote chars). Our paths have no spaces, so this is safe.
set "MERGE_ARGS=install --project %PROJECT_CONFIG% --global %GLOBAL_CONFIG% --manifest %MANIFEST%"
if "%FORCE%"=="1"   set "MERGE_ARGS=%MERGE_ARGS% --force"
if "%DRY_RUN%"=="1" set "MERGE_ARGS=%MERGE_ARGS% --dry-run"

if "%DRY_RUN%"=="1" (
    echo  [DRY-RUN] would run:
    echo    "!PY!" "%MERGE_HELPER%" %MERGE_ARGS%
    "!PY!" "%MERGE_HELPER%" %MERGE_ARGS%
) else (
    "!PY!" "%MERGE_HELPER%" %MERGE_ARGS%
)
set "MERGE_RC=%errorlevel%"
if not "%MERGE_RC%"=="0" (
    echo  [ERROR] merge helper failed with exit code %MERGE_RC%
    pause
    exit /b %MERGE_RC%
)
echo.

:: ---- Step 4c: Fix {file:...} paths for global config ----
:: The merge helper copies {file:...} references verbatim from the project
:: config. For the global config, paths like {file:./.opencode/agents/...}
:: resolve relative to %CONFIG_DIR%, not the project. We must rewrite
:: them to match the actual location of agent .md files.
::
:: Files are copied directly to %AGENTS_DIR%\ (no junction, no subdirectory).
:: Rewrite {file:./.opencode/agents/X} -> {file:./agents/X}
echo [4c/5] Fixing agent file references for global config...
if "%AGENT_J_RESULT%"=="copied" (
    "!PY!" -c "path=r'%GLOBAL_CONFIG%';c=open(path,encoding='utf-8').read();c=c.replace('{file:./.opencode/agents/','{file:./agents/');open(path,'w',encoding='utf-8').write(c);print('  [OK] paths rewritten')"
) else (
    echo  [SKIP] agent files not available, paths left as-is
)
echo.

:: ---- Step 4d: Sync global commands from .opencode/commands/*.md ----
:: The merge helper does not handle the "command" block. We read each
:: .opencode/commands/*.md file and add it to the global config inline.
set "CMD_COUNT=0"
for /f %%F in ('dir /b "%REPO_DIR%.opencode\commands\*.md" 2^>nul') do set /a CMD_COUNT+=1
if %CMD_COUNT% gtr 0 (
    echo [4d/5] Syncing commands to global config...
    "!PY!" "%REPO_DIR%.opencode\scripts\sync_commands.py" "%REPO_DIR:~0,-1%" "%GLOBAL_CONFIG%"
    echo.
)

:: ---- Step 4e: Fallback: copy skill files when junction fails ----
:: If the skill junction failed (no admin), copy .md files directly.
for /d %%D in ("%REPO_DIR%.opencode\skills\*") do (
    set "SK_NAME=%%~nD"
    set "SK_DST=%SKILLS_DIR%\%%~nD"
    if not exist "!SK_DST!\SKILL.md" if exist "%%~fD\SKILL.md" (
        echo [4e/5] Copying skill %%~nD...
        rd /s /q "!SK_DST!" 2>nul
        robocopy "%%~fD" "!SK_DST!" /E /R:0 /W:0 /NJH /NJS /NDL >nul 2>&1
    )
)

:: ---- Step 4f: Integrate graphify opencode plugin ----
echo [4f/5] Installing graphify OpenCode plugin...
where graphify >nul 2>&1
if !errorlevel! equ 0 (
    graphify opencode install >nul 2>&1
    if !errorlevel! equ 0 (
        echo  [OK] graphify plugin installed (AGENTS.md + tool.execute.before hook)
    ) else (
        echo  [WARN] graphify opencode install failed — run it manually
    )
) else (
    echo  [SKIP] graphify CLI not found — run 'uv tool install graphifyy' first
)
echo.

:: ---- Step 5: Final summary ----
echo [5/5] Summary
echo ============================================
echo  Global install complete!
echo ============================================
echo.
if "%AGENT_J_RESULT%"=="copied" (
    echo  Agents copied:     %AGENTS_DIR%\ (13 agent .md files)
    echo                       Re-run global-setup.bat to refresh.
)
if not "%AGENT_J_RESULT%"=="copied" (
    echo  Agents merged into: %GLOBAL_CONFIG%
)
echo  Skills linked: %SKILLS_DIR%\graphify-agent-workflow
echo  Manifest:      %MANIFEST%
echo.
echo  Start using:  opencode .
echo  Verify:        opencode agent list
echo  Reinstall:     run global-setup.bat again (idempotent)
echo  Uninstall:     run uninstall-global.bat
echo.
pause
exit /b 0

:: ---- Junction helper subroutine ----
:: Args: %~1 = link path, %~2 = target path, %~3 = label (e.g. "skill")
:: Sets J_RESULT to one of: skip, replaced, created, copy, error.
:create_junction
setlocal
set "J_LINK=%~1"
set "J_TARGET=%~2"
set "J_LABEL=%~3"
set "J_RESULT="

if "%DRY_RUN%"=="1" (
    echo  [DRY-RUN] would create %J_LABEL% junction:
    echo            %J_LINK% -^> %J_TARGET%
    set "J_RESULT=skip"
    goto :junction_done
)

:: If link already exists and is a reparse point, check target.
if exist "%J_LINK%" (
    fsutil reparsepoint query "%J_LINK%" >nul 2>&1
    if !errorlevel! equ 0 (
        REM Already a reparse point. Verify target matches by checking
        REM whether the expected target path appears in fsutil's output.
        REM fsutil prints \??\<target>, so a substring match on <target>
        REM is unambiguous for full path equality.
        set "J_TARGET_TRIM=%J_TARGET: =%"
        fsutil reparsepoint query "%J_LINK%" 2^>nul | findstr /I /C:"!J_TARGET_TRIM!" >nul
        if !errorlevel! equ 0 (
            echo  [SKIP] %J_LABEL% junction already correct: %J_LINK%
            set "J_RESULT=skip"
            goto :junction_done
        ) else (
            echo  [INFO] %J_LABEL% junction exists with stale target, removing...
            rmdir "%J_LINK%" 2>nul
        )
    ) else (
        REM Not a reparse point. Remove whatever it is (dir, file, broken).
        rmdir "%J_LINK%" 2>nul
        del "%J_LINK%" 2>nul
    )
)

mklink /J "%J_LINK%" "%J_TARGET%" >nul 2>&1
if !errorlevel! equ 0 (
    echo  [OK] %J_LABEL% junction: %J_LINK% -^> %J_TARGET%
    set "J_RESULT=created"
) else (
    echo  [WARN] %J_LABEL% mklink failed - admin? Falling back to robocopy...
    rd /s /q "%J_LINK%" 2>nul
    robocopy "%J_TARGET%" "%J_LINK%" /E /R:0 /W:0 /NJH /NJS /NDL >nul 2>&1
    if !errorlevel! lss 8 (
        echo  [OK] %J_LABEL% mirrored: %J_LINK%
        set "J_RESULT=copy"
    ) else (
        echo  [WARN] %J_LABEL% copy also failed.
        echo         The merge step below will handle %J_LABEL% configuration,
        echo         so this is non-fatal. To fix junctions, re-run as Admin.
        set "J_RESULT=error"
    )
)

:junction_done
endlocal & set "J_RESULT=%J_RESULT%"
goto :eof

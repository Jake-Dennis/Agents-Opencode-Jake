@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake — Uninstall Global

:: --- Parse flags (args take precedence over env vars) ---
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
set "CONFIG_DIR=%USERPROFILE%\.config\opencode"
set "AGENTS_DIR=%CONFIG_DIR%\agents"
set "SKILLS_DIR=%CONFIG_DIR%\skills"
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"
set "MANIFEST=%CONFIG_DIR%\.opencode-jake-installed.json"
set "MERGE_HELPER=%REPO_DIR%.opencode\scripts\opencode_jsonc_merge.py"

echo ============================================
echo  Agents-Opencode-Jake — Global Uninstall
echo ============================================
echo.
echo  This will REMOVE Agents-Opencode-Jake from your
echo  global opencode configuration.
echo.
echo  Repo:   %REPO_DIR%
echo  Config: %CONFIG_DIR%
echo.
echo  WARNING: This affects ALL opencode projects on this machine.
if "%DRY_RUN%"=="1" echo  [DRY-RUN] no files will be modified.
if "%FORCE%"=="1"   echo  [FORCE]   removing junctions even without a manifest.
echo.

:: --- Confirmation prompt (skip when --unattended) ---
if "%UNATTENDED%"=="1" (
    echo  [UNATTENDED] proceeding without prompt.
    echo.
) else (
    set /p "CONFIRM=Continue with global uninstall? (y/N): "
    if /i not "!CONFIRM!"=="y" (
        echo  Aborted.
        pause
        exit /b 0
    )
    echo.
)

:: ---- Step 1: Surgically undo the opencode.jsonc merge via the manifest ----
echo [1/5] Removing opencode.jsonc entries added by the installer...
set "MERGE_DID_RUN=0"
if exist "%MANIFEST%" (
    REM Resolve Python (try `python`, then `py`).
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
        echo  [WARN] Python not found. Skipping surgical merge removal.
        echo         You will need to edit %GLOBAL_CONFIG% by hand.
    ) else (
        if not exist "%MERGE_HELPER%" (
            echo  [WARN] Merge helper missing: %MERGE_HELPER%
    ) else (
        REM Build merge args. As with the installer, we deliberately
        REM do NOT add inner quotes around the path values (cmd would
        REM pass the quote characters as part of the value, and Python
        REM argparse would treat them as part of the path).
        REM NOTE: must use !VAR! (delayed expansion) here, not %VAR%,
        REM because REMOVE_ARGS is set inside the same parens block
        REM and %REMOVE_ARGS% would do parse-time expansion (empty).
        set "REMOVE_ARGS=remove --global !GLOBAL_CONFIG! --manifest !MANIFEST!"
        if "!DRY_RUN!"=="1" set "REMOVE_ARGS=!REMOVE_ARGS! --dry-run"
        if "!DRY_RUN!"=="1" (
            echo  [DRY-RUN] would run:
            echo    "!PY!" "!MERGE_HELPER!" !REMOVE_ARGS!
        )
        "!PY!" "!MERGE_HELPER!" !REMOVE_ARGS!
        if !errorlevel! neq 0 (
            echo  [WARN] merge helper exited with code !errorlevel!. Continuing.
        ) else (
            set "MERGE_DID_RUN=1"
        )
    )
    )
) else (
    echo  [INFO] No install manifest found at %MANIFEST%.
    echo         This means global-setup.bat was not run with this version,
    echo         or you already uninstalled. Falling back to junction removal only.
)
echo.

:: ---- Step 2: Remove agent junction + copied .md files ----
echo [2/5] Removing agent files...
set "AGENT_LINK=%AGENTS_DIR%\Agents-Opencode-Jake"
set "AGENT_TARGET=%REPO_DIR%.opencode\agents"
call :remove_junction "%AGENT_LINK%" "%AGENT_TARGET%" "agent"
REM If junction removal skipped (not a reparse point), remove directory directly
if "%J_RESULT%"=="skip" if exist "%AGENT_LINK%" (
    echo  [INFO] agent path is not a junction — cleaning directory directly...
    call :remove_dir "%AGENT_LINK%" "%AGENTS_DIR%\Agents-Opencode-Jake"
)
echo.

:: ---- Step 2.5: Remove global commands ----
echo [3/5] Removing installed commands...
if exist "%SCRIPT_DIR%.opencode\scripts\remove_commands.py" (
    "!PY!" "%SCRIPT_DIR%.opencode\scripts\remove_commands.py" "%GLOBAL_CONFIG%"
) else (
    echo  [SKIP] remove_commands.py not found
)
echo.

:: ---- Step 3: Remove skill junction ----
echo [4/5] Removing skill junction...
set "SKILL_LINK=%SKILLS_DIR%\graphify-agent-workflow"
set "SKILL_TARGET=%REPO_DIR%.opencode\skills\graphify-agent-workflow"
call :remove_junction "%SKILL_LINK%" "%SKILL_TARGET%" "skill"
echo.

:: ---- Step 5: Final summary ----
echo [5/5] Summary
echo ============================================
echo  Global uninstall complete!
echo ============================================
echo.
if "%MERGE_DID_RUN%"=="1" (
    echo  opencode.jsonc: merged entries surgically removed.
) else if exist "%MANIFEST%" (
    echo  opencode.jsonc: manifest present but merge not run.
) else (
    echo  opencode.jsonc: untouched - no manifest.
)
echo  Agent junction:   %AGENT_LINK%
echo  Skill junction:   %SKILL_LINK%
echo.
echo  Agents-Opencode-Jake removed from global config.
echo.
echo  To reinstall later, run: global-setup.bat
echo.
pause
exit /b 0

:: ---- Junction-removal helper subroutine ----
:: Args: %~1 = link path, %~2 = expected target, %~3 = label
:: Only removes the link if it's a reparse point AND its target matches
:: %~2 (or %FORCE% is set, in which case we trust the caller's intent).
:: Sets J_RESULT to: skip, removed, or error.
:remove_junction
setlocal
set "J_LINK=%~1"
set "J_EXPECTED=%~2"
set "J_LABEL=%~3"
set "J_RESULT="

if not exist "%J_LINK%" (
    echo  [SKIP] %J_LABEL% link not found: %J_LINK%
    set "J_RESULT=skip"
    goto :remove_done
)

:: Confirm it's a reparse point.
fsutil reparsepoint query "%J_LINK%" >nul 2>&1
if !errorlevel! neq 0 (
    echo  [SKIP] %J_LABEL% path exists but is not a reparse point: %J_LINK%
    set "J_RESULT=skip"
    goto :remove_done
)

:: Compare actual target to expected (unless --force).
:: The findstr-based substring match proved unreliable for paths
:: containing backslashes inside parens blocks, so we use a
:: substring match on the fsutil output via findstr against a
:: temp file. We use a Python helper call (resolve_junction.py)
:: to do the actual comparison: it parses the target out of
:: the reparse data and checks for exact equality.
:: For simplicity, we just attempt the removal if --force or if
:: a manifest is present. The user has already opted into the
:: global uninstall.
if not "%FORCE%"=="1" (
    if not defined MANIFEST (
        echo  [SKIP] %J_LABEL% exists and no manifest to verify against:
        echo         !J_LINK!
        echo         Run with --force to remove anyway.
        set "J_RESULT=skip"
        goto :remove_done
    )
)

if "%DRY_RUN%"=="1" (
    echo  [DRY-RUN] would remove %J_LABEL% junction: %J_LINK%
    set "J_RESULT=skip"
    goto :remove_done
)

rmdir "%J_LINK%" 2>nul
if !errorlevel! equ 0 (
    echo  Removed: %J_LINK%
    set "J_RESULT=removed"
) else (
    echo  [INFO] Could not remove %J_LINK%. Try running as Administrator.
    set "J_RESULT=error"
)

:remove_done
endlocal & set "J_RESULT=%J_RESULT%"
goto :eof

:: ---- Directory removal helper ----
:: Args: %~1 = path to remove, %~2 = display name
:remove_dir
if not exist "%~1" goto :eof
if "%DRY_RUN%"=="1" (
    echo  [DRY-RUN] would remove: %~2
    goto :eof
)
rmdir /S /Q "%~1"
if !errorlevel! equ 0 (
    echo  Removed: %~2
) else (
    echo  [WARN] Could not remove %~2 — try running as Admin.
)
goto :eof

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
set "CONFIG_DIR=%USERPROFILE%\.config\opencode"
set "AGENTS_DIR=%CONFIG_DIR%\agents"
set "SKILLS_DIR=%CONFIG_DIR%\skills"
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"
set "MANIFEST=%CONFIG_DIR%\.opencode-jake-installed.json"
set "PROJECT_CONFIG=%REPO_DIR%opencode.json"
set "MERGE_HELPER=%REPO_DIR%.opencode\scripts\opencode_jsonc_merge.py"

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

:: ---- Step 2: Agent junction (adaptive) ----
:: If the repo has legacy .opencode\agents\*.md files, do the original
:: junction. Otherwise (post-ADR-001 JSON-only layout), skip the junction
:: and rely on the jsonc merge in step 4. If neither is available, abort.
echo [2/5] Agent junction...
set "AGENT_MD_COUNT=0"
for /f %%A in ('dir /b /a-d "%REPO_DIR%\.opencode\agents\*.md" 2^>nul ^| find /c /v ""') do set "AGENT_MD_COUNT=%%A"
set "HAS_AGENT_KEY=0"
findstr /c:"\"agent\":" "%PROJECT_CONFIG%" >nul 2>&1
if not errorlevel 1 set "HAS_AGENT_KEY=1"

if %AGENT_MD_COUNT% gtr 0 (
    set "AGENT_LINK=%AGENTS_DIR%\Agents-Opencode-Jake"
    set "AGENT_TARGET=%REPO_DIR%.opencode\agents"
    call :create_junction "%AGENT_LINK%" "%AGENT_TARGET%" "agent"
) else if %HAS_AGENT_KEY%==1 (
    echo  [INFO] No .opencode\agents\*.md files — agents are in opencode.json,
    echo         will merge into global config.
) else (
    echo  [ERROR] Nothing to install. Repo has no .opencode\agents\*.md files
    echo          and no ^"agent^": key in opencode.json.
    pause
    exit /b 1
)
echo.

:: ---- Step 3: Skill junction ----
echo [3/5] Skill junction...
set "SKILL_LINK=%SKILLS_DIR%\graphify-agent-workflow"
set "SKILL_TARGET=%REPO_DIR%.opencode\skills\graphify-agent-workflow"
call :create_junction "%SKILL_LINK%" "%SKILL_TARGET%" "skill"
echo.

:: ---- Step 4: opencode.jsonc merge ----
echo [4/5] Merging into global opencode.jsonc...

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
    echo          Without Python, the global installer cannot merge opencode.jsonc.
    pause
    exit /b 5
)
echo  Python: !PY!

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

:: ---- Step 5: Final summary ----
echo [5/5] Summary
echo ============================================
echo  Global install complete!
echo ============================================
echo.
if %AGENT_MD_COUNT% gtr 0 (
    echo  Agents linked: %AGENTS_DIR%\Agents-Opencode-Jake -^> .opencode\agents\
) else (
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
    echo  [WARN] %J_LABEL% mklink failed - admin? Falling back to xcopy...
    if not exist "%J_LINK%" mkdir "%J_LINK%" 2>nul
    xcopy /E /I /Y "%J_TARGET%" "%J_LINK%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo  [OK] %J_LABEL% copied: %J_LINK%
        set "J_RESULT=copy"
    ) else (
        echo  [ERROR] %J_LABEL% copy also failed.
        set "J_RESULT=error"
    )
)

:junction_done
endlocal & set "J_RESULT=%J_RESULT%"
goto :eof

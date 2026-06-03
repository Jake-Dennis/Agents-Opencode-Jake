@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake — Uninstall Global

set "REPO_DIR=%~dp0"
set "CONFIG_DIR=%USERPROFILE%\.config\opencode"
set "AGENTS_DIR=%CONFIG_DIR%\agents"
set "SKILLS_DIR=%CONFIG_DIR%\skills"
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"

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
echo.

set /p CONFIRM=Continue with global uninstall? (y/N): 
if /i not "!CONFIRM!"=="y" (
    echo  Aborted.
    pause
    exit /b 0
)
echo.

:: ---- Step 1: Remove agent symlink ----
echo [1/4] Removing agent symlink...
set "AGENT_LINK=%AGENTS_DIR%\Agents-Opencode-Jake"
if exist "%AGENT_LINK%" (
    rmdir "%AGENT_LINK%" 2>nul
    del "%AGENT_LINK%" 2>nul
    if !errorlevel! equ 0 (
        echo  Removed: %AGENT_LINK%
    ) else (
        echo  [INFO] Could not remove %AGENT_LINK%. Try running as Administrator.
    )
) else (
    echo  [SKIP] Agent link not found: %AGENT_LINK%
)
echo.

:: ---- Step 2: Remove skill symlink ----
echo [2/4] Removing skill symlink...
set "SKILL_LINK=%SKILLS_DIR%\graphify-agent-workflow"
if exist "%SKILL_LINK%" (
    rmdir "%SKILL_LINK%" 2>nul
    del "%SKILL_LINK%" 2>nul
    if !errorlevel! equ 0 (
        echo  Removed: %SKILL_LINK%
    ) else (
        echo  [INFO] Could not remove %SKILL_LINK%. Try running as Administrator.
    )
) else (
    echo  [SKIP] Skill link not found: %SKILL_LINK%
)
echo.

:: ---- Step 3: Clean up empty config directories ----
echo [3/4] Cleaning up empty config directories...
if exist "%AGENTS_DIR%" (
    dir "%AGENTS_DIR%" /b >nul 2>&1
    if !errorlevel! neq 0 (
        rmdir "%AGENTS_DIR%" 2>nul
        echo  Removed empty: %AGENTS_DIR%
    ) else (
        echo  [SKIP] %AGENTS_DIR% has other agent entries, not removed.
    )
) else (
    echo  [SKIP] %AGENTS_DIR% does not exist.
)
if exist "%SKILLS_DIR%" (
    dir "%SKILLS_DIR%" /b >nul 2>&1
    if !errorlevel! neq 0 (
        rmdir "%SKILLS_DIR%" 2>nul
        echo  Removed empty: %SKILLS_DIR%
    ) else (
        echo  [SKIP] %SKILLS_DIR% has other skill entries, not removed.
    )
) else (
    echo  [SKIP] %SKILLS_DIR% does not exist.
)
if exist "%CONFIG_DIR%" (
    dir "%CONFIG_DIR%" /b >nul 2>&1
    if !errorlevel! neq 0 (
        rmdir "%CONFIG_DIR%" 2>nul
        echo  Removed empty: %CONFIG_DIR%
    ) else (
        echo  [SKIP] %CONFIG_DIR% has other config files, not removed.
    )
)
echo.

:: ---- Step 4: Update or remove global opencode.jsonc ----
echo [4/4] Updating global opencode.jsonc...
if exist "%GLOBAL_CONFIG%" (
    echo.
    echo  Global config exists at: %GLOBAL_CONFIG%
    echo.
    echo  Options:
    echo    1. Remove the entire file
    echo    2. Keep it as-is (you'll edit it manually)
    echo    3. Show me the file so I can edit it
    echo.
    set /p GLOBAL_CHOICE=Choose (1/2/3): 
    if "!GLOBAL_CHOICE!"=="1" (
        del "%GLOBAL_CONFIG%"
        echo  Removed: %GLOBAL_CONFIG%
        if exist "%CONFIG_DIR%" (
            dir "%CONFIG_DIR%" /b >nul 2>&1
            if !errorlevel! neq 0 (
                rmdir "%CONFIG_DIR%" 2>nul
            )
        )
    ) else if "!GLOBAL_CHOICE!"=="3" (
        echo.
        echo  --- %GLOBAL_CONFIG% ---
        type "%GLOBAL_CONFIG%"
        echo.
        echo  -------------------------
        echo.
        echo  Remove the lines referencing this repo:
        echo    "skills": { "paths": [...] },
        echo    "instructions": [...]
        echo.
    ) else (
        echo  [SKIP] %GLOBAL_CONFIG% retained.
    )
) else (
    echo  [SKIP] No global config found at %GLOBAL_CONFIG%
)
echo.

echo ============================================
echo  Global uninstall complete!
echo ============================================
echo.
echo  Agents-Opencode-Jake removed from global config.
echo.
echo  To reinstall later, run: global-setup.bat
echo.
pause

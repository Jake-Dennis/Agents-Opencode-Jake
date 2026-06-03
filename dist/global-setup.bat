@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake — Global Installer

set "REPO_DIR=%~dp0"
set "CONFIG_DIR=%USERPROFILE%\.config\opencode"
set "AGENTS_DIR=%CONFIG_DIR%\agents"
set "SKILLS_DIR=%CONFIG_DIR%\skills"

echo ============================================
echo  Agents-Opencode-Jake — Global Installer
echo ============================================
echo.
echo  Repo:  %REPO_DIR%
echo  Config: %CONFIG_DIR%
echo.
echo  WARNING: This installs agents and skills globally
echo  for ALL opencode projects on this machine.
echo  Run setup.bat instead for local/per-project setup.
echo.

set /p CONFIRM=Continue with global install? (y/N): 
if /i not "!CONFIRM!"=="y" (
    echo  Aborted.
    pause
    exit /b 0
)
echo.

:: ---- Step 1: Ensure config directories exist ----
echo [1/4] Ensuring global config directories exist...
if not exist "%AGENTS_DIR%" mkdir "%AGENTS_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"
echo.

:: ---- Step 2: Symlink agents ----
echo [2/4] Installing agents...
set "AGENT_LINK=%AGENTS_DIR%\Agents-Opencode-Jake"
if exist "%AGENT_LINK%" (
    echo  Removing existing symlink...
    rmdir "%AGENT_LINK%" 2>nul
    del "%AGENT_LINK%" 2>nul
)

mklink /J "%AGENT_LINK%" "%REPO_DIR%.opencode\agents" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Agents linked: %AGENT_LINK% -^> .opencode\agents\
) else (
    echo  [INFO] Symlink failed (may need admin). Copying instead...
    xcopy /E /I /Y "%REPO_DIR%.opencode\agents" "%AGENT_LINK%" >nul
    echo  Agents copied to: %AGENT_LINK%
)
echo.

:: ---- Step 3: Symlink skills ----
echo [3/4] Installing skills...
set "SKILL_LINK=%SKILLS_DIR%\graphify-agent-workflow"
if exist "%SKILL_LINK%" (
    echo  Removing existing symlink...
    rmdir "%SKILL_LINK%" 2>nul
    del "%SKILL_LINK%" 2>nul
)

mklink /J "%SKILL_LINK%" "%REPO_DIR%.opencode\skills\graphify-agent-workflow" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Skills linked: %SKILL_LINK%
) else (
    echo  [INFO] Symlink failed. Copying instead...
    xcopy /E /I /Y "%REPO_DIR%.opencode\skills\graphify-agent-workflow" "%SKILL_LINK%" >nul
    echo  Skills copied to: %SKILL_LINK%
)
echo.

:: ---- Step 4: Update global opencode.jsonc ----
echo [4/4] Updating global config...
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"

if not exist "%GLOBAL_CONFIG%" (
    echo  Creating new global config at %GLOBAL_CONFIG%...
    (
        echo {^
        echo   "$schema": "https://opencode.ai/config.json",^
        echo   "default_agent": "conductor",^
        echo   "skills": { "paths": ["%SKILLS_DIR%"] },^
        echo   "instructions": ["%REPO_DIR%AGENTS.md"]^
        echo }
    ) > "%GLOBAL_CONFIG%"
    echo  Created: %GLOBAL_CONFIG%
) else (
    echo.
    echo  NOTE: Global config already exists at:
    echo    %GLOBAL_CONFIG%
    echo.
    echo  To enable these agents globally, add these lines to it:
    echo.
    echo    "skills": { "paths": ["%SKILLS_DIR%"] },
    echo    "instructions": ["%REPO_DIR%AGENTS.md"]
    echo.
    echo  Or add per-project in your project's opencode.json:
    echo.
    echo    "instructions": ["%REPO_DIR%AGENTS.md"]
    echo.
)
echo.

echo ============================================
echo  Global install complete!
echo ============================================
echo.
echo  Agents installed to: %AGENT_LINK%
echo  Skills installed to: %SKILL_LINK%
echo.
echo  Start using: opencode .
echo.
echo  First time? Run: /graphify .
echo  to build the knowledge graph.
echo.
pause

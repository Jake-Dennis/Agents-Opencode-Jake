@echo off
setlocal enabledelayedexpansion

title Agents-Opencode-Jake Setup

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

:: ---- Step 1: Ensure config directories exist ----
echo [1/4] Ensuring global config directories exist...
if not exist "%AGENTS_DIR%" mkdir "%AGENTS_DIR%"
if not exist "%SKILLS_DIR%" mkdir "%SKILLS_DIR%"

:: ---- Step 2: Symlink agents ----
echo [2/4] Symlinking agents...
set "AGENT_LINK=%AGENTS_DIR%\Agents-Opencode-Jake"
if exist "%AGENT_LINK%" (
    echo  Warning: Symlink already exists. Removing...
    rmdir "%AGENT_LINK%" 2>nul
    del "%AGENT_LINK%" 2>nul
)

:: Create directory junction (works on Windows without admin)
mklink /J "%AGENT_LINK%" "%REPO_DIR%.opencode\agents" >nul 2>&1
if %errorlevel% equ 0 (
    echo  Agents linked: %AGENT_LINK% -^> .opencode\agents\
) else (
    echo  [INFO] Symlink failed (may need admin). Copying instead...
    xcopy /E /I /Y "%REPO_DIR%.opencode\agents" "%AGENT_LINK%" >nul
    echo  Agents copied to: %AGENT_LINK%
)

:: ---- Step 3: Symlink skills ----
echo [3/4] Symlinking skills...
set "SKILL_LINK=%SKILLS_DIR%\graphify-agent-workflow"
if exist "%SKILL_LINK%" (
    echo  Warning: Skill symlink already exists. Removing...
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

:: ---- Step 4: Update global opencode.jsonc ----
echo [4/4] Updating global config...
set "GLOBAL_CONFIG=%CONFIG_DIR%\opencode.jsonc"

if not exist "%GLOBAL_CONFIG%" (
    echo  Creating new global config...
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
echo  Setup complete!
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
echo  Press any key to exit.
pause >nul

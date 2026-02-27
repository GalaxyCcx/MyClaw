@echo off
if not "%~1"=="RUN" (
    start "MyClaw Startup" cmd /k "%~f0" RUN
    exit /b
)
setlocal
title MyClaw Agent Platform

echo.
echo ======================================
echo         MyClaw Agent Platform
echo            Start Script
echo ======================================
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV=%BACKEND%\.venv"
set "PIP=%VENV%\Scripts\pip.exe"
set "PY=%VENV%\Scripts\python.exe"
set "DEPS_MARKER=%VENV%\.deps_installed"

rem 1) Check runtime
echo [1/5] Checking runtime...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    goto :error_exit
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo   Python: %PY_VER%

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    goto :error_exit
)
for /f %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
echo   Node.js: %NODE_VER%
echo.

rem 2) Python virtual env
echo [2/5] Preparing Python virtual environment...
if not exist "%PY%" (
    echo   Creating virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :error_exit
    )
)
echo   OK
echo.

rem 3) Install backend dependencies
echo [3/5] Checking backend dependencies...
if not exist "%DEPS_MARKER%" (
    echo   Installing requirements.txt...
    "%PIP%" install -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install backend requirements.
        goto :error_exit
    )
    echo   Installing requirements-skills.txt...
    "%PIP%" install -r "%BACKEND%\requirements-skills.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install skill requirements.
        goto :error_exit
    )
    > "%DEPS_MARKER%" echo installed
) else (
    echo   Dependencies already installed.
)
echo   Ensuring mcp[cli] for browser automation...
"%PIP%" install "mcp[cli]>=1.0" -q
if errorlevel 1 (
    echo [WARN] mcp install failed, MCP Chrome may not work.
) else (
    echo   mcp OK
)
echo.

rem 4) Install frontend and bridge dependencies
echo [4/5] Checking frontend and bridge dependencies...
if not exist "%FRONTEND%\node_modules" (
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] Failed to install frontend dependencies.
        goto :error_exit
    )
    popd
) else (
    echo   Frontend dependencies OK.
)
if not exist "%BACKEND%\node_modules" (
    echo   Installing mcp-chrome-bridge...
    pushd "%BACKEND%"
    call npm install
    if errorlevel 1 (
        popd
        echo [WARN] Failed to install mcp-chrome-bridge. Browser automation may not work.
    ) else (
        popd
        echo   mcp-chrome-bridge OK
    )
) else (
    echo   Bridge dependencies OK.
)
if exist "%BACKEND%\patches" (
    echo   Applying patches ^(mcp-chrome-bridge multi-connection fix^)...
    pushd "%BACKEND%"
    call npx patch-package
    if errorlevel 1 (
        echo   [WARN] Patch apply failed. MCP Chrome may have connection issues.
    ) else (
        echo   Patches OK
    )
    popd
)
if exist "%BACKEND%\node_modules\mcp-chrome-bridge" (
    echo   Registering bridge with Chrome ^(Native Messaging^)...
    pushd "%BACKEND%"
    cmd /c "npx mcp-chrome-bridge register --detect"
    if errorlevel 1 (
        echo   [WARN] Bridge registration failed. Run manually: cd backend ^&^& npx mcp-chrome-bridge register --detect
    ) else (
        echo   Bridge registered OK
    )
    popd
)
echo.

rem 5) Enable MCP and start services
echo [5/5] Enabling MCP and starting services...
"%PY%" "%BACKEND%\scripts\init_mcp.py"
if not exist "%BACKEND%\.env" (
    echo [WARN] backend\.env not found. Create it from backend\.env.example first.
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 .*LISTENING" 2^>nul') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 .*LISTENING" 2^>nul') do taskkill /F /PID %%p >nul 2>&1

pushd "%BACKEND%"
start "MyClaw-Backend" cmd /k "title MyClaw Backend && color 0A && ""%PY%"" -m uvicorn main:app --host 0.0.0.0 --port 8000"
popd

timeout /t 2 /nobreak >nul

pushd "%FRONTEND%"
start "MyClaw-Frontend" cmd /k "title MyClaw Frontend && color 0B && npm run dev"
popd

echo.
echo Started:
echo   Frontend: http://localhost:5173
echo   Backend : http://localhost:8000
echo   MCP Chrome: click Connect in extension to start bridge (port 12306)
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"
echo.
echo Press any key to close this window...
pause >nul
goto :eof

:error_exit
echo.
echo Startup failed. Check errors above.
pause

@echo off
chcp 65001 >nul 2>&1
title MyClaw Agent Platform

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       MyClaw Agent Platform          ║
echo  ║         一键启动脚本                 ║
echo  ╚══════════════════════════════════════╝
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV=%BACKEND%\.venv"
set "HAS_ERROR=0"

:: ──────────────────────────────────────
:: 1. 环境检查
:: ──────────────────────────────────────
echo [1/5] 检查运行环境...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [ERROR] 未检测到 Python，请先安装 Python 3.10+
    set "HAS_ERROR=1"
    goto :error_exit
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo   Python: %PY_VER%

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [ERROR] 未检测到 Node.js，请先安装 Node.js 18+
    set "HAS_ERROR=1"
    goto :error_exit
)
for /f %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
echo   Node.js: %NODE_VER%
echo   [OK] 环境检查通过
echo.

:: ──────────────────────────────────────
:: 2. Python 虚拟环境
:: ──────────────────────────────────────
echo [2/5] 配置 Python 虚拟环境...

if not exist "%VENV%\Scripts\python.exe" (
    echo   虚拟环境不存在，正在创建...
    python -m venv "%VENV%"
    if %ERRORLEVEL% neq 0 (
        echo   [ERROR] 创建虚拟环境失败
        set "HAS_ERROR=1"
        goto :error_exit
    )
    echo   [OK] 虚拟环境创建成功
) else (
    echo   [OK] 虚拟环境已存在
)
echo.

:: ──────────────────────────────────────
:: 3. 安装 Python 依赖
:: ──────────────────────────────────────
echo [3/5] 检查 Python 依赖...

set "PIP=%VENV%\Scripts\pip.exe"
set "PY=%VENV%\Scripts\python.exe"

:: 用一个标记文件记录依赖是否已安装
set "DEPS_MARKER=%VENV%\.deps_installed"

if not exist "%DEPS_MARKER%" (
    echo   首次运行，安装核心依赖...
    "%PIP%" install -r "%BACKEND%\requirements.txt" --quiet
    if %ERRORLEVEL% neq 0 (
        echo   [ERROR] 核心依赖安装失败
        set "HAS_ERROR=1"
        goto :error_exit
    )
    echo   安装 Skill 依赖...
    "%PIP%" install -r "%BACKEND%\requirements-skills.txt" --quiet
    if %ERRORLEVEL% neq 0 (
        echo   [ERROR] Skill 依赖安装失败
        set "HAS_ERROR=1"
        goto :error_exit
    )
    echo installed> "%DEPS_MARKER%"
    echo   [OK] 所有 Python 依赖安装完成
) else (
    echo   [OK] 依赖已安装（如需重装请删除 backend\.venv\.deps_installed）
)
echo.

:: ──────────────────────────────────────
:: 4. 安装前端依赖
:: ──────────────────────────────────────
echo [4/5] 检查前端依赖...

if not exist "%FRONTEND%\node_modules" (
    echo   node_modules 不存在，安装前端依赖...
    cd /d "%FRONTEND%"
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo   [ERROR] 前端依赖安装失败
        set "HAS_ERROR=1"
        goto :error_exit
    )
    echo   [OK] 前端依赖安装完成
) else (
    echo   [OK] 前端依赖已安装
)
echo.

:: ──────────────────────────────────────
:: 5. 检查 .env 配置
:: ──────────────────────────────────────
if not exist "%BACKEND%\.env" (
    echo [!] 警告：未找到 backend\.env 配置文件
    echo     请复制 backend\.env.example 并填写 API Key
    echo.
)

:: ──────────────────────────────────────
:: 6. 终止已有进程
:: ──────────────────────────────────────
echo [5/5] 启动服务...

:: 检查 8000 端口是否被占用
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   终止已有后端进程 PID %%p ...
    taskkill /F /PID %%p >nul 2>&1
)

:: 检查 5173 端口是否被占用
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173.*LISTENING" 2^>nul') do (
    echo   终止已有前端进程 PID %%p ...
    taskkill /F /PID %%p >nul 2>&1
)

timeout /t 1 /nobreak >nul

:: ──────────────────────────────────────
:: 7. 启动后端
:: ──────────────────────────────────────
echo.
echo   启动后端 (http://localhost:8000) ...
cd /d "%BACKEND%"
start "MyClaw-Backend" cmd /k "title MyClaw Backend && color 0A && "%PY%" -m uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

:: ──────────────────────────────────────
:: 8. 启动前端
:: ──────────────────────────────────────
echo   启动前端 (http://localhost:5173) ...
cd /d "%FRONTEND%"
start "MyClaw-Frontend" cmd /k "title MyClaw Frontend && color 0B && npm run dev"

timeout /t 3 /nobreak >nul

:: ──────────────────────────────────────
:: 完成
:: ──────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════╗
echo  ║          启动完成！                  ║
echo  ║                                      ║
echo  ║  前端: http://localhost:5173         ║
echo  ║  后端: http://localhost:8000         ║
echo  ║                                      ║
echo  ║  关闭方式：关闭两个弹出的终端窗口   ║
echo  ╚══════════════════════════════════════╝
echo.

:: 5秒后自动打开浏览器
echo 5 秒后自动打开浏览器...
timeout /t 5 /nobreak >nul
start http://localhost:5173

goto :eof

:error_exit
echo.
echo  [!] 启动失败，请检查上方错误信息
pause

@echo off
chcp 65001 >nul 2>&1
title MyClaw - 停止服务

echo.
echo  停止 MyClaw 服务...
echo.

set "FOUND=0"

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   终止后端进程 PID %%p
    taskkill /F /PID %%p >nul 2>&1
    set "FOUND=1"
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173.*LISTENING" 2^>nul') do (
    echo   终止前端进程 PID %%p
    taskkill /F /PID %%p >nul 2>&1
    set "FOUND=1"
)

if "%FOUND%"=="0" (
    echo   没有发现运行中的 MyClaw 服务
) else (
    echo.
    echo   [OK] 所有服务已停止
)

echo.
timeout /t 3 /nobreak >nul

@echo off
setlocal
title MyClaw - Stop Services

echo.
echo Stopping MyClaw services...
echo.

set "FOUND=0"

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 .*LISTENING" 2^>nul') do (
    echo   Killing backend PID %%p
    taskkill /F /PID %%p >nul 2>&1
    set "FOUND=1"
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 .*LISTENING" 2^>nul') do (
    echo   Killing frontend PID %%p
    taskkill /F /PID %%p >nul 2>&1
    set "FOUND=1"
)

if "%FOUND%"=="0" (
    echo   No MyClaw services found.
) else (
    echo.
    echo   [OK] Services stopped.
)

echo.
exit /b 0

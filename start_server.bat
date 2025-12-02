@echo off
title Reddit Intelligence Server
color 0A

echo ========================================
echo Reddit Intelligence Server Manager
echo ========================================
echo.

:menu
echo 1. Start Server (30 min interval)
echo 2. Start Server (1 hour interval)
echo 3. Start Server (Test Mode)
echo 4. Start Server (Daemon Mode)
echo 5. Stop Server
echo 6. View Server Status
echo 7. View Logs
echo 8. Exit
echo.
set /p choice="Choose option (1-8): "

if "%choice%"=="1" goto start30
if "%choice%"=="2" goto start60
if "%choice%"=="3" goto test
if "%choice%"=="4" goto daemon
if "%choice%"=="5" goto stop
if "%choice%"=="6" goto status
if "%choice%"=="7" goto logs
if "%choice%"=="8" goto exit
echo Invalid choice, try again.
goto menu

:start30
echo Starting server with 30-minute interval...
python server.py --interval 30
goto menu

:start60
echo Starting server with 60-minute interval...
python server.py --interval 60
goto menu

:test
echo Running test mode...
python server.py --test
pause
goto menu

:daemon
echo Starting daemon mode...
python server.py --daemon --interval 30
goto menu

:stop
echo Stopping any running Python processes...
taskkill /f /im python.exe 2>nul
echo Server stopped.
pause
goto menu

:status
echo Checking server status...
tasklist | findstr python
if exist server_stats.json (
    echo.
    echo Server Statistics:
    type server_stats.json
)
pause
goto menu

:logs
echo Viewing recent logs...
if exist automation.log (
    echo.
    echo Last 20 log entries:
    powershell "Get-Content automation.log -Tail 20"
) else (
    echo No log file found.
)
pause
goto menu

:exit
echo Goodbye!
exit
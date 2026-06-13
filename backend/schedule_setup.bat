@echo off
:: AIPulse — One-time Windows Task Scheduler setup
:: Run this ONCE as Administrator to register the daily 7am pipeline task.
::
:: Usage: Right-click → "Run as administrator"

setlocal

set TASK_NAME=AIPulseDailyPipeline
set BAT_FILE=%~dp0run_pipeline.bat
set RUN_TIME=07:00

echo ========================================================
echo  AIPulse — Scheduling daily pipeline at %RUN_TIME%
echo  Task name : %TASK_NAME%
echo  Script    : %BAT_FILE%
echo ========================================================
echo.

:: Delete existing task if it exists (clean re-register)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create the scheduled task
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%BAT_FILE%\"" ^
    /sc DAILY ^
    /st %RUN_TIME% ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Task "%TASK_NAME%" scheduled at %RUN_TIME% daily.
    echo.
    echo To verify:  schtasks /query /tn "%TASK_NAME%"
    echo To run now: schtasks /run /tn "%TASK_NAME%"
    echo To delete:  schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo ERROR: Task scheduling failed.
    echo Make sure you ran this script as Administrator.
)

echo.
pause
endlocal

@echo off
:: AIPulse Daily Pipeline Runner
:: Runs the full content pipeline and logs output with today's date.
::
:: To run manually: double-click this file or call it from Task Scheduler.

setlocal

:: ── Config ──────────────────────────────────────────────────────────────────
set BACKEND_DIR=%~dp0
set PYTHON=python

:: Try common venv locations
if exist "%BACKEND_DIR%venv\Scripts\python.exe"     set PYTHON=%BACKEND_DIR%venv\Scripts\python.exe
if exist "%BACKEND_DIR%.venv\Scripts\python.exe"    set PYTHON=%BACKEND_DIR%.venv\Scripts\python.exe
if exist "%BACKEND_DIR%env\Scripts\python.exe"      set PYTHON=%BACKEND_DIR%env\Scripts\python.exe

:: Log file with today's date
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set DT=%%i
set LOG_DATE=%DT:~0,8%
set LOG_FILE=%BACKEND_DIR%output\pipeline_%LOG_DATE%.txt

:: ── Run ──────────────────────────────────────────────────────────────────────
echo [%DATE% %TIME%] Starting AIPulse daily pipeline...
echo [%DATE% %TIME%] Python: %PYTHON%
echo [%DATE% %TIME%] Log: %LOG_FILE%

"%PYTHON%" "%BACKEND_DIR%src\pipeline.py" >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Pipeline completed successfully.
) else (
    echo [%DATE% %TIME%] Pipeline finished with errors. Check %LOG_FILE%
)

endlocal

@echo off
cd /d "%~dp0"
echo Removing lock file if present...
del /f /q ".git\index.lock" 2>nul
echo.
echo Staging all changes...
git add -A
echo.
echo Committing...
git commit -m "Add carousel generator: preview app, generate script, brand config, fix onclick bug"
echo.
echo Pulling remote changes (rebase)...
git pull --rebase origin main
echo.
echo Pushing to main...
git push origin main
echo.
echo Done! Press any key to close.
pause >nul

@echo off
cd /d "%~dp0"

echo Killing any background GitHub Desktop / git processes...
taskkill /f /im githubdesktop.exe 2>nul
taskkill /f /im git.exe 2>nul
timeout /t 2 /nobreak >nul

echo Removing lock files...
del /f /q ".git\index.lock" 2>nul
del /f /q ".git\MERGE_HEAD" 2>nul

echo Aborting any in-progress rebase...
git rebase --abort 2>nul

echo.
echo Staging all changes...
git add -A

echo.
echo Committing any remaining changes...
git commit -m "Carousel generator: all files staged" 2>nul || echo (nothing extra to commit)

echo.
echo Pulling remote (merge, not rebase)...
git pull --no-rebase --no-edit origin main

echo.
echo Pushing to main...
git push origin main

echo.
echo === Done! ===
git log --oneline -3
pause

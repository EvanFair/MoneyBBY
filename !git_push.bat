@echo off
cd /d "%~dp0"
echo.
echo === GoodNewsCast Git Push ===
echo.
git config user.email "evan.fair@gmail.com"
git config user.name "Evan"
git add .
git status
echo.
set /p MSG="Commit message: "
git commit -m "%MSG%"
git push origin main
echo.
echo Done!
pause

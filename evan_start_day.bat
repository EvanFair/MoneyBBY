@echo off
cd /d "%~dp0"
echo.
echo === Starting Your Work Day ===
echo.
echo Step 1: Getting the latest code from GitHub...
git config user.email "evan.fair@gmail.com"
git config user.name "Evan"
git checkout main
git pull origin main
echo.
echo Step 2: Switching to your personal branch...
git checkout evan-branch 2>nul || git checkout -b evan-branch
git merge main
echo.
echo You are ready to code! You are now on YOUR branch (evan-branch).
echo When you are done working, run evan_save_and_upload.bat
echo.
pause

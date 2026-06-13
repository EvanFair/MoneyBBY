@echo off
cd /d "%~dp0"
echo.
echo === Starting Your Work Day ===
echo.
echo Step 1: Getting the latest code from GitHub...
git config user.email "BUDDY_EMAIL_HERE@gmail.com"
git config user.name "BUDDY_NAME_HERE"
git checkout main
git pull origin main
echo.
echo Step 2: Switching to your personal branch...
git checkout JobsonBranch 2>nul || git checkout -b JobsonBranch
git merge main
echo.
echo You are ready to code! You are now on YOUR branch (JobsonBranch).
echo When you are done working, run buddy_save_and_upload.bat
echo.
pause

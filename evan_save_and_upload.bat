@echo off
cd /d "%~dp0"
echo.
echo === Saving and Uploading Your Work ===
echo.
git config user.email "evan.fair@gmail.com"
git config user.name "Evan"
echo.
echo What did you work on today?
set /p MSG="Describe your changes: "
echo.
echo Saving your work...
git add .
git commit -m "%MSG%"
echo.
echo Uploading to GitHub...
git push origin evan-branch
echo.
echo =====================================================
echo  YOUR WORK IS SAVED! Now tell your buddy to run
echo  his merge_to_main.bat when you are both ready
echo  to combine your work into the main version.
echo =====================================================
echo.
pause

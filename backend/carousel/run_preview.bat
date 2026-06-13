@echo off
title Carousel Preview App
echo.
echo  Checking dependencies...
python -m pip install flask python-pptx requests python-dotenv lxml --quiet 2>nul
echo  Starting Carousel Preview...
echo.
python "%~dp0preview_app.py"
if errorlevel 1 (
    echo.
    echo  Something went wrong. Press any key to see the error above.
    pause >nul
)

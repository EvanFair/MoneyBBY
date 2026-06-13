Set-Location $PSScriptRoot

Write-Host "Killing git processes..." -ForegroundColor Yellow
Get-Process git -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Write-Host "Removing lock file..." -ForegroundColor Yellow
Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue

Write-Host "Restoring carousel files from commit 1c9da3a..." -ForegroundColor Yellow
git checkout 1c9da3a -- backend/carousel/brand_config.json
git checkout 1c9da3a -- backend/carousel/carousel_template.pptx
git checkout 1c9da3a -- backend/carousel/generate_carousel.py
git checkout 1c9da3a -- backend/carousel/preview_app.py
git checkout 1c9da3a -- backend/carousel/run_preview.bat

Write-Host "Staging carousel files..." -ForegroundColor Yellow
git add backend/carousel/

Write-Host "Committing..." -ForegroundColor Yellow
git commit -m "Restore carousel generator files (generate_carousel.py, preview_app.py, brand_config, template)"

Write-Host "Pushing to main..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Result ===" -ForegroundColor Green
git log --oneline -4
git ls-tree --name-only HEAD backend/carousel/
Write-Host ""
Read-Host "Press Enter to close"

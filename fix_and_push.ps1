Set-Location $PSScriptRoot

Write-Host "Killing git/cmd processes..." -ForegroundColor Yellow
Get-Process git -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process git-remote-https -ErrorAction SilentlyContinue | Stop-Process -Force

Start-Sleep -Seconds 1

Write-Host "Removing lock files..." -ForegroundColor Yellow
Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue
Remove-Item ".git\rebase-merge\*" -Force -ErrorAction SilentlyContinue
Remove-Item ".git\rebase-merge" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item ".git\MERGE_HEAD" -Force -ErrorAction SilentlyContinue
Remove-Item ".git\AUTO_MERGE" -Force -ErrorAction SilentlyContinue

Write-Host "Resetting index..." -ForegroundColor Yellow
git reset HEAD

Write-Host "Staging all files..." -ForegroundColor Yellow
git add -A

Write-Host "Committing..." -ForegroundColor Yellow
git commit -m "Carousel generator: preview app + onclick fix" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "(nothing new to commit)" -ForegroundColor Gray }

Write-Host "Force pushing to main..." -ForegroundColor Yellow
git push --force-with-lease origin main

Write-Host ""
Write-Host "=== Result ===" -ForegroundColor Green
git log --oneline -4
Write-Host ""
Read-Host "Press Enter to close"

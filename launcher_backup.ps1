# Soul Swarm Launcher - PowerShell Version
# Save this as launcher.ps1

function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host "              SOUL SWARM ULTIMATE CONTROL                     " -ForegroundColor Magenta
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  CONTINUOUS MODES" -ForegroundColor Yellow
    Write-Host "  [1] Normal Mode    - Posts every 1-2 hours"
    Write-Host "  [2] Stealth Mode   - Posts every 30-60 minutes"
    Write-Host "  [3] Burst Mode     - Posts every 10-20 minutes"
    Write-Host "  [4] Master Mode    - Stealth + ALL optimizations"
    Write-Host ""
    Write-Host "  ATTACK MODES" -ForegroundColor Red
    Write-Host "  [5] Basic Convergence  - Quick swarm"
    Write-Host "  [6] Advanced Swarm     - Full control"
    Write-Host "  [7] Bot Hunter         - Vigilante service"
    Write-Host ""
    Write-Host "  UTILITIES" -ForegroundColor Cyan
    Write-Host "  [8] Test Mode      - Single post per soul"
    Write-Host "  [9] Interactive    - Manual commands"
    Write-Host "  [A] Admin API      - Token management"
    Write-Host "  [0] Exit"
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Start-BasicConvergence {
    Clear-Host
    Write-Host ""
    Write-Host "  BASIC CONVERGENCE MODE" -ForegroundColor Red
    Write-Host "  -----------------------" -ForegroundColor DarkGray
    Write-Host ""
    
    $target = Read-Host "  Enter target handle (without @)"
    
    if (-not $target) {
        Write-Host "  No target specified!" -ForegroundColor Red
        Read-Host "  Press Enter to continue"
        return
    }
    
    Write-Host ""
    Write-Host "  Target: @$target" -ForegroundColor Yellow
    Write-Host "  Duration: ~30 minutes" -ForegroundColor Yellow
    Write-Host ""
    
    $confirm = Read-Host "  Start attack? (Y/N)"
    
    if ($confirm -eq 'Y' -or $confirm -eq 'y') {
        python launch.py --converge $target
    }
}

function Start-AdvancedConvergence {
    Clear-Host
    Write-Host ""
    Write-Host "  ADVANCED CONVERGENCE CONTROL" -ForegroundColor Magenta
    Write-Host "  -----------------------------" -ForegroundColor DarkGray
    Write-Host ""
    
    $target = Read-Host "  Enter target handle"
    if (-not $target) { return }
    
    Write-Host ""
    Write-Host "  Select Mood:" -ForegroundColor Yellow
    Write-Host "  [1] AGGRESSIVE"
    Write-Host "  [2] SUPPORTIVE"
    Write-Host "  [3] CHAOTIC"
    $mood = Read-Host "  Choice"
    
    $totalPosts = Read-Host "  Total posts [30]"
    if (-not $totalPosts) { $totalPosts = "30" }
    
    Write-Host ""
    Write-Host "  Launching advanced convergence..." -ForegroundColor Green
    
    # Save params to file and use that
    $params = @{
        target = $target
        mood = $mood
        posts = $totalPosts
    }
    $params | ConvertTo-Json | Out-File "temp_params.json"
    
    # Call Python with simple command
    python -c "print('Advanced convergence would run here with params from temp_params.json')"
}

# Main Loop
while ($true) {
    Show-Menu
    $choice = Read-Host "  Select Option"
    
    switch ($choice) {
        '1' { 
            Write-Host "  Starting Normal Mode..." -ForegroundColor Green
            python launch.py --normal
        }
        '2' { 
            Write-Host "  Starting Stealth Mode..." -ForegroundColor Yellow
            python launch.py --stealth
        }
        '3' { 
            Write-Host "  Starting Burst Mode..." -ForegroundColor Red
            python launch.py --burst
        }
        '4' {
            if (Test-Path "swarm_master.py") {
                python swarm_master.py
            } else {
                python launch.py --stealth --optimize
            }
        }
        '5' { Start-BasicConvergence }
        '6' { Start-AdvancedConvergence }
        '7' {
            Write-Host "  Starting Bot Hunter..." -ForegroundColor Cyan
            Set-Location vigilante
            python military_bot_hunter.py
            Set-Location ..
        }
        '8' { python launch.py --test }
        '9' { python launch.py --interactive }
        'A' { 
            Start-Process powershell -ArgumentList "python admin_api_secure.py"
            Write-Host "  Admin API started" -ForegroundColor Green
        }
        'a' { 
            Start-Process powershell -ArgumentList "python admin_api_secure.py"
            Write-Host "  Admin API started" -ForegroundColor Green
        }
        '0' { exit }
        default {
            Write-Host "  Invalid choice!" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
    
    Write-Host ""
    Read-Host "  Press Enter to continue"
}
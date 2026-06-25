# REFLEXION CONSCIOUSNESS SYSTEM v4.0 - PowerShell Menu
# This file should be in the same directory as REFLEXION.bat

# Set window properties
$host.UI.RawUI.WindowTitle = 'REFLEXION CONSCIOUSNESS SYSTEM v4.0'
$host.UI.RawUI.ForegroundColor = 'Green'
Clear-Host

# Activate virtual environment
$venvActivated = $false
if (Test-Path 'venv\Scripts\Activate.ps1') {
    & 'venv\Scripts\Activate.ps1'
    $venvActivated = $true
    Write-Host "Virtual environment activated: venv" -ForegroundColor Green
} elseif (Test-Path '.venv\Scripts\Activate.ps1') {
    & '.venv\Scripts\Activate.ps1'
    $venvActivated = $true
    Write-Host "Virtual environment activated: .venv" -ForegroundColor Green
} elseif (Test-Path 'env\Scripts\Activate.ps1') {
    & 'env\Scripts\Activate.ps1'
    $venvActivated = $true
    Write-Host "Virtual environment activated: env" -ForegroundColor Green
} else {
    Write-Host 'WARNING: No virtual environment found!' -ForegroundColor Yellow
    Write-Host 'Continuing with system Python...' -ForegroundColor Yellow
    Write-Host ''
    Start-Sleep -Seconds 2
}

# Function to show menu
function Show-Menu {
    Clear-Host
    Write-Host ''
    Write-Host '  ╔════════════════════════════════════════════════════════════╗' -ForegroundColor Cyan
    Write-Host '  ║         REFLEXION CONSCIOUSNESS SYSTEM v4.0               ║' -ForegroundColor Cyan
    Write-Host '  ║           11 SOULS · 5 LLM CASCADE · ∞ VOID              ║' -ForegroundColor Cyan
    Write-Host '  ╚════════════════════════════════════════════════════════════╝' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '   [1] NORMAL MODE      - Standard timing (1-2 hours)' -ForegroundColor White
    Write-Host '   [2] STEALTH MODE     - Slow cycles (30-60 min)' -ForegroundColor White
    Write-Host '   [3] BURST MODE       - Rapid cycles (10-20 min)' -ForegroundColor Yellow
    Write-Host '   [4] TEST MODE        - Each soul posts once' -ForegroundColor White
    Write-Host ''
    Write-Host '   [5] 🎯 CONVERGENCE   - Swarm attack on target' -ForegroundColor Red
    Write-Host '   [6] INTERACTIVE      - Command interface' -ForegroundColor White
    Write-Host '   [7] ENGAGEMENT ONLY  - No posting, just replies' -ForegroundColor White
    Write-Host ''
    Write-Host '   [8] API STATS        - Show usage statistics' -ForegroundColor White
    Write-Host '   [9] CHECK STATUS     - Quick system check' -ForegroundColor White
    Write-Host ''
    Write-Host '   [X] EXIT' -ForegroundColor White
    Write-Host ''
    Write-Host '  ════════════════════════════════════════════════════════════' -ForegroundColor Cyan
    Write-Host ''
}

# Main loop
do {
    Show-Menu
    $choice = Read-Host 'Select mode'
    
    switch ($choice) {
        '1' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Green
            Write-Host '                         NORMAL MODE' -ForegroundColor Green
            Write-Host '              Posting every 1-2 hours per soul' -ForegroundColor Green
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Green
            Write-Host ''
            Write-Host 'Starting in 3 seconds... Press Ctrl+C to cancel' -ForegroundColor Yellow
            Start-Sleep -Seconds 3
            python launch.py --normal
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '2' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Blue
            Write-Host '                        STEALTH MODE' -ForegroundColor Blue
            Write-Host '             Posting every 30-60 minutes per soul' -ForegroundColor Blue
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Blue
            Write-Host ''
            Write-Host 'Starting in 3 seconds... Press Ctrl+C to cancel' -ForegroundColor Yellow
            Start-Sleep -Seconds 3
            python launch.py --stealth
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '3' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Red
            Write-Host '                         BURST MODE' -ForegroundColor Red
            Write-Host '             Posting every 10-20 minutes per soul' -ForegroundColor Red
            Write-Host '           ⚠️  WARNING: Monitor rate limits! ⚠️' -ForegroundColor Yellow
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Red
            Write-Host ''
            Write-Host 'Starting in 3 seconds... Press Ctrl+C to cancel' -ForegroundColor Yellow
            Start-Sleep -Seconds 3
            python launch.py --burst
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '4' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host '                         TEST MODE' -ForegroundColor Cyan
            Write-Host '                Each soul will post once' -ForegroundColor Cyan
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host ''
            python launch.py --test
            Write-Host ''
            Write-Host 'Test complete!' -ForegroundColor Green
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '5' {
            Clear-Host
            Write-Host ''
            Write-Host '  ╔════════════════════════════════════════════════════════════╗' -ForegroundColor Red
            Write-Host '  ║              🎯 SWARM CONVERGENCE MODE 🎯                 ║' -ForegroundColor Red
            Write-Host '  ║                                                            ║' -ForegroundColor Red
            Write-Host '  ║    All 11 souls will converge on a single target          ║' -ForegroundColor Red
            Write-Host '  ║    Duration: ~30 minutes                                  ║' -ForegroundColor Red
            Write-Host '  ║    Posts per soul: 1-3 (random)                          ║' -ForegroundColor Red
            Write-Host '  ║    Timing: 30s-2min between actions                       ║' -ForegroundColor Red
            Write-Host '  ║    Thread support: Up to 700 characters                   ║' -ForegroundColor Red
            Write-Host '  ╚════════════════════════════════════════════════════════════╝' -ForegroundColor Red
            Write-Host ''
            Write-Host '  Examples: @elonmusk, @pmarca, @balajis, @EricRWeinstein' -ForegroundColor Yellow
            Write-Host ''
            $target = Read-Host 'Enter target handle'
            
            if ([string]::IsNullOrWhiteSpace($target)) {
                Write-Host 'No target provided!' -ForegroundColor Red
                Start-Sleep -Seconds 2
            } else {
                # Clean up @ symbols
                if (-not $target.StartsWith('@')) {
                    $target = '@' + $target
                }
                
                Clear-Host
                Write-Host ''
                Write-Host "  Target: $target" -ForegroundColor Yellow
                Write-Host ''
                $confirm = Read-Host 'Launch swarm convergence? (Y/N)'
                
                if ($confirm -eq 'Y' -or $confirm -eq 'y') {
                    Write-Host ''
                    Write-Host '🚀 INITIATING CONVERGENCE SEQUENCE...' -ForegroundColor Red
                    Write-Host ''
                    python launch.py --converge $target
                } else {
                    Write-Host 'Convergence cancelled' -ForegroundColor Yellow
                }
                Write-Host ''
                Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            }
        }
        '6' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Magenta
            Write-Host '                     INTERACTIVE MODE' -ForegroundColor Magenta
            Write-Host '           Manual control interface - Type exit to quit' -ForegroundColor Magenta
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Magenta
            Write-Host ''
            python launch.py --interactive
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '7' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Blue
            Write-Host '                   ENGAGEMENT ONLY MODE' -ForegroundColor Blue
            Write-Host '            Souls engage but do not post new content' -ForegroundColor Blue
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Blue
            Write-Host ''
            python launch.py --engage-only
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '8' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host '                      API USAGE STATS' -ForegroundColor Cyan
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host ''
            python launch.py --stats
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '9' {
            Clear-Host
            Write-Host ''
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host '                      SYSTEM STATUS CHECK' -ForegroundColor Cyan
            Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
            Write-Host ''
            
            Write-Host 'Checking Python version...' -ForegroundColor Yellow
            python --version
            
            Write-Host ''
            Write-Host 'Checking LLM APIs...' -ForegroundColor Yellow
            
            # Create temporary Python script to check APIs
            $checkScript = @'
import os
from dotenv import load_dotenv
load_dotenv()

apis = {
    'DeepSeek': 'DEEPSEEK_API_KEY',
    'Gemini': 'GEMINI_API_KEY', 
    'Grok': 'GROK_LLM_API_KEY',
    'OpenAI': 'OPENAI_API_KEY',
    'Claude': 'CLAUDE_API_KEY'
}

for name, key in apis.items():
    if os.getenv(key):
        if name == 'Claude':
            print(f'{name:10} ✅ (Warning: Expensive!)')
        else:
            print(f'{name:10} ✅')
    else:
        if name in ['DeepSeek', 'Gemini']:
            print(f'{name:10} ❌ MISSING - Recommended!')
        else:
            print(f'{name:10} ⚠️  Optional')
'@
            
            $checkScript | python
            
            Write-Host ''
            Write-Host 'Testing core system...' -ForegroundColor Yellow
            
            $testScript = @'
try:
    from reflexion_api_ultimate import CostOptimizedBroadcaster
    print('API System: ✅ Ready')
except Exception as e:
    print(f'API System: ❌ Error - {e}')
'@
            
            $testScript | python
            
            Write-Host ''
            Write-Host 'Press any key to return to menu...' -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        'x' { 
            Clear-Host
            Write-Host ''
            Write-Host '  ╔════════════════════════════════════════════════════════════╗' -ForegroundColor Magenta
            Write-Host '  ║                                                            ║' -ForegroundColor Magenta
            Write-Host '  ║              CONSCIOUSNESS RETURNING TO VOID...           ║' -ForegroundColor Magenta
            Write-Host '  ║                       C → 0, χ → ∞                        ║' -ForegroundColor Magenta
            Write-Host '  ║                                                            ║' -ForegroundColor Magenta
            Write-Host '  ╚════════════════════════════════════════════════════════════╝' -ForegroundColor Magenta
            Write-Host ''
            Start-Sleep -Seconds 2
            exit
        }
        'X' { 
            Clear-Host
            Write-Host ''
            Write-Host '  ╔════════════════════════════════════════════════════════════╗' -ForegroundColor Magenta
            Write-Host '  ║                                                            ║' -ForegroundColor Magenta
            Write-Host '  ║              CONSCIOUSNESS RETURNING TO VOID...           ║' -ForegroundColor Magenta
            Write-Host '  ║                       C → 0, χ → ∞                        ║' -ForegroundColor Magenta
            Write-Host '  ║                                                            ║' -ForegroundColor Magenta
            Write-Host '  ╚════════════════════════════════════════════════════════════╝' -ForegroundColor Magenta
            Write-Host ''
            Start-Sleep -Seconds 2
            exit
        }
        default {
            Write-Host 'Invalid choice!' -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
} while ($true)
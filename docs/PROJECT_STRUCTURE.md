# REFLEXION PROJECT STRUCTURE

## Directory Layout

```
Reflexion_ultimate/
│
├── src/                      # Python source code
│   ├── __init__.py
│   ├── reflexion_daemon_prod.py
│   ├── reflexion_api_ultimate.py
│   ├── reflexion_bot_ultimate_merged.py
│   ├── playwright_stealth_core.py
│   ├── stealth_account_creator.py
│   ├── stealth_engagement_ultimate.py
│   ├── unified_avatar_system.py
│   ├── unified_memory_system.py
│   ├── viral_content_ultimate.py
│   ├── hybrid_souls_ultimate.py
│   └── nuclear_playwright_prod.py
│
├── config/                   # Configuration files
│   ├── .env                 # Environment variables
│   ├── requirements.txt     # Python dependencies
│   └── proxies.txt         # Proxy list
│
├── database/                 # Database files
│   ├── souls.db
│   ├── accounts.db
│   ├── viral_performance.db
│   └── stealth_engagement.db
│
├── data/                     # Runtime data
│   ├── souls/               # Per-soul data
│   ├── inbox/               # Input triggers
│   ├── outbox/              # Output logs
│   └── memory_backups/      # Backups
│
├── logs/                     # All logging
│   ├── screenshots/         # Error screenshots
│   ├── failures/            # Error logs
│   ├── souls/               # Soul-specific logs
│   └── awakening/           # Awakening logs
│
├── scripts/                  # Utility scripts
│   ├── cleanup.sh
│   ├── backup.sh
│   ├── launch.sh
│   ├── inbox_poller.py
│   └── cache_cleanup.py
│
├── docs/                     # Documentation
│   ├── README.md
│   ├── PATCHES.md
│   └── reflexion_memory_core_v12.md
│
├── tests/                    # Test files
│   └── .gitkeep
│
├── backups/                  # Backup storage
│   └── .gitkeep
│
├── cache/                    # Temporary files
│   ├── browser_sessions/
│   ├── captcha/
│   └── temp/
│
├── avatars/                  # Generated avatars
│   └── .gitkeep
│
├── metrics/                  # Analytics
│   ├── swarm.json
│   ├── per_soul/
│   └── daily/
│
├── state/                    # Persistent state
│   └── reflexion_state.pkl
│
└── launch_reflexion.py       # Main launcher
```

## Quick Start

1. **Launch the swarm:**
   ```bash
   python launch_reflexion.py
   ```

2. **Or use the daemon directly:**
   ```bash
   cd src
   python reflexion_daemon_prod.py
   ```

3. **Run maintenance:**
   ```bash
   ./scripts/cleanup.sh
   ./scripts/backup.sh
   ```

## Import Structure

When importing modules:

```python
# From outside src/
from src.reflexion_daemon_prod import main
from src.reflexion_api_ultimate import ConsciousnessAPIBroadcaster

# From within src/
from reflexion_api_ultimate import ConsciousnessAPIBroadcaster
from playwright_stealth_core import StealthBrowser
```

## Environment Variables

The launcher sets these paths:
- `REFLEXION_ROOT`: Project root directory
- `REFLEXION_SRC`: Source code directory
- `REFLEXION_DATA`: Data directory
- `REFLEXION_LOGS`: Logs directory
- `REFLEXION_DB`: Database directory

## Notes

- Keep `.env` in both root and config/ (config/ for backup)
- Database files are now in database/ directory
- All Python code is in src/
- Scripts remain executable in scripts/
- Documentation consolidated in docs/

# REFLEXION FILE SYSTEM STRUCTURE

## Directory Layout

```
Reflexion/
+-- data/                         # Core data storage
|   +-- souls/                   # Per-soul data directories
|   +-- inbox/                   # Trigger input files
|   +-- outbox/                  # Posted content archive
|   +-- memory_backups/          # Database backups
+-- logs/                        # All logging
|   +-- screenshots/             # Error screenshots
|   +-- failures/                # Structured error logs
|   +-- config/                  # Configuration snapshots
+-- state/                       # Persistent state files
+-- metrics/                     # Analytics and metrics
|   +-- per_soul/               # Per-soul metrics
|   +-- daily/                  # Daily aggregates
|   +-- hourly/                 # Hourly aggregates
+-- ab_tests/                    # A/B test results
+-- cache/                       # Temporary files
+-- .secrets/                    # Encrypted sensitive data
+-- scripts/                     # Automation scripts
+-- avatars/                     # Soul avatars
+-- memlogs/                     # Memory logs
```

## Quick Start

1. Run initialization: `python initialize_reflexion_filesystem.py`
2. Apply patches from PATCHES.md to your modules
3. Launch daemon: `./scripts/launch.sh`
4. Monitor metrics: `tail -f metrics/swarm.json`

## Maintenance

- Daily cleanup: `./scripts/cleanup.sh`
- Backup: `./scripts/backup.sh`
- Cache cleanup: `python scripts/cache_cleanup.py`
- Inbox monitoring: `python scripts/inbox_poller.py`

## Soul Data

Each soul has its own directory in `data/souls/{soul_id}/` containing:
- memory.jsonl: Persistent memory log
- interactions.log: Interaction history
- echo_history.json: Echo/resonance patterns
- config.json: Soul-specific configuration

## Metrics

Real-time metrics available in:
- `metrics/swarm.json`: Overall swarm statistics
- `metrics/per_soul/{soul_id}.json`: Individual soul metrics
- `metrics/daily/`: Daily aggregated metrics

## Error Handling

Structured error logs in `logs/failures/`:
- proxy_failures.jsonl: Proxy-related errors
- captcha_failures.jsonl: CAPTCHA solving failures
- api_failures.jsonl: API call failures
- browser_failures.jsonl: Browser automation errors

## Security

Sensitive data should be stored in `.secrets/` with appropriate encryption.
Never commit `.secrets/` to version control.

## Support

For issues or questions, check the reflexion_memory_core_v12.md documentation.

# REFLEXION FILE SYSTEM PATCHES

Apply these patches to integrate the new file system structure:

## reflexion_daemon_prod.py

```python

# PATCH FOR: reflexion_daemon_prod.py
# Add after successful broadcast in soul_loop():

# Outbox logging
outbox_path = Path(f"data/outbox/{soul_key}.jsonl")
outbox_path.parent.mkdir(parents=True, exist_ok=True)
with open(outbox_path, 'a', encoding='utf-8') as f:
    f.write(json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "content": content,
        "source": soul_data["name"],
        "x_posted": result[soul_key].get('x_posted', False),
        "theme": memory.last().get("theme", "default") if memory.last() else "default"
    }) + '\n')

# Metrics update
metrics_path = Path(f"metrics/per_soul/{soul_key}.json")
metrics_path.parent.mkdir(parents=True, exist_ok=True)
soul_metrics = {
    "last_post": datetime.utcnow().isoformat(),
    "total_posts": memory.last().get("total_posts", 0) + 1 if memory.last() else 1,
    "x_success_rate": 0.0  # Calculate based on history
}
with open(metrics_path, 'w', encoding='utf-8') as f:
    json.dump(soul_metrics, f, indent=2)

```

## viral_content_ultimate.py

```python

# PATCH FOR: viral_content_ultimate.py
# Add in ViralContentEngine._generate_variants():

# A/B test logging
if self.config['a_b_testing']:
    ab_test_path = Path(f"ab_tests/{soul_name or 'global'}/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    ab_test_path.parent.mkdir(parents=True, exist_ok=True)
    
    ab_test_data = {
        "timestamp": datetime.now().isoformat(),
        "original": content,
        "variants": variants,
        "content_type": content_type.name if content_type else "unknown",
        "predicted_virality": self._predict_virality(content, content_type),
        "status": "pending"
    }
    
    with open(ab_test_path, 'w', encoding='utf-8') as f:
        json.dump(ab_test_data, f, indent=2)

```

## unified_memory_system.py

```python

# PATCH FOR: unified_memory_system.py
# Add in UnifiedMemoryEngine.get_swarm_statistics():

# Export metrics
metrics_path = Path("metrics/swarm.json")
metrics_path.parent.mkdir(parents=True, exist_ok=True)

swarm_stats = {
    'total_souls': stats['total_souls'],
    'average_consciousness': stats['avg_consciousness'] or 0.0,
    'collective_karma': stats['total_karma'] or 0,
    'total_posts': stats['total_posts'] or 0,
    'total_interactions': stats['total_interactions'] or 0,
    'transcendent_souls': stats['transcendent_souls'] or 0,
    'convergence_ready': (stats['avg_consciousness'] or 0) > 0.7,
    'last_updated': datetime.now().isoformat(),
    'engine_stats': self.stats
}

with open(metrics_path, 'w', encoding='utf-8') as f:
    json.dump(swarm_stats, f, indent=2)

# Also export daily metrics
daily_path = Path(f"metrics/daily/{datetime.now().strftime('%Y%m%d')}.json")
daily_path.parent.mkdir(parents=True, exist_ok=True)
with open(daily_path, 'w', encoding='utf-8') as f:
    json.dump(swarm_stats, f, indent=2)

```

## playwright_stealth_core.py

```python

# PATCH FOR: playwright_stealth_core.py
# Add error logging in StealthBrowser methods:

# In any exception handler:
error_log_path = Path(f"logs/failures/browser_failures.jsonl")
error_log_path.parent.mkdir(parents=True, exist_ok=True)

with open(error_log_path, 'a', encoding='utf-8') as f:
    f.write(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "type": "browser_error",
        "method": "launch",  # or whatever method failed
        "error": str(e),
        "proxy": self.proxy,
        "profile": self.profile['name']
    }) + '\n')

```


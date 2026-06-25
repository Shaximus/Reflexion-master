#!/usr/bin/env python3
"""
Cache Cleanup Service for Reflexion
Automatically purges old cache files
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheCleanup:
    def __init__(self, cache_path: str = "cache", max_age_hours: int = 24):
        self.cache_path = Path(cache_path)
        self.max_age = timedelta(hours=max_age_hours)
        
    def cleanup(self):
        """Remove old cache files"""
        now = datetime.now()
        removed = 0
        
        for cache_file in self.cache_path.rglob("*"):
            if cache_file.is_file():
                age = now - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if age > self.max_age:
                    cache_file.unlink()
                    removed += 1
                    
        if removed > 0:
            logger.info(f"Removed {removed} old cache files")
            
    def run(self, interval: int = 3600):
        """Run cleanup loop"""
        logger.info("Starting cache cleanup service...")
        while True:
            self.cleanup()
            time.sleep(interval)

if __name__ == "__main__":
    cleanup = CacheCleanup()
    cleanup.run()

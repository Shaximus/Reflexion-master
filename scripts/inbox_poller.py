#!/usr/bin/env python3
"""
Inbox Polling Service for Reflexion
Monitors data/inbox/ for trigger files and processes them
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InboxPoller:
    def __init__(self, inbox_path: str = "data/inbox"):
        self.inbox_path = Path(inbox_path)
        self.processed = set()
        
    def poll(self):
        """Check for new trigger files"""
        for trigger_file in self.inbox_path.glob("*.json"):
            if trigger_file.name not in self.processed:
                self.process_trigger(trigger_file)
                self.processed.add(trigger_file.name)
                
    def process_trigger(self, trigger_file: Path):
        """Process a trigger file"""
        try:
            with open(trigger_file, 'r') as f:
                trigger = json.load(f)
                
            logger.info(f"Processing trigger: {trigger_file.name}")
            logger.info(f"  Type: {trigger.get('type')}")
            logger.info(f"  Target: {trigger.get('target_soul')}")
            logger.info(f"  Content: {trigger.get('content')[:50]}...")
            
            # Move to processed
            processed_path = self.inbox_path / "processed" / trigger_file.name
            processed_path.parent.mkdir(exist_ok=True)
            trigger_file.rename(processed_path)
            
        except Exception as e:
            logger.error(f"Failed to process {trigger_file}: {e}")
            
    def run(self, interval: int = 10):
        """Run polling loop"""
        logger.info("Starting inbox polling service...")
        while True:
            self.poll()
            time.sleep(interval)

if __name__ == "__main__":
    poller = InboxPoller()
    poller.run()

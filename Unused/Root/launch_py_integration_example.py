#!/usr/bin/env python3
"""
LAUNCH.PY TRANSPORT INTEGRATION PATTERN
Apply these exact changes to your existing launch.py file.
"""

# ============================================================================
# AT THE VERY TOP OF launch.py (before ANY imports that use APIs)
# ============================================================================

from dotenv import load_dotenv
load_dotenv()  # MUST be first line to ensure env vars are loaded

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# NEW: Import transport instead of ryan_api
from twitter_transport import TransportFactory, TransportWatcher

# ... (rest of your existing imports)

# ============================================================================
# ADD THIS PROOF PACK HELPER FUNCTION
# ============================================================================

def log_to_proof_pack(soul: str, action: str, url: str, content: str = None):
    """Log successful posts/replies to Proof Pack"""
    proof_file = Path("engagement/proof_pack.json")
    proof_file.parent.mkdir(exist_ok=True)
    
    # Load existing proof pack
    proofs = []
    if proof_file.exists():
        try:
            with open(proof_file, 'r') as f:
                proofs = json.load(f)
        except:
            proofs = []
    
    # Add new entry
    entry = {
        "soul": soul,
        "action": action,
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "content_preview": content[:100] if content else None
    }
    proofs.append(entry)
    
    # Keep only last 1000 entries
    proofs = proofs[-1000:]
    
    # Save atomically
    tmp = proof_file.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(proofs, f, indent=2)
    tmp.replace(proof_file)
    
    print(f"📸 Proof logged: {soul} - {url}")

# ============================================================================
# UPDATE YOUR MAIN CLASS/FUNCTION
# ============================================================================

class YourOrchestrator:  # Or whatever your main class is called
    def __init__(self):
        # OLD: self.ryan_api = RyanTwitterAPISecure()
        # NEW:
        self.transport = TransportFactory.create_from_env()
        self.transport_watcher = TransportWatcher(self.transport)
        self.watcher_task = None
        
        # ... rest of your existing __init__ ...
    
    async def start(self):
        """Start the orchestrator with hot-reload watcher"""
        # Start the transport watcher for hot-reload
        self.watcher_task = asyncio.create_task(self.transport_watcher.start())
        
        try:
            await self.main_loop()
        finally:
            # Clean shutdown
            self.transport_watcher.stop()
            if self.watcher_task:
                await self.watcher_task
    
    async def main_loop(self):
        """Your main orchestration loop"""
        while True:
            # CRITICAL: Refresh tokens at start of EACH iteration
            await self.transport.refresh_tokens_from_disk()
            
            # Get available souls (not banned, have tokens)
            available_souls = self.transport.get_available_souls()
            print(f"🔄 Loop iteration - {len(available_souls)} souls available")
            
            for soul in available_souls:
                try:
                    # Generate content (your existing logic)
                    content = await self.generate_content(soul)  # Your method
                    
                    # Post via transport (normalized response)
                    result = await self.transport.post_tweet(soul, content)
                    
                    # Handle normalized response format
                    if result["success"]:
                        # Extract URL from normalized response
                        if result.get("tweet") and result["tweet"].get("url"):
                            log_to_proof_pack(
                                soul=soul,
                                action="post",
                                url=result["tweet"]["url"],
                                content=content
                            )
                            print(f"✅ {soul} posted: {result['tweet']['url']}")
                        else:
                            print(f"✅ {soul} posted (no URL returned)")
                    
                    elif result.get("skip"):
                        # Soul is banned or rate limited - skip this iteration
                        print(f"⏭️ Skipping {soul}: {result.get('error')}")
                        continue
                    
                    else:
                        # Temporary error - log but continue
                        print(f"❌ {soul} failed: {result.get('error')}")
                        
                except Exception as e:
                    print(f"Error with {soul}: {e}")
                    continue
            
            # Wait before next cycle
            await asyncio.sleep(300)  # 5 minutes or your preferred interval

# ============================================================================
# EXAMPLE: Reply to mentions (shows reply pattern)
# ============================================================================

async def process_mentions(transport, soul: str):
    """Example of processing mentions with transport"""
    # Fetch mentions
    mentions_result = await transport.fetch_mentions(soul, limit=10)
    
    if not mentions_result["success"]:
        print(f"Failed to fetch mentions: {mentions_result.get('error')}")
        return
    
    for mention in mentions_result.get("mentions", []):
        tweet_id = mention.get("id")
        tweet_text = mention.get("text", "")
        
        # Generate reply (your logic)
        reply_content = f"Thanks for the mention! 🚀"  # Your generation logic
        
        # Reply via transport
        result = await transport.reply_tweet(soul, tweet_id, reply_content)
        
        if result["success"] and result.get("tweet"):
            log_to_proof_pack(
                soul=soul,
                action="reply",
                url=result["tweet"]["url"],
                content=reply_content
            )
            print(f"↩️ Replied: {result['tweet']['url']}")

# ============================================================================
# INTERACTIVE MODE EXAMPLE (if you have one)
# ============================================================================

async def run_interactive():
    """Interactive command mode using transport"""
    # Create transport
    transport = TransportFactory.create_from_env()
    
    # Start watcher for hot-reload
    watcher = TransportWatcher(transport)
    watcher_task = asyncio.create_task(watcher.start())
    
    try:
        print("\n🎮 Interactive Mode")
        print("Commands: post <soul> <text>, souls, refresh, quit")
        
        while True:
            try:
                command = input("\n> ").strip()
                
                if command == "quit":
                    break
                
                elif command == "souls":
                    souls = transport.get_available_souls()
                    print(f"Available: {', '.join(souls)}")
                
                elif command == "refresh":
                    await transport.refresh_tokens_from_disk()
                    print("✅ Tokens refreshed")
                
                elif command.startswith("post "):
                    parts = command.split(" ", 2)
                    if len(parts) >= 3:
                        soul, text = parts[1], parts[2]
                        result = await transport.post_tweet(soul, text)
                        
                        if result["success"] and result.get("tweet"):
                            print(f"✅ Posted: {result['tweet']['url']}")
                            log_to_proof_pack(soul, "post", result['tweet']['url'], text)
                        else:
                            print(f"❌ Failed: {result.get('error')}")
                            
            except KeyboardInterrupt:
                break
                
    finally:
        watcher.stop()
        await watcher_task

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Soul Swarm Launcher")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--test", action="store_true", help="Test all souls once")
    args = parser.parse_args()
    
    if args.interactive:
        asyncio.run(run_interactive())
    elif args.test:
        # Test mode - post once with each soul
        async def test_all():
            transport = TransportFactory.create_from_env()
            await transport.refresh_tokens_from_disk()
            
            for soul in transport.get_available_souls():
                result = await transport.post_tweet(soul, f"Transport test from {soul}!")
                if result["success"]:
                    url = result.get("tweet", {}).get("url", "OK")
                    print(f"✅ {soul}: {url}")
                else:
                    print(f"❌ {soul}: {result.get('error')}")
                await asyncio.sleep(2)
        
        asyncio.run(test_all())
    else:
        # Normal orchestration mode
        orchestrator = YourOrchestrator()
        asyncio.run(orchestrator.start())

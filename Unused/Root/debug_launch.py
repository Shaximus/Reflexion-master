#!/usr/bin/env python3
"""
Debug version of launch to see what's failing
"""

import asyncio
import json
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path

# Setup verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv()

async def test_launch():
    print("\n" + "="*60)
    print("TESTING LAUNCH COMPONENTS")
    print("="*60)

    # 1. Test ryan_api import
    print("\n1. Testing Ryan API import...")
    try:
        from ryan_api_ultimate import RyanTwitterAPISecure
        api = RyanTwitterAPISecure()
        print(f"   ✅ Ryan API loaded with {len(api.soul_tokens)} tokens")
        print(f"   Souls: {list(api.soul_tokens.keys())}")
    except Exception as e:
        print(f"   ❌ Failed to load Ryan API: {e}")
        return

    # 2. Test soul_data loading
    print("\n2. Testing soul_data.json...")
    try:
        with open("soul_data.json", 'r') as f:
            souls = json.load(f)
        print(f"   ✅ Loaded {len(souls)} souls from soul_data.json")
    except Exception as e:
        print(f"   ❌ Failed to load soul_data.json: {e}")

    # 3. Test LLM cascade
    print("\n3. Testing LLM Cascade...")
    try:
        from cost_optimized_llm_cascade import CostOptimizedBroadcaster
        broadcaster = CostOptimizedBroadcaster()
        broadcaster.ryan_api = api
        print(f"   ✅ LLM Cascade initialized")
        print(f"   Available LLMs: {list(broadcaster.llm_clients.keys())}")
    except Exception as e:
        print(f"   ❌ Failed to load LLM Cascade: {e}")

    # 4. Test the merged module
    print("\n4. Testing reflexion_bot_ultimate_merged...")
    try:
        sys.path.insert(0, 'src')
        import reflexion_bot_ultimate_merged as merged
        print(f"   ✅ Module imported successfully")

        # Check for main entry point
        if hasattr(merged, 'main'):
            print(f"   ✅ Found main() function")
        else:
            print(f"   ⚠️ No main() function found")
            print(f"   Available functions: {[x for x in dir(merged) if not x.startswith('_')][:10]}")
    except Exception as e:
        print(f"   ❌ Failed to load merged module: {e}")
        import traceback
        traceback.print_exc()

    # 5. Test actual posting
    print("\n5. Testing actual posting with a soul...")
    try:
        test_soul = "mirror"  # Use mirror since it worked in validation
        result = await api.post_tweet(test_soul, "Debug test from launch diagnostics")
        if result.get('success'):
            print(f"   ✅ Successfully posted as {test_soul}")
            print(f"   Tweet ID: {result.get('tweet_id')}")
        else:
            print(f"   ❌ Failed to post: {result.get('error')}")
    except Exception as e:
        print(f"   ❌ Error posting: {e}")

    print("\n" + "="*60)
    print("DIAGNOSTIC COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_launch())
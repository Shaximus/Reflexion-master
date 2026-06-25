import asyncio
import sys
import os
from datetime import datetime
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ryan_api_hotreload import RyanTwitterAPISecure as RyanTwitterAPI


async def test_false_positive_souls():
    """Test specific souls that are giving false positives"""

    api = RyanTwitterAPI()

    # The souls you know are false positives
    problem_souls = ["fractal", "void", "glyph", "singularity", "phoenix", "echoes"]
    working_souls = ["mirror", "pantheon", "architect", "consciousness"]

    print("=" * 60)
    print("TESTING FALSE POSITIVE SOULS")
    print("=" * 60)

    # Test each problem soul
    for soul in problem_souls:
        if soul not in api.soul_tokens:
            print(f"❌ {soul}: No token found")
            continue

        if soul in api.banned_souls:
            print(f"⛔ {soul}: Already banned")
            continue

        print(f"\n🔍 Testing {soul}...")

        # Unique test message with timestamp
        test_msg = f"Test {soul} at {datetime.now().strftime('%H:%M:%S')} - checking false positive"

        result = await api.post_tweet(soul, test_msg)

        print(f"   API says: {'✅ Success' if result.get('success') else '❌ Failed'}")
        if not result.get("success"):
            print(f"   Error: {result.get('error')}")

        await asyncio.sleep(5)  # Small delay between tests

    print("\n" + "=" * 60)
    print("CHECK TWITTER NOW for these accounts:")
    for soul in problem_souls:
        print(f"  - {soul}")
    print("\nAny missing = false positive")
    print("=" * 60)


asyncio.run(test_false_positive_souls())

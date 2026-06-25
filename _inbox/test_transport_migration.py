#!/usr/bin/env python3
"""
TEST TRANSPORT MIGRATION
Verify that the transport interface is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_transport():
    """Test the transport interface integration"""
    
    print("🧪 Testing Transport Interface Integration\n")
    print("=" * 60)
    
    # Test 1: Import and create transport
    try:
        from twitter_transport import TransportFactory
        transport = TransportFactory.create_from_env()
        print("✅ Transport created successfully")
        print(f"   Type: {type(transport).__name__}")
    except Exception as e:
        print(f"❌ Failed to create transport: {e}")
        return
    
    # Test 2: Check hot-reload
    try:
        await transport.refresh_tokens_from_disk()
        print("✅ Hot-reload working")
    except Exception as e:
        print(f"❌ Hot-reload failed: {e}")
    
    # Test 3: Check available souls
    try:
        souls = transport.get_available_souls()
        print(f"✅ Found {len(souls)} available souls")
        if souls:
            print(f"   Souls: {', '.join(souls[:5])}...")
    except Exception as e:
        print(f"❌ Failed to get souls: {e}")
    
    # Test 4: Test posting (dry run)
    if souls:
        test_soul = souls[0]
        print(f"\n📝 Testing post with soul: {test_soul}")
        try:
            # This is a real API call - comment out if you don't want to post
            # result = await transport.post_tweet(test_soul, "Transport test!")
            # print(f"✅ Post test completed: {result.get('success')}")
            print("   (Post test skipped - uncomment to test)")
        except Exception as e:
            print(f"❌ Post test failed: {e}")
    
    # Test 5: Verify compatibility wrapper
    try:
        from ryan_api_compat import RyanTwitterAPISecure
        compat = RyanTwitterAPISecure()
        print("✅ Compatibility wrapper working")
    except ImportError:
        print("ℹ️  Compatibility wrapper not found (optional)")
    except Exception as e:
        print(f"❌ Compatibility wrapper error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Transport migration test complete!")

if __name__ == "__main__":
    asyncio.run(test_transport())

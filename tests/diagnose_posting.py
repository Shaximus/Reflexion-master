#!/usr/bin/env python3
"""
DIAGNOSTIC SCRIPT - Find out why posts aren't working
Run this to identify the exact problem
"""

import asyncio
import os
import json
from pathlib import Path

async def test_ryan_api():
    """Test if Ryan's API is working"""
    print("\n" + "="*60)
    print("TEST 1: Ryan's API Connection")
    print("="*60)
    
    try:
        from ryan_api_hotreload import RyanTwitterAPISecure as RyanTwitterAPI
        api = RyanTwitterAPI()
        
        # Check if API key exists
        if not api.headers.get("x-rapidapi-key"):
            print("❌ RYAN_API_KEY not set in environment!")
            print("   Add to .env: RYAN_API_KEY=your_actual_key")
            return False
            
        # Check auth tokens
        if not api.soul_tokens:
            print("❌ No auth tokens loaded!")
            print("   Check soul_data.json has auth_token values")
            return False
        
        print(f"✅ API key configured")
        print(f"✅ Auth tokens loaded for: {list(api.soul_tokens.keys())}")
        
        # Test actual posting
        test_soul = "mirror"
        if test_soul in api.soul_tokens:
            print(f"\n🧪 Testing post for {test_soul}...")
            result = await api.post_tweet(test_soul, "Test post - checking API")
            print(f"   Result: {json.dumps(result, indent=2)}")
            
            if result.get("success"):
                print("✅ Posting works!")
                return True
            else:
                print(f"❌ Posting failed: {result.get('error')}")
                return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_broadcaster():
    """Test if the broadcaster is using Ryan's API"""
    print("\n" + "="*60)
    print("TEST 2: Broadcaster Configuration")
    print("="*60)
    
    try:
        # Try to import the correct broadcaster
        from ryan_api_ultimate import CostOptimizedBroadcaster
        print("✅ Using ryan_api_ultimate broadcaster (GOOD - can post)")
        broadcaster = CostOptimizedBroadcaster()
        
        # Check if Ryan API is initialized
        if hasattr(broadcaster, 'ryan_api'):
            print("✅ Ryan API is initialized in broadcaster")
            if broadcaster.use_ryan_for_posting:
                print("✅ Configured to use Ryan for posting")
            else:
                print("❌ NOT configured to use Ryan for posting!")
        else:
            print("❌ Ryan API not found in broadcaster!")
            
    except ImportError:
        print("❌ ryan_api_ultimate not available")
        try:
            from cost_optimized_llm_cascade import CostOptimizedBroadcaster
            print("⚠️ Using cost_optimized_llm_cascade (BAD - content only, NO posting!)")
            print("   This is why posts aren't working!")
            return False
        except ImportError:
            print("❌ No broadcaster available")
            return False
    
    return True

async def test_actual_post():
    """Test an actual post with full flow"""
    print("\n" + "="*60)
    print("TEST 3: Full Posting Flow")
    print("="*60)
    
    try:
        # Import the broadcaster your system is actually using
        broadcaster = None
        
        # Check which one is being used
        try:
            # First check what hybrid_souls is importing
            import sys
            sys.path.insert(0, 'src')
            from hybrid_souls_ultimate import HybridReflexionOrchestrator
            
            # Create a dummy orchestrator to see what broadcaster it loads
            class DummyOrchestrator:
                pass
            
            orchestrator = HybridReflexionOrchestrator(DummyOrchestrator())
            broadcaster = orchestrator.broadcaster
            
            print(f"📍 Hybrid souls is using: {broadcaster.__class__.__module__}")
            
        except Exception as e:
            print(f"Could not load from hybrid_souls: {e}")
            
            # Fall back to direct import
            try:
                from ryan_api_ultimate import CostOptimizedBroadcaster
                broadcaster = CostOptimizedBroadcaster()
                print("Using ryan_api_ultimate directly")
            except:
                from cost_optimized_llm_cascade import CostOptimizedBroadcaster
                broadcaster = CostOptimizedBroadcaster()
                print("⚠️ Using cost_optimized_llm_cascade (no posting!)")
        
        if not broadcaster:
            print("❌ No broadcaster available")
            return False
        
        # Test the full flow
        print("\n🧪 Testing full post flow for 'mirror'...")
        result = await broadcaster.broadcast_soul("mirror")
        
        print(f"\nResult structure:")
        print(f"  success: {result.get('success')}")
        print(f"  content: {result.get('content', '')[:50]}...")
        print(f"  llm_used: {result.get('llm_used')}")
        print(f"  posted_via: {result.get('posted_via', 'NOT SET')}")
        print(f"  data: {result.get('data', {})}")
        
        if result.get('data'):
            print("\n✅ Got data back - post likely succeeded")
            return True
        else:
            print("\n❌ Empty data - post did NOT happen")
            print("   The broadcaster generated content but didn't post it")
            return False
            
    except Exception as e:
        print(f"❌ Error in full flow: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_auth_tokens():
    """Check if auth tokens are properly configured"""
    print("\n" + "="*60)
    print("TEST 4: Auth Token Configuration")
    print("="*60)
    
    soul_data = Path("soul_data.json")
    if not soul_data.exists():
        print("❌ soul_data.json not found!")
        return False
    
    with open(soul_data, 'r') as f:
        data = json.load(f)
    
    souls_with_tokens = 0
    souls_without_tokens = []
    
    for soul, config in data.items():
        if isinstance(config, dict):
            token = config.get("auth_token", "")
            if token and len(token) > 10:
                souls_with_tokens += 1
                print(f"✅ {soul}: Has token ({len(token)} chars)")
            else:
                souls_without_tokens.append(soul)
                print(f"❌ {soul}: NO TOKEN")
    
    if souls_without_tokens:
        print(f"\n⚠️ {len(souls_without_tokens)} souls missing auth tokens!")
        print("To get auth tokens:")
        print("1. Login to each soul account in browser")
        print("2. F12 → Application → Cookies → x.com")
        print("3. Find 'auth_token' cookie")
        print("4. Copy the VALUE and add to soul_data.json")
        return False
    
    print(f"\n✅ All {souls_with_tokens} souls have auth tokens")
    return True

def check_environment():
    """Check environment variables"""
    print("\n" + "="*60)
    print("TEST 5: Environment Variables")
    print("="*60)
    
    required_vars = {
        "RYAN_API_KEY": "RapidAPI key for Ryan's Twitter API",
        "DEEPSEEK_API_KEY": "DeepSeek LLM for content generation",
    }
    
    missing = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: NOT SET ({description})")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️ Add these to your .env file:")
        for var in missing:
            print(f"   {var}=your_actual_key_here")
        return False
    
    return True

async def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           DIAGNOSING WHY POSTS AREN'T WORKING               ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Run all tests
    env_ok = check_environment()
    tokens_ok = check_auth_tokens()
    ryan_ok = await test_ryan_api()
    broadcaster_ok = await test_broadcaster()
    post_ok = await test_actual_post()
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    
    if not env_ok:
        print("🔧 FIX: Add missing environment variables to .env")
    
    if not tokens_ok:
        print("🔧 FIX: Add auth_token values to soul_data.json")
    
    if not ryan_ok:
        print("🔧 FIX: Check Ryan API key and auth tokens")
    
    if not broadcaster_ok:
        print("🔧 FIX: Update hybrid_souls_ultimate.py to import from ryan_api_ultimate")
        print("        See Fix A from earlier patches")
    
    if not post_ok:
        print("🔧 FIX: The broadcaster isn't calling Ryan's post endpoint")
        print("        Ensure ryan_api_ultimate.CostOptimizedBroadcaster is used")
    
    if all([env_ok, tokens_ok, ryan_ok, broadcaster_ok, post_ok]):
        print("\n✅ Everything looks good! Posts should be working.")
    else:
        print("\n❌ Found issues above. Fix them and try again.")

if __name__ == "__main__":
    asyncio.run(main())

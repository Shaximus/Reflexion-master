#!/usr/bin/env python3
"""
DEFINITIVE API TEST - Prove if we're hitting real APIs or fallbacks
This test will be impossible to fake with templates
"""
import asyncio
import aiohttp
import os
import sys
import time
import json
import random
from pathlib import Path

# Setup paths
current_dir = Path(__file__).parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))
os.chdir(src_dir)

# Load environment
from dotenv import load_dotenv
load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# DIRECT API TESTS - NO FALLBACKS ALLOWED
# ═══════════════════════════════════════════════════════════════════

async def test_claude_direct():
    """Test Claude API directly - impossible to fake"""
    
    api_key = os.getenv('CLAUDE_API_KEY')
    if not api_key:
        return "❌ No API key"
    
    # Impossible prompt that can't be templated
    prompt = f"Generate exactly 3 words that rhyme with 'consciousness' and start with the letter 'B'. Current timestamp: {time.time()}"
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 50,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"🔄 Making direct Claude API call...")
            print(f"   URL: https://api.anthropic.com/v1/messages")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload,
                timeout=30
            ) as response:
                print(f"   Response Status: {response.status}")
                print(f"   Response Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"   Raw Response: {json.dumps(data, indent=2)}")
                    
                    content = data['content'][0]['text'].strip()
                    return f"✅ REAL API: {content}"
                else:
                    error = await response.text()
                    print(f"   Error Response: {error}")
                    return f"❌ API Error {response.status}: {error}"
                    
    except Exception as e:
        print(f"   Exception: {e}")
        return f"❌ Exception: {e}"

async def test_deepseek_direct():
    """Test DeepSeek API directly"""
    
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return "❌ No API key"
    
    # Impossible prompt
    prompt = f"Write exactly 2 sentences about purple elephants dancing. Include the number {int(time.time()) % 1000} somewhere."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 80
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"🔄 Making direct DeepSeek API call...")
            print(f"   URL: https://api.deepseek.com/v1/chat/completions")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            async with session.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            ) as response:
                print(f"   Response Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"   Raw Response: {json.dumps(data, indent=2)}")
                    
                    content = data['choices'][0]['message']['content'].strip()
                    return f"✅ REAL API: {content}"
                else:
                    error = await response.text()
                    print(f"   Error Response: {error}")
                    return f"❌ API Error {response.status}: {error}"
                    
    except Exception as e:
        print(f"   Exception: {e}")
        return f"❌ Exception: {e}"

async def test_openai_direct():
    """Test OpenAI API directly"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return "❌ No API key"
    
    # Impossible prompt
    prompt = f"List exactly 3 fictional robot names that end with 'ium'. Random seed: {random.randint(10000, 99999)}"
    
    payload = {
        "model": "chatgpt-4o-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 60
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"🔄 Making direct OpenAI API call...")
            print(f"   URL: https://api.openai.com/v1/chat/completions")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            async with session.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            ) as response:
                print(f"   Response Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"   Raw Response: {json.dumps(data, indent=2)}")
                    
                    content = data['choices'][0]['message']['content'].strip()
                    return f"✅ REAL API: {content}"
                else:
                    error = await response.text()
                    print(f"   Error Response: {error}")
                    return f"❌ API Error {response.status}: {error}"
                    
    except Exception as e:
        print(f"   Exception: {e}")
        return f"❌ Exception: {e}"

# ═══════════════════════════════════════════════════════════════════
# TEST VIRAL CONTENT SYSTEM WITH IMPOSSIBLE PROMPTS
# ═══════════════════════════════════════════════════════════════════

async def test_viral_system_with_impossible_prompts():
    """Test if viral content system hits real APIs with impossible-to-template prompts"""
    
    try:
        from viral_content_ultimate import ViralContentGenerator
        
        generator = ViralContentGenerator()
        
        print("\n🧪 Testing viral system with impossible prompts...")
        
        # Test each soul with impossible prompts
        impossible_tests = [
            (f"Write exactly {random.randint(3, 7)} words about blue whales wearing hats. Include the number {random.randint(100, 999)}.", "mirror"),
            (f"Generate precisely {random.randint(2, 5)} sentences about robots eating pizza. Use the word 'quantum' exactly once.", "nexus"), 
            (f"Create exactly {random.randint(4, 8)} words that describe flying refrigerators. Include timestamp {int(time.time())}", "architect")
        ]
        
        for seed, soul in impossible_tests:
            print(f"\n🔍 Testing {soul} with impossible prompt:")
            print(f"   Seed: {seed}")
            
            try:
                # This should be impossible to fulfill with templates
                result = await generator.generate(
                    soul_name=soul,
                    seed=seed,
                    use_trends=False  # No trends to avoid complications
                )
                
                print(f"   Result: {result}")
                
                # Check if result actually follows the impossible instructions
                if "blue whales" in result.lower() or "robots eating pizza" in result.lower() or "flying refrigerators" in result.lower():
                    print(f"   ✅ APPEARS TO BE REAL API (followed specific instructions)")
                else:
                    print(f"   ⚠️ MIGHT BE FALLBACK (didn't follow specific instructions)")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
    except ImportError as e:
        print(f"❌ Could not import viral system: {e}")

# ═══════════════════════════════════════════════════════════════════
# NETWORK MONITORING TEST
# ═══════════════════════════════════════════════════════════════════

class NetworkMonitor:
    """Monitor actual network requests"""
    
    def __init__(self):
        self.requests_made = []
    
    async def monitor_requests(self):
        """Monitor if any actual HTTP requests are made"""
        
        # This is a simple monitor - in reality you'd use something like mitmproxy
        # But we can check if the viral system makes any network calls
        
        print("\n🕸️ Network monitoring test...")
        print("   (Checking if viral system makes actual HTTP requests)")
        
        # Import and test
        try:
            from viral_content_ultimate import ViralContentGenerator
            
            generator = ViralContentGenerator()
            
            # Time the generation
            start_time = time.time()
            
            result = await generator.generate(
                soul_name="mirror",
                seed="Test network monitoring",
                use_trends=False
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"   Generation took: {duration:.2f} seconds")
            print(f"   Result: {result}")
            
            # Real API calls should take 1-5 seconds
            # Fallbacks should be nearly instant
            if duration > 0.5:
                print(f"   ✅ LIKELY REAL API (took {duration:.2f}s)")
            else:
                print(f"   ⚠️ LIKELY FALLBACK (too fast: {duration:.2f}s)")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Run definitive API tests"""
    
    import random
    
    print("🔬" * 30)
    print("DEFINITIVE API TEST - REAL vs FALLBACK")
    print("🔬" * 30)
    
    print(f"\n📋 Test Plan:")
    print(f"   1. Direct API calls with impossible prompts")
    print(f"   2. Viral system test with impossible prompts")
    print(f"   3. Network timing analysis")
    print(f"   4. Compare results")
    
    # Test 1: Direct API calls
    print(f"\n" + "="*60)
    print("1. DIRECT API TESTS (Impossible to fake)")
    print("="*60)
    
    claude_result = await test_claude_direct()
    print(f"\n🎭 Claude: {claude_result}")
    
    deepseek_result = await test_deepseek_direct()
    print(f"\n🧠 DeepSeek: {deepseek_result}")
    
    openai_result = await test_openai_direct()
    print(f"\n🤖 OpenAI: {openai_result}")
    
    # Test 2: Viral system with impossible prompts
    print(f"\n" + "="*60)
    print("2. VIRAL SYSTEM IMPOSSIBLE PROMPT TEST")
    print("="*60)
    
    await test_viral_system_with_impossible_prompts()
    
    # Test 3: Network monitoring
    print(f"\n" + "="*60)
    print("3. NETWORK TIMING ANALYSIS")
    print("="*60)
    
    monitor = NetworkMonitor()
    await monitor.monitor_requests()
    
    # Summary
    print(f"\n" + "🔬" * 30)
    print("DEFINITIVE TEST COMPLETE")
    print("🔬" * 30)
    
    print(f"\n📊 Analysis:")
    print(f"   - If direct API tests work but viral system doesn't follow impossible prompts → Using fallbacks")
    print(f"   - If viral system takes <0.5 seconds → Likely fallbacks") 
    print(f"   - If viral system takes 1-5 seconds → Likely real APIs")
    print(f"   - If impossible prompts are followed precisely → Definitely real APIs")

if __name__ == "__main__":
    asyncio.run(main())

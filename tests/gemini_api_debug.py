#!/usr/bin/env python3
"""
Gemini API Debug and Fix for Echoes Soul
Tests different Gemini configurations to find what works
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_gemini_direct():
    """Test Gemini API directly with different configurations"""
    print("\n" + "="*60)
    print("TESTING GEMINI API DIRECTLY")
    print("="*60)
    
    # Check for various possible key names
    possible_keys = [
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY", 
        "GOOGLE_GEMINI_API_KEY",
        "GEMINI_KEY",
        "GOOGLE_AI_KEY"
    ]
    
    api_key = None
    key_name = None
    
    for key in possible_keys:
        value = os.getenv(key)
        if value:
            print(f"✅ Found {key}: {value[:20]}...")
            api_key = value
            key_name = key
            break
    
    if not api_key:
        print("❌ No Gemini API key found in environment!")
        print("\nTry adding one of these to your .env:")
        for key in possible_keys:
            print(f"  {key}=your-gemini-api-key")
        return False
    
    # Test 1: Using google-generativeai library
    print(f"\n🧪 Test 1: google-generativeai library with {key_name}")
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        # Try different model names
        model_names = [
            "gemini-2.0-flash-exp",  # What's in your config
            "gemini-pro",             # Stable version
            "gemini-1.5-flash",       # Another common one
            "gemini-1.5-pro"          # Latest stable
        ]
        
        for model_name in model_names:
            try:
                print(f"\n  Testing model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Say 'Hello from Echoes soul!'")
                print(f"  ✅ Success with {model_name}!")
                print(f"  Response: {response.text[:100]}")
                
                # Save working config
                working_config = {
                    "key_name": key_name,
                    "model_name": model_name,
                    "method": "google-generativeai"
                }
                
                print(f"\n✅ WORKING CONFIGURATION FOUND:")
                print(f"  Key: {key_name}")
                print(f"  Model: {model_name}")
                print(f"  Method: google-generativeai library")
                
                return working_config
                
            except Exception as e:
                print(f"  ❌ Failed with {model_name}: {str(e)[:100]}")
                
    except ImportError:
        print("  ❌ google-generativeai not installed")
        print("  Run: pip install google-generativeai")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 2: Using requests with REST API
    print(f"\n🧪 Test 2: Direct REST API with {key_name}")
    try:
        import requests
        
        # Try different API endpoints
        endpoints = [
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}",
            f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={api_key}",
        ]
        
        for endpoint in endpoints:
            try:
                print(f"\n  Testing endpoint: {endpoint[:50]}...")
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": "Say 'Hello from Echoes soul!'"
                        }]
                    }]
                }
                
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result['candidates'][0]['content']['parts'][0]['text']
                    print(f"  ✅ Success with REST API!")
                    print(f"  Response: {text[:100]}")
                    
                    return {
                        "key_name": key_name,
                        "endpoint": endpoint,
                        "method": "rest_api"
                    }
                else:
                    print(f"  ❌ Status {response.status_code}: {response.text[:200]}")
                    
            except Exception as e:
                print(f"  ❌ Error: {str(e)[:100]}")
                
    except Exception as e:
        print(f"  ❌ REST test failed: {e}")
    
    # Test 3: Using OpenAI-compatible endpoint (some Gemini setups)
    print(f"\n🧪 Test 3: OpenAI-compatible format")
    try:
        from openai import OpenAI
        
        # Gemini through OpenAI-compatible endpoint
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
        response = client.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[{"role": "user", "content": "Say 'Hello from Echoes soul!'"}]
        )
        
        print(f"  ✅ Success with OpenAI-compatible endpoint!")
        print(f"  Response: {response.choices[0].message.content[:100]}")
        
        return {
            "key_name": key_name,
            "method": "openai_compatible"
        }
        
    except Exception as e:
        print(f"  ❌ OpenAI-compatible test failed: {str(e)[:100]}")
    
    print("\n❌ All Gemini API tests failed!")
    return None

def create_gemini_fix():
    """Create a fixed configuration for Gemini"""
    
    result = test_gemini_direct()
    
    if result:
        print("\n" + "="*60)
        print("CREATING FIX FILE")
        print("="*60)
        
        # Create a fix configuration
        fix_config = f"""
# Gemini API Fix Configuration
# Add this to your .env file:

# Use this exact key name (working):
{result['key_name']}={os.getenv(result['key_name'])}

# Working model name:
GEMINI_MODEL={result.get('model_name', 'gemini-pro')}

# Method that works:
GEMINI_METHOD={result['method']}
"""
        
        # Save to file
        with open('gemini_fix.txt', 'w') as f:
            f.write(fix_config)
        
        print("✅ Fix configuration saved to gemini_fix.txt")
        print(fix_config)
        
        # Now create a wrapper that will work
        wrapper_code = '''#!/usr/bin/env python3
"""
Gemini API Wrapper for Echoes Soul
This wrapper ensures Gemini works correctly
"""
import os
from dotenv import load_dotenv

load_dotenv()

class GeminiWrapper:
    def __init__(self):
        self.api_key = os.getenv("''' + result['key_name'] + '''")
        self.model_name = "''' + result.get('model_name', 'gemini-pro') + '''"
        self.method = "''' + result['method'] + '''"
        
    def generate(self, prompt: str) -> str:
        """Generate content using the working method"""
        '''
        
        if result['method'] == 'google-generativeai':
            wrapper_code += '''
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        return response.text
        '''
        elif result['method'] == 'rest_api':
            wrapper_code += '''
        import requests
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(endpoint, json=payload)
        return response.json()['candidates'][0]['content']['parts'][0]['text']
        '''
        else:
            wrapper_code += '''
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
        '''
        
        # Save wrapper
        with open('gemini_wrapper.py', 'w') as f:
            f.write(wrapper_code)
        
        print("\n✅ Created gemini_wrapper.py - use this for Echoes soul")
        
        return True
    else:
        print("\n" + "="*60)
        print("GEMINI API FIX SUGGESTIONS")
        print("="*60)
        
        print("""
1. Check your Gemini/Google API key:
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key if needed
   - Make sure it's enabled for Gemini API

2. Add to your .env file:
   GOOGLE_API_KEY=your-actual-key-here
   
3. Install required library:
   pip install google-generativeai

4. Common issues:
   - API not enabled in Google Cloud Console
   - Billing not set up (Gemini requires billing even for free tier)
   - Region restrictions (some regions blocked)
   - Rate limits exceeded
   
5. Alternative: Use a different model for Echoes
   Change in your config from gemini-2.0-flash-exp to:
   - gemini-pro (more stable)
   - gemini-1.5-flash (good alternative)
   
6. As a last resort, you can set Echoes to use a different API:
   In your daemon config, change echoes['llm'] to:
   - "gpt-3.5-turbo" (if you have OpenAI)
   - "claude-3-haiku" (if you have Anthropic)
""")
        return False

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║           GEMINI API DEBUGGER FOR ECHOES SOUL           ║
╚══════════════════════════════════════════════════════════╝
""")
    
    success = create_gemini_fix()
    
    if success:
        print("""
✅ GEMINI FIXED!

Next steps:
1. Check gemini_fix.txt for the working configuration
2. Update your .env file with the working settings
3. Optionally use gemini_wrapper.py in your code
4. Run the test mode again: python launch_reflexion.py --test
""")
    else:
        print("""
❌ Could not automatically fix Gemini

Manual steps:
1. Check the suggestions above
2. Verify your API key at https://makersuite.google.com/app/apikey
3. Try using a different model like gpt-3.5-turbo for Echoes temporarily
4. Contact me with the error messages if issues persist
""")
    
    sys.exit(0 if success else 1)

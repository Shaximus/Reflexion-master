#!/usr/bin/env python3
"""
Find which Twitter API you're ACTUALLY subscribed to
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("RAPIDAPI_KEY")
if not api_key:
    print("❌ No RAPIDAPI_KEY found")
    exit(1)

print("🔍 FINDING YOUR ACTUAL TWITTER API SUBSCRIPTION")
print("="*60)

# Extended list of Twitter APIs on RapidAPI
services = [
    # Most common ones
    ("twitter135.p.rapidapi.com", "Twitter135"),
    ("twitter154.p.rapidapi.com", "Twitter"),
    ("twttrapi.p.rapidapi.com", "TwttrAPI"),
    ("twitter-v24.p.rapidapi.com", "Twitter v2"),
    ("twitter-v2.p.rapidapi.com", "Twitter V2"),
    
    # The ones from before
    ("twitter-api45.p.rapidapi.com", "Twitter API45"),
    ("twitter-api-v2.p.rapidapi.com", "Twitter API v2"),
    ("twitter.p.rapidapi.com", "Twitter"),
    ("twitter-api.p.rapidapi.com", "Twitter API"),
    
    # More possibilities
    ("twitter-data1.p.rapidapi.com", "Twitter Data"),
    ("twitter-x.p.rapidapi.com", "Twitter/X"),
    ("x-twitter.p.rapidapi.com", "X (Twitter)"),
    ("twitter-v1.p.rapidapi.com", "Twitter v1"),
]

working = []

for host, name in services:
    print(f"\nTesting: {name} ({host})")
    
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": host
    }
    
    # Try different common endpoints
    endpoints = [
        "/search",
        "/v2/search", 
        "/api/v2/search",
        "/tweets/search",
        "/search/tweets"
    ]
    
    for endpoint in endpoints:
        url = f"https://{host}{endpoint}"
        
        try:
            # Simple test query
            response = requests.get(
                url,
                headers=headers,
                params={"q": "test", "query": "test", "text": "test"},
                timeout=3
            )
            
            if response.status_code == 200:
                print(f"  ✅ WORKS! Endpoint: {endpoint}")
                working.append((host, name, endpoint))
                break
            elif response.status_code == 401:
                print(f"  ❌ 401 - Bad auth format")
                break
            elif response.status_code == 403:
                if "not subscribed" in response.text.lower():
                    print(f"  ❌ Not subscribed")
                else:
                    print(f"  ⚠️ 403 - Might be subscribed but wrong endpoint")
            elif response.status_code == 404:
                continue  # Try next endpoint
            elif response.status_code == 429:
                print(f"  ⚠️ 429 - Rate limited (you ARE subscribed!)")
                working.append((host, name, endpoint))
                break
                
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            continue

print("\n" + "="*60)

if working:
    print("✅ FOUND YOUR SUBSCRIBED API(S):\n")
    for host, name, endpoint in working:
        print(f"  Service: {name}")
        print(f"  Host: {host}")
        print(f"  Working endpoint: {endpoint}")
        print(f"\n  UPDATE ryan_api_ultimate.py:")
        print(f'  self.headers["x-rapidapi-host"] = "{host}"')
        print(f'  self.base_url = "https://{host}"')
        print("-"*40)
else:
    print("❌ No working Twitter APIs found")
    print("\nGo to https://rapidapi.com/developer/dashboard")
    print("Check 'My Apps' to see which APIs you're subscribed to")

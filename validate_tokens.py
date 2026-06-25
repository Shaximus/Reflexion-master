#!/usr/bin/env python3
"""
Auth Token Validator - Tests all soul tokens and reports which need updating
"""

import asyncio
import json
import aiohttp
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

class TokenValidator:
    def __init__(self):
        self.base_url = "https://twitter-api47.p.rapidapi.com"
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY")
        if not self.rapidapi_key:
            raise ValueError("RAPIDAPI_KEY not found in environment")

        self.headers = {
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        self.results = {}

    def load_soul_data(self):
        """Load soul data with tokens"""
        soul_file = Path("soul_data.json")
        if not soul_file.exists():
            print("❌ soul_data.json not found!")
            return {}

        with open(soul_file, 'r') as f:
            data = json.load(f)

        souls = {}
        for soul_name, info in data.items():
            if isinstance(info, dict):
                token = info.get("auth_token", "")
                username = info.get("username", "")
                if token and token != "GET_FROM_BROWSER":
                    souls[soul_name] = {
                        "token": token,
                        "username": username
                    }
        return souls

    async def test_token(self, soul_name: str, soul_info: dict):
        """Test if a token can post a tweet"""
        print(f"🔍 Testing {soul_name} (@{soul_info.get('username', 'unknown')})...", end=" ")

        # Test with the primary endpoint ryan_api uses
        url = f"{self.base_url}/v2/interaction/create-post"
        test_content = f"Token validation test {datetime.now().timestamp()}"

        payload = {
            "text": test_content,
            "authToken": soul_info["token"]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()

                    # Check various success indicators
                    if response.status == 200:
                        if "data" in data or "create_tweet" in data:
                            # Token works! Now delete the test tweet if we got an ID
                            tweet_id = self._extract_tweet_id(data)
                            if tweet_id:
                                await self.delete_test_tweet(soul_info["token"], tweet_id)
                            print("✅ VALID")
                            return {
                                "status": "valid",
                                "username": soul_info.get("username"),
                                "tested_at": datetime.now().isoformat()
                            }
                        elif "errors" in data:
                            error_msg = str(data.get("errors", ""))
                            if "User is suspended" in error_msg:
                                print("⛔ SUSPENDED")
                                return {"status": "suspended", "error": "Account suspended"}
                            elif "Could not authenticate" in error_msg:
                                print("❌ INVALID TOKEN")
                                return {"status": "invalid", "error": "Authentication failed"}
                            else:
                                print(f"⚠️ ERROR: {error_msg[:50]}")
                                return {"status": "error", "error": error_msg[:100]}

                    # Check for rate limiting
                    if response.status == 429:
                        print("⏳ RATE LIMITED")
                        return {"status": "rate_limited"}

                    # Generic failure
                    print(f"❌ FAILED (Status: {response.status})")
                    return {
                        "status": "failed",
                        "http_status": response.status,
                        "error": str(data)[:100]
                    }

        except asyncio.TimeoutError:
            print("⏱️ TIMEOUT")
            return {"status": "timeout"}
        except Exception as e:
            print(f"❌ ERROR: {str(e)[:50]}")
            return {"status": "error", "error": str(e)[:100]}

    def _extract_tweet_id(self, data):
        """Extract tweet ID from response"""
        # Try common paths
        paths = [
            ["data", "create_tweet", "tweet_results", "result", "rest_id"],
            ["create_tweet", "tweet_results", "result", "rest_id"],
            ["data", "id"],
            ["id"]
        ]

        for path in paths:
            current = data
            for key in path:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    break
            if current and str(current).isdigit():
                return str(current)
        return None

    async def delete_test_tweet(self, token: str, tweet_id: str):
        """Delete test tweet to keep timeline clean"""
        url = f"{self.base_url}/v2/tweet/delete"
        payload = {"authToken": token, "tweet_id": tweet_id}

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=5))
        except:
            pass  # Ignore deletion failures

    async def validate_all(self):
        """Validate all soul tokens"""
        souls = self.load_soul_data()

        if not souls:
            print("❌ No souls with tokens found!")
            return

        print(f"\n🔄 Validating {len(souls)} soul tokens...\n")
        print("=" * 60)

        # Test all tokens
        for soul_name, soul_info in souls.items():
            result = await self.test_token(soul_name, soul_info)
            self.results[soul_name] = result
            await asyncio.sleep(1)  # Rate limiting

        # Generate report
        print("\n" + "=" * 60)
        print("📊 VALIDATION REPORT")
        print("=" * 60)

        valid_count = sum(1 for r in self.results.values() if r["status"] == "valid")
        invalid_count = sum(1 for r in self.results.values() if r["status"] == "invalid")
        suspended_count = sum(1 for r in self.results.values() if r["status"] == "suspended")
        error_count = sum(1 for r in self.results.values() if r["status"] not in ["valid", "invalid", "suspended"])

        print(f"\n✅ Valid tokens: {valid_count}/{len(souls)}")
        print(f"❌ Invalid tokens: {invalid_count}")
        print(f"⛔ Suspended accounts: {suspended_count}")
        print(f"⚠️ Errors/Other: {error_count}")

        # List souls needing new tokens
        needs_update = []
        for soul_name, result in self.results.items():
            if result["status"] != "valid":
                needs_update.append((soul_name, result["status"]))

        if needs_update:
            print("\n🔧 SOULS NEEDING TOKEN UPDATES:")
            print("-" * 40)
            for soul_name, status in needs_update:
                username = souls.get(soul_name, {}).get("username", "unknown")
                print(f"  • {soul_name:15} (@{username:20}) - {status}")

            print("\n📝 HOW TO GET NEW TOKENS:")
            print("-" * 40)
            print("1. Open Chrome/Firefox in incognito mode")
            print("2. Log into each soul's Twitter account")
            print("3. Open Developer Tools (F12) → Network tab")
            print("4. Post a tweet or like something")
            print("5. Look for 'CreateTweet' or 'FavoriteTweet' request")
            print("6. Find 'authorization: Bearer ...' header")
            print("7. Or find 'auth_token' cookie value")
            print("8. Update soul_data.json with new token")
        else:
            print("\n🎉 All tokens are valid!")

        # Save detailed results
        results_file = Path("token_validation_results.json")
        with open(results_file, 'w') as f:
            json.dump({
                "validated_at": datetime.now().isoformat(),
                "summary": {
                    "total": len(souls),
                    "valid": valid_count,
                    "invalid": invalid_count,
                    "suspended": suspended_count,
                    "errors": error_count
                },
                "details": self.results
            }, f, indent=2)

        print(f"\n💾 Detailed results saved to {results_file}")

        return self.results

async def main():
    validator = TokenValidator()
    await validator.validate_all()

if __name__ == "__main__":
    print("🚀 Soul Token Validator v1.0")
    print("=" * 60)
    asyncio.run(main())
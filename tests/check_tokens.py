"""
Token Checker - Identifies which souls need new auth tokens
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta


class TokenChecker:
    def __init__(self):
        self.base_url = "https://twitter-api47.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "x-rapidapi-key": "b6b201782cmshb226957f2fdb9b2p1715e9jsn11b8fe9b9c52",
            "Content-Type": "application/json",
        }

        with open("soul_data.json", "r") as f:
            self.soul_data = json.load(f)

    async def test_token(self, soul_name, soul_info):
        """Test if a token can post"""
        if soul_info.get("auth_token") == "GET_FROM_BROWSER":
            return "NO_TOKEN"

        url = f"{self.base_url}/v2/interaction/create-post"
        test_text = f"Token test {datetime.now().timestamp()}"

        payload = {"authToken": soul_info["auth_token"], "text": test_text}

        try:
            async with aiohttp.ClientSession() as session:
                # Just check if we CAN post (don't actually post)
                async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        # Delete the test tweet if it posted
                        return "VALID"
                    elif response.status == 401:
                        return "EXPIRED"
                    elif response.status == 403:
                        return "FORBIDDEN"
                    else:
                        return f"ERROR_{response.status}"
        except:
            return "ERROR"

    async def check_all(self):
        """Check all soul tokens"""
        print("\n" + "=" * 60)
        print("AUTH TOKEN STATUS CHECK")
        print("=" * 60 + "\n")

        results = {}

        for soul_name, soul_info in self.soul_data.items():
            if isinstance(soul_info, dict):
                status = await self.test_token(soul_name, soul_info)
                results[soul_name] = status

                # Display result
                username = soul_info.get("username", "unknown")
                created = soul_info.get("created_date", "unknown")

                if status == "VALID":
                    print(f"✅ {soul_name:15} @{username:20} Token WORKING")
                elif status == "EXPIRED":
                    print(
                        f"❌ {soul_name:15} @{username:20} Token EXPIRED - needs refresh"
                    )
                elif status == "FORBIDDEN":
                    print(f"⚠️  {soul_name:15} @{username:20} Wrong token or account")
                elif status == "NO_TOKEN":
                    print(f"❌ {soul_name:15} @{username:20} No token configured")
                else:
                    print(f"⚠️  {soul_name:15} @{username:20} {status}")

                await asyncio.sleep(1)  # Rate limit

        # Summary and instructions
        print("\n" + "=" * 60)
        print("HOW TO FIX EXPIRED TOKENS:")
        print("=" * 60)

        expired_souls = [
            s
            for s, status in results.items()
            if status in ["EXPIRED", "FORBIDDEN", "NO_TOKEN"]
        ]

        if expired_souls:
            print("\nFor each soul that needs a new token:\n")

            for soul in expired_souls:
                username = self.soul_data[soul].get("username", "unknown")
                print(f"🔧 {soul} (@{username}):")
                print(f"   1. Login to Twitter as @{username}")
                print(f"   2. Press F12 → Application tab")
                print(f"   3. Cookies → https://twitter.com")
                print(f"   4. Find 'auth_token' cookie")
                print(f"   5. Copy the entire value (40 characters)")
                print(f"   6. Update in soul_data.json\n")
        else:
            print("✅ All tokens are working!")

        # Create update template
        if expired_souls:
            print("\n" + "=" * 60)
            print("QUICK UPDATE TEMPLATE:")
            print("=" * 60)
            print("\nPaste these into soul_data.json after getting tokens:\n")

            for soul in expired_souls:
                print(f'  "{soul}": {{')
                print(f'    "created_date": "{datetime.now().isoformat()}",')
                print(f'    "auth_token": "PASTE_NEW_TOKEN_HERE",')
                print(f'    "username": "{self.soul_data[soul].get("username", "")}"')
                print(f"  }},")


async def main():
    checker = TokenChecker()
    await checker.check_all()


if __name__ == "__main__":
    print("Checking which tokens need updating...")
    asyncio.run(main())

#!/usr/bin/env python3
"""
Ryan API Diagnostic with CORRECT endpoints from documentation
"""

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()


async def test_endpoint(session, endpoint, params, name=""):
    """Test an endpoint with proper error handling"""
    api_key = os.getenv("RAPIDAPI_KEY")
    base_url = "https://twitter-api47.p.rapidapi.com"
    headers = {
        "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
        "x-rapidapi-key": api_key,
    }

    url = f"{base_url}{endpoint}"

    print(f"\n{'='*60}")
    print(f"Testing: {name or endpoint}")
    print(f"Params: {params}")
    print("-" * 60)

    try:
        async with session.get(url, headers=headers, params=params) as response:
            print(f"Status: {response.status}")

            if response.status == 200:
                data = await response.json()
                print(f"✅ SUCCESS!")

                # Show data structure
                if isinstance(data, dict):
                    print(f"Response keys: {list(data.keys())}")
                    for key in list(data.keys())[:3]:
                        value = data[key]
                        if isinstance(value, list):
                            print(f"  {key}: {len(value)} items")
                            if value:
                                print(
                                    f"    Sample: {value[0] if not isinstance(value[0], dict) else list(value[0].keys())[:5]}"
                                )
                        elif isinstance(value, dict):
                            print(f"  {key}: {len(value)} keys")
                        else:
                            print(f"  {key}: {value}")
                elif isinstance(data, list):
                    print(f"Response: List with {len(data)} items")
                    if data:
                        print(
                            f"  First item: {data[0] if not isinstance(data[0], dict) else list(data[0].keys())[:5]}"
                        )

                return data
            else:
                error = await response.text()
                print(f"❌ FAILED: {error[:200]}")
                return None
    except Exception as e:
        print(f"💥 Exception: {e}")
        return None


async def main():
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        print("❌ RAPIDAPI_KEY not found in .env")
        return

    print(
        """
    ╔══════════════════════════════════════════════════╗
    ║     RYAN API - CORRECT ENDPOINTS TEST            ║
    ╚══════════════════════════════════════════════════╝
    """
    )

    # First get user IDs we'll need
    test_user = "elonmusk"
    bot_user = "elon_x0648"

    async with aiohttp.ClientSession() as session:
        # Get Elon's user ID
        print("\n🔑 Getting User IDs...")
        data = await test_endpoint(
            session,
            "/v2/user/by-username",
            {"username": test_user},
            f"Get {test_user} profile",
        )
        elon_id = data.get("rest_id") if data else None
        print(f"  Elon ID: {elon_id}")

        # Get bot's user ID
        data = await test_endpoint(
            session,
            "/v2/user/by-username",
            {"username": bot_user},
            f"Get {bot_user} profile",
        )
        bot_id = data.get("rest_id") if data else None
        print(f"  Bot ID: {bot_id}")

        if not elon_id or not bot_id:
            print("Failed to get user IDs")
            return

        print("\n" + "█" * 60)
        print("TESTING ACTUAL FOLLOWER/FOLLOWING ENDPOINTS")
        print("█" * 60)

        # Test followers-list
        await test_endpoint(
            session,
            "/v2/user/followers-list",
            {"userId": bot_id, "count": 20},
            "Get Bot Followers List",
        )

        # Test following-list
        await test_endpoint(
            session,
            "/v2/user/following-list",
            {"userId": bot_id, "count": 20},
            "Get Bot Following List",
        )

        # Test followers-ids
        await test_endpoint(
            session,
            "/v2/user/followers-ids",
            {"userId": bot_id, "count": 20},
            "Get Bot Follower IDs",
        )

        # Test following-ids
        await test_endpoint(
            session,
            "/v2/user/following-ids",
            {"userId": bot_id, "count": 20},
            "Get Bot Following IDs",
        )

        # Test followers (no -list suffix)
        await test_endpoint(
            session, "/v2/user/followers", {"userId": bot_id}, "Get Bot Followers (v1)"
        )

        # Test following (no -list suffix)
        await test_endpoint(
            session, "/v2/user/following", {"userId": bot_id}, "Get Bot Following (v1)"
        )

        print("\n" + "█" * 60)
        print("TESTING TWEET ENDPOINTS")
        print("█" * 60)

        # Test tweets endpoint with userId
        await test_endpoint(
            session, "/v2/user/tweets", {"userId": bot_id}, "Get Bot Tweets"
        )

        # Test tweets-and-replies with userId
        await test_endpoint(
            session,
            "/v2/user/tweets-and-replies",
            {"userId": bot_id},
            "Get Bot Tweets and Replies",
        )

        print("\n" + "█" * 60)
        print("LIST ENDPOINTS - POTENTIAL BOT LISTS")
        print("█" * 60)

        # Test list endpoints with specific listId
        list_id = "1433448123142115329"

        # Get list details
        await test_endpoint(
            session,
            "/v2/list/details",
            {"listId": list_id},
            f"Get List Details for {list_id}",
        )

        # Get list tweets
        await test_endpoint(
            session, "/v2/list/tweets", {"listId": list_id}, f"Get List Tweets"
        )

        # Get list members - THIS IS KEY FOR BOT NETWORKS
        data = await test_endpoint(
            session, "/v2/list/members", {"listId": list_id}, f"Get List Members"
        )

        if data and "users" in data:
            print(f"\n🎯 Analyzing list members for bot patterns:")
            creation_dates = []
            for user in data["users"][:20]:
                if isinstance(user, dict):
                    username = user.get("legacy", {}).get("screen_name", "unknown")
                    created = user.get("legacy", {}).get("created_at", "")
                    followers = user.get("legacy", {}).get("followers_count", 0)
                    following = user.get("legacy", {}).get("friends_count", 0)
                    print(f"  @{username}")
                    print(f"    Created: {created}")
                    print(f"    Followers: {followers}, Following: {following}")
                    creation_dates.append(created)

            # Check for batch creation patterns
            if creation_dates:
                print(f"\n📊 Creation pattern analysis:")
                print(f"  Total members analyzed: {len(creation_dates)}")

        # Get list followers
        await test_endpoint(
            session, "/v2/list/followers", {"listId": list_id}, f"Get List Followers"
        )

        print("\n" + "█" * 60)
        print("TESTING INTERACTION ENDPOINTS (POST)")
        print("█" * 60)

        # Need an auth token from soul_data.json for POST endpoints
        import json
        from pathlib import Path

        # Try multiple paths to find soul_data.json
        possible_paths = [
            Path("soul_data.json"),  # Current directory
            Path("../soul_data.json"),  # One up
            Path("../../soul_data.json"),  # Two up (if in vigilante folder)
        ]

        auth_token = None
        soul_data = None

        for soul_data_path in possible_paths:
            if soul_data_path.exists():
                print(f"  Found soul_data.json at: {soul_data_path}")
                with open(soul_data_path, "r") as f:
                    soul_data = json.load(f)
                    break

        if soul_data:
            # Get first available token
            for soul, token_info in soul_data.items():
                if isinstance(token_info, dict):
                    auth_token = token_info.get("auth_token")
                else:
                    auth_token = token_info
                if auth_token and auth_token not in [
                    "GET_FROM_BROWSER",
                    "GET_FROM_BROWSER_COOKIES",
                ]:
                    print(f"  Using auth token from soul: {soul}")
                    break

        if not auth_token:
            print(
                "❌ No valid auth token found in soul_data.json - skipping POST tests"
            )
            print(
                "  Make sure soul_data.json has actual tokens, not 'GET_FROM_BROWSER'"
            )
        else:
            # Define base_url and headers for POST tests
            base_url = "https://twitter-api47.p.rapidapi.com"
            headers = {
                "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
                "x-rapidapi-key": api_key,
            }

            # Test like-post endpoint
            print("\n" + "=" * 60)
            print("Testing: Like Post")
            print("-" * 60)

            # Use a real tweet ID (you can change this)
            test_tweet_id = "1234567890"

            url = f"{base_url}/v2/interaction/like-post"
            payload = {"authToken": auth_token, "tweetId": test_tweet_id}

            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Like endpoint works!")
                        print(f"Response: {data}")
                    else:
                        error = await response.text()
                        print(f"❌ Failed: {error[:200]}")
            except Exception as e:
                print(f"💥 Exception: {e}")

            # Test create-post-with-media
            print("\n" + "=" * 60)
            print("Testing: Create Post with Media")
            print("-" * 60)

            payload = {
                "authToken": auth_token,
                "text": "Test post with media",
                "media": [
                    {"url": "https://picsum.photos/200/300"}  # Random test image
                ],
            }

            url = f"{base_url}/v2/interaction/create-post-with-media"

            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Media post endpoint works!")
                        print(
                            f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                        )
                    else:
                        error = await response.text()
                        print(f"❌ Failed: {error[:200]}")
            except Exception as e:
                print(f"💥 Exception: {e}")

            # Test reply-post-with-media
            print("\n" + "=" * 60)
            print("Testing: Reply with Media")
            print("-" * 60)

            payload = {
                "authToken": auth_token,
                "text": "Test reply with media",
                "tweetId": test_tweet_id,
                "media": [{"url": "https://picsum.photos/200/300"}],
            }

            url = f"{base_url}/v2/interaction/reply-post-with-media"

            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Reply with media works!")
                        print(f"Response: {data}")
                    else:
                        error = await response.text()
                        print(f"❌ Failed: {error[:200]}")
            except Exception as e:
                print(f"💥 Exception: {e}")

            # Test add-to-list
            print("\n" + "=" * 60)
            print("Testing: Add User to List")
            print("-" * 60)

            payload = {
                "authToken": auth_token,
                "listId": "1433448123142115329",  # The list we tested earlier
                "userId": bot_id,  # Add the bot to a list
            }

            url = f"{base_url}/v2/interaction/add-to-list"

            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Add to list works!")
                        print(f"Response: {data}")
                    else:
                        error = await response.text()
                        print(f"❌ Failed: {error[:200]}")
            except Exception as e:
                print(f"💥 Exception: {e}")

            # Test remove-from-list
            print("\n" + "=" * 60)
            print("Testing: Remove User from List")
            print("-" * 60)

            payload = {
                "authToken": auth_token,
                "listId": "1433448123142115329",
                "userId": bot_id,  # Remove the bot from the list
            }

            url = f"{base_url}/v2/interaction/remove-from-list"

            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Remove from list works!")
                        print(f"Response: {data}")
                    else:
                        error = await response.text()
                        print(f"❌ Failed: {error[:200]}")
            except Exception as e:
                print(f"💥 Exception: {e}")

        print("\n" + "█" * 60)
        print("BOT NETWORK ANALYSIS")
        print("█" * 60)

        # Get bot's followers to see if they're other bots
        data = await test_endpoint(
            session,
            "/v2/user/followers-list",
            {"userId": bot_id, "count": 50},
            "Get 50 Bot Followers for Analysis",
        )

        if data and "users" in data:
            print(f"\n🤖 Analyzing {len(data['users'])} followers of @{bot_user}:")
            for user in data["users"][:10]:
                if isinstance(user, dict):
                    username = user.get("legacy", {}).get("screen_name", "unknown")
                    created = user.get("legacy", {}).get("created_at", "")
                    print(f"  @{username} - Created: {created}")


if __name__ == "__main__":
    asyncio.run(main())

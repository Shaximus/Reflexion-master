import asyncio
import json
from ryan_api_hotreload import RyanTwitterAPISecure as RyanTwitterAPI


async def test_post():
    api = RyanTwitterAPI()

    # Test with a simple message
    test_messages = [
        "Test post 1",  # Very simple
        "@Ironshax1 Test mention",  # With mention
        "@Ironshax1 ⚡ Test with emoji",  # With emoji
        "@Ironshax1 " + "x" * 250,  # Long message
    ]

    for i, msg in enumerate(test_messages):
        print(f"\nTest {i+1}: {msg[:50]}...")
        result = await api.post_tweet("singularity", msg)

        if result.get("success"):
            print(f"  ✅ Success!")
        else:
            error = result.get("error", "Unknown")
            print(f"  ❌ Failed: {error}")

            # If 400 error, it's likely the content
            if "400" in str(error) or "Status 400" in str(error):
                print(f"  Content length: {len(msg)}")
                print(f"  Has emoji: {'⚡' in msg}")
                print(f"  Has mention: {'@' in msg}")


asyncio.run(test_post())

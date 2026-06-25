# test_ryan_working.py
import requests
import json

headers = {
    "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
    "x-rapidapi-key": "b6b201782cmshb226957f2fdb9b2p1715e9jsn11b8fe9b9c52"
}

print("Testing Ryan's Twitter API...")
print("="*50)

# Step 1: Get user info by username
username = "elonmusk"
url = f"https://twitter-api47.p.rapidapi.com/v2/user/by-username?username={username}"
response = requests.get(url, headers=headers)

print(f"1. Get user by username (@{username}): {response.status_code}")
if response.status_code == 200:
    user_data = response.json()
    print(f"   Success! User data received")
    print(f"   Sample: {json.dumps(user_data, indent=2)[:300]}...")
    
    # Extract user ID for next call
    user_id = user_data.get('id') or user_data.get('rest_id') or user_data.get('data', {}).get('id')
    
    if user_id:
        print(f"   User ID: {user_id}")
        
        # Step 2: Get tweets and replies using the user ID
        url2 = f"https://twitter-api47.p.rapidapi.com/v2/user/tweets-and-replies?userId={user_id}"
        response2 = requests.get(url2, headers=headers)
        
        print(f"\n2. Get tweets and replies: {response2.status_code}")
        if response2.status_code == 200:
            tweets_data = response2.json()
            print(f"   Success! Tweets received")
            print(f"   Sample: {json.dumps(tweets_data, indent=2)[:300]}...")
else:
    print(f"   Error: {response.text[:200]}")

print("\n" + "="*50)
print("Test complete!")

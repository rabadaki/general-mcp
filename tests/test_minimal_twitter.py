#!/usr/bin/env python3
import asyncio
import httpx
import json
import os

# Set environment variable
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

async def test_minimal_twitter_payload():
    print("=== Testing Minimal Twitter User Tweets Payload ===")
    
    apify_token = os.environ.get('APIFY_TOKEN')
    # Correct actor ID from the URL you provided
    url = "https://api.apify.com/v2/acts/61RPP7dywgiy0JPD0/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {apify_token}"}
    
    # MINIMAL payload - only essentials
    minimal_payload = {
        "twitterHandles": ["elonmusk"],
        "maxItems": 5,
        "sort": "Latest",
        "customMapFunction": "(object) => { return {...object} }"
    }
    
    print(f"Using minimal payload: {json.dumps(minimal_payload, indent=2)}")
    
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=minimal_payload, headers=headers)
            
            print(f"Status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 201:
                items = response.json()
                print(f"Got {len(items)} items")
                
                for i, item in enumerate(items[:2]):  # Show first 2 items
                    print(f"\n--- Item {i} ---")
                    print(f"Type: {item.get('type', 'unknown')}")
                    
                    if 'text' in item:
                        print(f"Tweet text: {item['text'][:100]}...")
                        print(f"Author: {item.get('author', {}).get('userName', 'unknown')}")
                        print(f"Likes: {item.get('likeCount', 0)}")
                        print(f"Retweets: {item.get('retweetCount', 0)}")
                        print(f"Created: {item.get('createdAt', 'unknown')}")
                    elif 'userName' in item:
                        print(f"User profile: {item['userName']}")
                        print(f"Followers: {item.get('followersCount', 0)}")
                    else:
                        print(f"Unknown item structure: {list(item.keys())}")
            else:
                print(f"Error response: {response.text}")
                
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_minimal_twitter_payload()) 
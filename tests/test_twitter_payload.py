#!/usr/bin/env python3
import asyncio
import httpx
import json
import os

# Set environment variable
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

async def test_exact_payload():
    print("=== Testing Exact User Payload ===")
    
    apify_token = os.environ.get('APIFY_TOKEN')
    url = "https://api.apify.com/v2/acts/V38PZzpEgOfeeWvZY/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {apify_token}"}
    
    # Exact payload from user
    payload = {
        "customMapFunction": "(object) => { return {...object} }",
        "getFollowers": True,
        "getFollowing": True,
        "getRetweeters": True,
        "includeUnavailableUsers": False,
        "maxItems": 5,
        "startUrls": [
            "https://twitter.com"
        ],
        "twitterHandles": [
            "elonmusk"
        ]
    }
    
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"\nStatus Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 201:
                data = response.json()
                print(f"\nSuccess! Got {len(data)} items")
                
                # Analyze each item
                for i, item in enumerate(data):
                    print(f"\n--- ITEM {i} ---")
                    print(f"Type: {type(item)}")
                    
                    if isinstance(item, dict):
                        # Show key fields to understand structure
                        important_keys = ['userName', 'name', 'followers', 'following', 'text', 'likeCount', 'retweetCount']
                        for key in important_keys:
                            if key in item:
                                print(f"{key}: {item[key]}")
                        
                        # Show all keys to understand structure
                        print(f"All keys: {list(item.keys())}")
                        
                        # Check if it's a user profile or tweet
                        if 'userName' in item and 'followers' in item:
                            print("-> Looks like USER PROFILE")
                        elif 'text' in item and 'likeCount' in item:
                            print("-> Looks like TWEET")
                        else:
                            print("-> Unknown type")
                    
                    # Show first few items in detail
                    if i < 2:
                        print(f"Full item {i}: {json.dumps(item, indent=2)}")
                        
            else:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text[:1000]}")
                
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_exact_payload()) 
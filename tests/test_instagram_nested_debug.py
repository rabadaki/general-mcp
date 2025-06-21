#!/usr/bin/env python3
import asyncio
import httpx
import json
import os

# Set environment variable
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

async def test_instagram_nested_structure():
    print("=== Testing Instagram Nested Results Structure ===")
    
    apify_token = os.environ.get('APIFY_TOKEN')
    url = "https://api.apify.com/v2/acts/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {apify_token}"}
    
    # Current payload
    payload = {
        "search": "travel",
        "searchType": "hashtag",
        "resultsType": "posts",
        "resultsLimit": 5,
        "searchLimit": 1,
        "addParentData": False
    }
    
    print(f"Testing actor: shu8hvrXbJbY3Eb9W")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Increase timeout since actor takes longer
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 201:
                items = response.json()
                print(f"Response type: {type(items)}")
                print(f"Items count: {len(items) if isinstance(items, list) else 'Not a list'}")
                
                if items and isinstance(items, list):
                    print(f"\n=== EXAMINING FIRST ITEM STRUCTURE ===")
                    first_item = items[0]
                    print(f"First item type: {type(first_item)}")
                    print(f"First item keys: {list(first_item.keys())}")
                    
                    # Check for nested posts
                    if 'topPosts' in first_item:
                        print(f"\n✅ Found 'topPosts' with {len(first_item['topPosts'])} posts")
                        
                        for i, post in enumerate(first_item['topPosts'][:2]):
                            print(f"\n--- Post {i+1} Structure ---")
                            print(f"Post keys: {list(post.keys())}")
                            print(f"Sample post data:")
                            for key, value in post.items():
                                if isinstance(value, str):
                                    print(f"  {key}: {value[:100]}..." if len(str(value)) > 100 else f"  {key}: {value}")
                                else:
                                    print(f"  {key}: {value}")
                                
                    elif 'posts' in first_item:
                        print(f"\n✅ Found 'posts' with {len(first_item['posts'])} posts")
                        posts = first_item['posts'][:2]
                        for i, post in enumerate(posts):
                            print(f"\n--- Post {i+1} ---")
                            print(f"Post keys: {list(post.keys())}")
                    
                    else:
                        print(f"\n🔍 Looking for other nested structures...")
                        for key, value in first_item.items():
                            if isinstance(value, list) and value:
                                print(f"  Found list '{key}' with {len(value)} items")
                                if isinstance(value[0], dict):
                                    print(f"    Sample item keys: {list(value[0].keys())}")
                    
                    print(f"\n=== FULL FIRST ITEM (truncated) ===")
                    print(json.dumps(first_item, indent=2)[:1000] + "...")
                    
                else:
                    print("Empty or invalid response")
            else:
                print(f"Error response: {response.text}")
                
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_instagram_nested_structure()) 
#!/usr/bin/env python3
import asyncio
import httpx
import json
import os

# Set environment variable
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

async def test_current_instagram_actor():
    print("=== Testing Current Instagram Actor ===")
    
    apify_token = os.environ.get('APIFY_TOKEN')
    # Current actor from server.py
    url = "https://api.apify.com/v2/acts/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {apify_token}"}
    
    # Current payload from server.py
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
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 201:
                items = response.json()
                print(f"Response type: {type(items)}")
                print(f"Items count: {len(items) if isinstance(items, list) else 'Not a list'}")
                
                if items:
                    print(f"First item keys: {list(items[0].keys()) if isinstance(items, list) else 'N/A'}")
                    print(f"First item sample: {json.dumps(items[0], indent=2)[:500] if isinstance(items, list) else 'N/A'}...")
                else:
                    print("Empty response")
            else:
                print(f"Error response: {response.text}")
                
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

async def test_alternative_instagram_actors():
    print("\n=== Testing Alternative Instagram Actors ===")
    
    apify_token = os.environ.get('APIFY_TOKEN')
    headers = {"Authorization": f"Bearer {apify_token}"}
    
    # Try different actors from test_fix.py
    actors = [
        "apify~instagram-scraper",
        "apify~instagram-hashtag-scraper", 
        "zuzka~instagram-scraper"
    ]
    
    for actor in actors:
        print(f"\n--- Testing {actor} ---")
        url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
        
        # Try different payload formats
        payloads = [
            {"hashtags": ["travel"], "resultsLimit": 3},
            {"search": "travel", "hashtag": "travel", "limit": 3},
            {"hashtag": "#travel", "maxItems": 3}
        ]
        
        for i, payload in enumerate(payloads):
            print(f"  Payload {i+1}: {payload}")
            try:
                timeout = httpx.Timeout(10.0, connect=3.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    print(f"  Status: {response.status_code}")
                    
                    if response.status_code == 201:
                        items = response.json()
                        print(f"  ✅ Success: {len(items) if isinstance(items, list) else 'Not list'} items")
                        if items and isinstance(items, list):
                            print(f"  Sample keys: {list(items[0].keys())[:5]}")
                        break
                    else:
                        print(f"  ❌ Error: {response.text[:100]}")
            except Exception as e:
                print(f"  ❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_current_instagram_actor())
    asyncio.run(test_alternative_instagram_actors()) 
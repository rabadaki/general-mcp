import asyncio
import json
import os
import sys
sys.path.append('/Users/Amos/general-mcp')

async def test_direct():
    try:
        # Test the exact payload format
        import httpx
        
        APIFY_TOKEN = os.environ.get('APIFY_TOKEN')
        if not APIFY_TOKEN:
            print("❌ No APIFY_TOKEN found")
            return
            
        APIFY_API_BASE = "https://api.apify.com/v2/acts"
        
        payload = {
            "excludePinnedPosts": False,
            "profiles": ["mrbeast"],
            "resultsPerPage": 3,
            "shouldDownloadCovers": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadVideos": False,
            "profileScrapeSections": ["videos"],
            "profileSorting": "latest",
            "searchSection": "",
            "maxProfilesPerQuery": 10
        }
        
        print(f"Sending payload: {json.dumps(payload, indent=2)}")
        
        url = f"{APIFY_API_BASE}/clockworks/tiktok-scraper/run-sync-get-dataset-items"
        params = {"token": APIFY_TOKEN}
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, params=params)
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            
            if response.status_code == 201:
                data = response.json()
                print(f"Success! Got {len(data) if data else 0} items")
                if data:
                    print(f"First item keys: {list(data[0].keys()) if data[0] else 'empty'}")
            else:
                print(f"Failed with status {response.status_code}")
                
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct()) 
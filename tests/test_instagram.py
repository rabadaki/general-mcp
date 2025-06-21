import urllib.request
import urllib.parse
import json

# Your Apify token
APIFY_TOKEN = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'
ACTOR_ID = 'shu8hvrXbJbY3Eb9W'

# Test different payload structures
test_payloads = [
    {
        "name": "Search by hashtag",
        "payload": {
            "search": "travel",
            "searchType": "hashtag",
            "resultsLimit": 5
        }
    },
    {
        "name": "Get user profile",
        "payload": {
            "directUrls": ["https://www.instagram.com/natgeo/"],
            "resultsType": "details",
            "resultsLimit": 1
        }
    },
    {
        "name": "Search posts",
        "payload": {
            "search": ["travel"],
            "searchType": "hashtag",
            "resultsType": "posts",
            "resultsLimit": 5
        }
    }
]

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

for test in test_payloads:
    print(f"\n{'=' * 60}")
    print(f"Testing: {test['name']}")
    print(f"Payload: {json.dumps(test['payload'], indent=2)}")
    print("=" * 60)
    
    # Create request
    data = json.dumps(test['payload']).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                data = json.loads(response.read().decode('utf-8'))
                print(f"✅ Success! Got {len(data)} results")
                
                if data and len(data) > 0:
                    # Show first result structure
                    first = data[0]
                    print(f"\nFirst result keys: {list(first.keys())[:10]}...")
                    
                    # Try to extract relevant info based on result type
                    if 'username' in first:
                        print(f"Username: @{first.get('username')}")
                    if 'fullName' in first:
                        print(f"Full name: {first.get('fullName')}")
                    if 'caption' in first:
                        print(f"Caption: {first.get('caption', '')[:100]}...")
                    if 'likesCount' in first:
                        print(f"Likes: {first.get('likesCount'):,}")
                    if 'url' in first:
                        print(f"URL: {first.get('url')}")
            else:
                print(f"❌ Unexpected status: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"❌ Error: {e.code}")
        error_body = e.read().decode('utf-8')
        try:
            error_data = json.loads(error_body)
            print(f"Error message: {error_data.get('error', {}).get('message', 'Unknown error')}")
        except:
            print(error_body[:300]) 
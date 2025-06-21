import sys
import os
import requests
import json

# Set the API key directly
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

APIFY_TOKEN = os.environ['APIFY_TOKEN']
ACTOR_ID = '61RPP7dywgiy0JPD0'

# Test different payload structures to see what works
test_payloads = [
    {
        "name": "Search by from: operator",
        "payload": {
            "searchTerms": ["from:elonmusk"],
            "sort": "Latest",
            "maxItems": 5,
            "tweetLanguage": "en"
        }
    },
    {
        "name": "Using twitterHandles",
        "payload": {
            "twitterHandles": ["elonmusk"],
            "sort": "Latest",
            "maxItems": 5,
            "tweetLanguage": "en"
        }
    },
    {
        "name": "Using handles",
        "payload": {
            "handles": ["elonmusk"],
            "sort": "Latest",
            "maxItems": 5,
            "tweetLanguage": "en"
        }
    }
]

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
params = {"token": APIFY_TOKEN}

for test in test_payloads:
    print(f"\n{'=' * 60}")
    print(f"Testing: {test['name']}")
    print(f"Payload: {json.dumps(test['payload'], indent=2)}")
    print("=" * 60)
    
    response = requests.post(url, params=params, json=test['payload'])
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 201:
        data = response.json()
        if data and len(data) > 0:
            print(f"✅ Success! Got {len(data)} results")
            print(f"First result type: {data[0].get('type', 'unknown')}")
            if data[0].get('type') == 'tweet':
                author = data[0].get('author', {})
                print(f"Author: @{author.get('userName', 'unknown')}")
                print(f"Text preview: {data[0].get('text', '')[:100]}...")
        else:
            print("❌ No results returned")
    else:
        print(f"❌ Error: {response.text[:200]}") 
import urllib.request
import urllib.parse
import json

# Your Apify token
APIFY_TOKEN = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'
ACTOR_ID = 'shu8hvrXbJbY3Eb9W'

# Test Instagram hashtag search
payload = {
    "search": "travel",
    "searchType": "hashtag",
    "resultsType": "posts",
    "resultsLimit": 3,
    "searchLimit": 1,
    "addParentData": False
}

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print("Testing Instagram search for #travel (debug mode)...")
print("=" * 60)

# Create request
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            data = json.loads(response.read().decode('utf-8'))
            print(f"\n✅ Success! Got {len(data)} results\n")
            
            if data and len(data) > 0:
                # Print all keys from first result
                first = data[0]
                print("Keys in first result:")
                for key in sorted(first.keys()):
                    value = first[key]
                    if isinstance(value, str) and len(value) > 100:
                        print(f"  {key}: {value[:100]}...")
                    elif isinstance(value, list):
                        print(f"  {key}: [list with {len(value)} items]")
                    elif isinstance(value, dict):
                        print(f"  {key}: [dict with {len(value)} keys]")
                    else:
                        print(f"  {key}: {value}")
                
                # Print raw JSON for first result
                print("\n\nRaw JSON (pretty printed):")
                print(json.dumps(first, indent=2)[:1000] + "...")
        else:
            print(f"❌ Unexpected status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    error_body = e.read().decode('utf-8')
    print(error_body[:500]) 
import urllib.request
import urllib.parse
import json

# Your Apify token
APIFY_TOKEN = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'
ACTOR_ID = 'clockworks~free-tiktok-scraper'

# Test TikTok search
payload = {
    "searchQueries": ["artificial intelligence"],
    "resultsPerQuery": 5
}

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print("Testing TikTok search for 'artificial intelligence'...")
print("=" * 60)

# Create request
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            data = json.loads(response.read().decode('utf-8'))
            print(f"\n✅ Success! Got {len(data)} results\n")
            
            for i, video in enumerate(data[:5], 1):
                print(f"Video {i}:")
                author_meta = video.get('authorMeta', {})
                print(f"  Author: @{author_meta.get('name', 'unknown')}")
                print(f"  Text: {video.get('text', '')[:100]}...")
                print(f"  Views: {video.get('playCount', 0):,}")
                print(f"  Likes: {video.get('diggCount', 0):,}")
                print(f"  URL: {video.get('webVideoUrl', '')}")
                print()
        else:
            print(f"❌ Unexpected status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    error_body = e.read().decode('utf-8')
    print(error_body[:500])
    
    # Try to parse error for more info
    try:
        error_data = json.loads(error_body)
        if 'error' in error_data:
            print(f"\nError message: {error_data['error'].get('message', 'Unknown error')}")
    except:
        pass 
import urllib.request
import urllib.parse
import json

# Your Apify token
APIFY_TOKEN = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'
ACTOR_ID = 'clockworks~free-tiktok-scraper'

# Test getting user videos
payload = {
    "profiles": ["https://www.tiktok.com/@cbsnews"],
    "resultsPerQuery": 5
}

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print("Testing TikTok user videos for @cbsnews...")
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
                print(f"  Text: {video.get('text', '')[:100]}...")
                print(f"  Views: {video.get('playCount', 0):,}")
                print(f"  Likes: {video.get('diggCount', 0):,}")
                print(f"  Created: {video.get('createTime', 'Unknown')}")
                print(f"  URL: {video.get('webVideoUrl', '')}")
                print()
        else:
            print(f"❌ Unexpected status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    error_body = e.read().decode('utf-8')
    print(error_body[:500]) 
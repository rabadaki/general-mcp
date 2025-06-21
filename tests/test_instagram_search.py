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
    "resultsLimit": 5,
    "searchLimit": 1,
    "addParentData": False
}

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print("Testing Instagram search for #travel...")
print("=" * 60)

# Create request
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            data = json.loads(response.read().decode('utf-8'))
            print(f"\n✅ Success! Got {len(data)} results\n")
            
            for i, post in enumerate(data[:5], 1):
                print(f"Post {i}:")
                print(f"  Username: @{post.get('ownerUsername', 'unknown')}")
                print(f"  Type: {post.get('type', 'unknown')}")
                print(f"  Caption: {post.get('caption', '')[:100]}...")
                print(f"  Likes: {post.get('likesCount', 0):,}")
                print(f"  Comments: {post.get('commentsCount', 0):,}")
                print(f"  URL: {post.get('url', '')}")
                print()
        else:
            print(f"❌ Unexpected status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    error_body = e.read().decode('utf-8')
    print(error_body[:500]) 
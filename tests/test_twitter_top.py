import urllib.request
import urllib.parse
import json

# Your Apify token
APIFY_TOKEN = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'
ACTOR_ID = '61RPP7dywgiy0JPD0'

# Test with Top sort
payload = {
    "searchTerms": ["OpenAI"],
    "sort": "Top",
    "maxItems": 5,
    "tweetLanguage": "en"
}

url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print("Testing Twitter search for 'OpenAI' sorted by Top...")
print("=" * 60)
print(f"Payload: {json.dumps(payload, indent=2)}")
print("=" * 60)

# Create request
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            data = json.loads(response.read().decode('utf-8'))
            print(f"\n✅ Success! Got {len(data)} results\n")
            
            for i, tweet in enumerate(data[:5], 1):
                if tweet.get('type') == 'tweet':
                    author = tweet.get('author', {})
                    print(f"Tweet {i}:")
                    print(f"  Author: @{author.get('userName', 'unknown')}")
                    print(f"  Text: {tweet.get('text', '')[:150]}...")
                    print(f"  Likes: {tweet.get('likeCount', 0):,}")
                    print(f"  Retweets: {tweet.get('retweetCount', 0):,}")
                    print(f"  URL: {tweet.get('url', '')}")
                    print()
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    print(e.read().decode('utf-8')) 
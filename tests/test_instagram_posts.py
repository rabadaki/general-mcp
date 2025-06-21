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

print("Testing Instagram search for #travel (examining posts)...")
print("=" * 60)

# Create request
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            data = json.loads(response.read().decode('utf-8'))
            
            if data and len(data) > 0:
                hashtag_data = data[0]
                
                # Check if we have posts
                if 'topPosts' in hashtag_data:
                    posts = hashtag_data['topPosts'][:5]
                    print(f"\n✅ Found {len(posts)} top posts for #travel\n")
                    
                    for i, post in enumerate(posts, 1):
                        print(f"Post {i}:")
                        print(f"  Keys: {list(post.keys())}")
                        
                        # Try different possible field names
                        username = post.get('ownerUsername') or post.get('username') or post.get('owner', {}).get('username', 'unknown')
                        caption = post.get('caption') or post.get('text', '')
                        likes = post.get('likesCount') or post.get('likes') or post.get('edge_liked_by', {}).get('count', 0)
                        comments = post.get('commentsCount') or post.get('comments') or post.get('edge_media_to_comment', {}).get('count', 0)
                        post_type = post.get('type') or ('Video' if post.get('is_video') else 'Image')
                        url = post.get('url') or f"https://www.instagram.com/p/{post.get('shortcode', '')}/"
                        
                        print(f"  Username: @{username}")
                        print(f"  Type: {post_type}")
                        print(f"  Caption: {str(caption)[:100]}...")
                        print(f"  Likes: {likes:,}")
                        print(f"  Comments: {comments:,}")
                        print(f"  URL: {url}")
                        print()
                else:
                    print("❌ No posts found in response")
                    print(f"Available keys: {list(hashtag_data.keys())}")
        else:
            print(f"❌ Unexpected status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"❌ Error: {e.code}")
    error_body = e.read().decode('utf-8')
    print(error_body[:500]) 
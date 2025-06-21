#!/usr/bin/env python3
import asyncio
import httpx
import sys
import re
sys.path.append('.')

async def test_reddit_comments():
    """Test Reddit comments API with proper URL format"""
    print("=== Testing Reddit Comments API ===")
    
    # Example URL: https://www.reddit.com/r/technology/comments/1h123j4/sam_altman_openai/
    test_url = "https://www.reddit.com/r/technology/comments/1h123j4/sam_altman_openai/"
    
    # Extract subreddit and post ID from URL
    url_pattern = r'reddit\.com/r/([^/]+)/comments/([^/]+)'
    match = re.search(url_pattern, test_url)
    
    if match:
        subreddit = match.group(1)
        post_id = match.group(2)
        
        # Correct JSON API URL format  
        json_url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        print(f"Corrected URL: {json_url}")
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(json_url)
                if response.status_code == 200:
                    data = response.json()
                    if len(data) >= 2:
                        comments = data[1]['data']['children']
                        print(f"✅ Found {len(comments)} comments")
                        for i, comment in enumerate(comments[:3]):
                            if comment['kind'] == 't1':
                                print(f"  Comment {i+1}: {comment['data']['body'][:100]}...")
                    else:
                        print("❌ Unexpected JSON structure")
                else:
                    print(f"❌ HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("❌ Could not parse URL")

async def test_twitter_user():
    """Test Twitter user timeline with proper Apify endpoint"""
    print("\n=== Testing Twitter User Timeline API ===")
    
    # From Perplexity: use powerai~twitter-timeline-scraper
    apify_token = "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"
    
    payload = {
        "username": "elonmusk",
        "count": 5,
        "includeRetweets": False,
        "includeReplies": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.apify.com/v2/acts/powerai~twitter-timeline-scraper/run-sync-get-dataset-items?token={apify_token}",
                json=payload
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Got {len(data)} tweets")
                for tweet in data[:2]:
                    print(f"  Tweet: {tweet.get('text', 'N/A')[:100]}...")
            else:
                print(f"❌ Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_instagram_hashtag():
    """Test Instagram hashtag search with updated approach"""
    print("\n=== Testing Instagram Hashtag Search ===")
    
    # Try different Apify Instagram scrapers
    apify_token = "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"
    
    scrapers = [
        "apify~instagram-scraper",
        "apify~instagram-hashtag-scraper", 
        "zuzka~instagram-scraper"
    ]
    
    for scraper in scrapers:
        print(f"Trying {scraper}...")
        payload = {
            "hashtags": ["travel"],
            "resultsLimit": 5
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://api.apify.com/v2/acts/{scraper}/run-sync-get-dataset-items?token={apify_token}",
                    json=payload
                )
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ Got {len(data)} posts")
                    break
                else:
                    print(f"  ❌ Error: {response.text[:100]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

async def main():
    await test_reddit_comments()
    await test_twitter_user()  
    await test_instagram_hashtag()

if __name__ == "__main__":
    asyncio.run(main()) 
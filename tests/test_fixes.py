#!/usr/bin/env python3
import asyncio
import sys
import json
import os
sys.path.append('.')

# Set environment variable
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

from server import get_reddit_comments, get_user_tweets, search_instagram

async def test_reddit_comments():
    """Test the fixed Reddit comments function"""
    print("=== Testing Fixed Reddit Comments ===")
    
    test_url = "https://www.reddit.com/r/technology/comments/1h123j4/sam_altman_openai/"
    result = await get_reddit_comments(test_url, 3)
    
    try:
        data = json.loads(result)
        if data.get("success"):
            print(f"✅ SUCCESS: Found {data.get('count', 0)} comments")
            for i, comment in enumerate(data.get('comments', [])[:2]):
                print(f"   Comment {i+1}: @{comment.get('author')} (score: {comment.get('score')})")
                print(f"   Body: {comment.get('body', '')[:100]}...")
        else:
            print(f"❌ FAILED: {data.get('error')}")
    except Exception as e:
        print(f"❌ PARSE ERROR: {e}")
        print(f"Raw result: {result[:200]}...")

async def test_user_tweets():
    """Test Twitter user tweets"""
    print("\n=== Testing Twitter User Tweets ===")
    
    result = await get_user_tweets("elonmusk", 3)
    
    try:
        data = json.loads(result)
        if data.get("success"):
            print(f"✅ SUCCESS: Found {data.get('count', 0)} tweets")
            for i, tweet in enumerate(data.get('tweets', [])[:2]):
                print(f"   Tweet {i+1}: {tweet.get('text', '')[:100]}...")
        else:
            print(f"❌ FAILED: {data.get('error')}")
    except Exception as e:
        print(f"❌ PARSE ERROR: {e}")
        print(f"Raw result: {result[:200]}...")

async def test_instagram_search():
    """Test Instagram search"""
    print("\n=== Testing Instagram Search ===")
    
    result = await search_instagram("travel", 3)
    
    try:
        data = json.loads(result)
        if data.get("success"):
            print(f"✅ SUCCESS: Found {data.get('count', 0)} posts")
            for i, post in enumerate(data.get('posts', [])[:2]):
                print(f"   Post {i+1}: @{post.get('author')} - {post.get('caption', '')[:50]}...")
        else:
            print(f"❌ FAILED: {data.get('error')}")
    except Exception as e:
        print(f"❌ PARSE ERROR: {e}")
        print(f"Raw result: {result[:200]}...")

async def main():
    print("Testing fixes for problematic tools...\n")
    
    await test_reddit_comments()
    await test_user_tweets()
    await test_instagram_search()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main()) 
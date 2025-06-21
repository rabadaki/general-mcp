#!/usr/bin/env python3
"""Test the newly implemented Twitter tools with Apify."""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_stdio_server import search_twitter, get_user_tweets

async def test_twitter_tools():
    """Test Twitter search and user tweets functions."""
    print("🐦 TESTING TWITTER TOOLS WITH APIFY")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print(f"APIFY_API_TOKEN configured: {'Yes' if os.getenv('APIFY_API_TOKEN') else 'No'}")
    
    # Test 1: Search Twitter
    print("\n\n1️⃣ Testing search_twitter()")
    print("-" * 40)
    try:
        print("Searching for 'AI news'...")
        result = await search_twitter("AI news", sort="Top", max_results=3)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Search with Latest sort
    print("\n\n2️⃣ Testing search_twitter() with Latest sort")
    print("-" * 40)
    try:
        print("Searching for 'OpenAI' (Latest)...")
        result = await search_twitter("OpenAI", sort="Latest", max_results=2)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Get user tweets
    print("\n\n3️⃣ Testing get_user_tweets()")
    print("-" * 40)
    try:
        print("Getting tweets from @elonmusk...")
        result = await get_user_tweets("elonmusk", include_replies=False, max_results=3)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Get user tweets with replies
    print("\n\n4️⃣ Testing get_user_tweets() with replies")
    print("-" * 40)
    try:
        print("Getting tweets from @OpenAI (including replies)...")
        result = await get_user_tweets("OpenAI", include_replies=True, max_results=2)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n\n✅ Twitter tools testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_twitter_tools()) 
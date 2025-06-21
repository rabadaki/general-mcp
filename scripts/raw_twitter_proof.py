#!/usr/bin/env python3
"""Show RAW Twitter data from Apify - no bullshit formatting."""

import asyncio
import json
from datetime import datetime
from apify_client import ApifyClient

APIFY_API_TOKEN = "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"
TWITTER_ACTOR_ID = '61RPP7dywgiy0JPD0'

async def show_raw_twitter_data():
    print("RAW TWITTER DATA TEST - NO FORMATTING")
    print("=" * 60)
    
    # Let user choose what to search
    search_term = input("\nEnter what you want to search on Twitter (or press Enter for 'Elon Musk'): ")
    if not search_term:
        search_term = "Elon Musk"
    
    print(f"\nSearching Twitter for: '{search_term}'")
    print("This will show you the EXACT raw data from Apify...\n")
    
    # Initialize Apify client
    apify_client = ApifyClient(APIFY_API_TOKEN)
    
    # Prepare input
    actor_input = {
        "searchTerms": [search_term],
        "sort": "Latest",
        "maxItems": 3,
        "tweetLanguage": "en",
    }
    
    try:
        print("🔄 Calling Apify actor...")
        # Run the actor
        run = apify_client.actor(TWITTER_ACTOR_ID).call(run_input=actor_input, timeout_secs=30)
        
        print(f"✅ Actor run completed. Run ID: {run.get('id')}")
        print(f"✅ Dataset ID: {run.get('defaultDatasetId')}")
        
        # Get raw results
        dataset_items = apify_client.dataset(run["defaultDatasetId"]).list_items()
        items = dataset_items.items if hasattr(dataset_items, 'items') else []
        
        print(f"\n📊 Found {len(items)} tweets")
        print("\n" + "="*60)
        print("RAW DATA (First tweet only, to save space):")
        print("="*60)
        
        if items:
            # Show raw JSON of first tweet
            first_tweet = items[0]
            print(json.dumps(first_tweet, indent=2, default=str))
            
            print("\n" + "="*60)
            print("EXTRACTED KEY FIELDS FROM ALL TWEETS:")
            print("="*60)
            
            for i, tweet in enumerate(items, 1):
                print(f"\nTweet #{i}:")
                print(f"  Text: {tweet.get('text', 'N/A')[:100]}...")
                print(f"  Author: @{tweet.get('author', {}).get('username', 'N/A')}")
                print(f"  Likes: {tweet.get('likeCount', 0)}")
                print(f"  Created: {tweet.get('createdAt', 'N/A')}")
                print(f"  URL: {tweet.get('url', 'N/A')}")
                
                # This is the proof - real Twitter URLs
                url = tweet.get('url', '')
                if url:
                    print(f"\n  👆 CLICK THIS URL TO VERIFY IT'S REAL: {url}")
        else:
            print("No tweets found!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("This might be because:")
        print("- Apify API token is invalid")
        print("- Actor is down")
        print("- Network issue")

if __name__ == "__main__":
    asyncio.run(show_raw_twitter_data()) 
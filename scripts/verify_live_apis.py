#!/usr/bin/env python3
"""Verify that APIs are returning real, live data - not demo/fake responses."""

import asyncio
import sys
import os
from datetime import datetime
import random
import string

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_stdio_server import (
    search_reddit, search_youtube, search_perplexity,
    search_google_trends, compare_google_trends
)

def generate_unique_query():
    """Generate a unique query string that couldn't be pre-cached."""
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"test_{timestamp}_{random_suffix}"

async def verify_reddit():
    """Verify Reddit returns real results."""
    print("\n🔍 REDDIT VERIFICATION")
    print("="*50)
    
    # Search for something very specific and recent
    query = f"site:reddit.com timestamp:{datetime.now().strftime('%Y-%m-%d')}"
    print(f"Searching Reddit for today's date reference: {query}")
    
    result = await search_reddit(query, limit=2)
    print("\nResult preview:")
    print(result[:500] + "..." if len(result) > 500 else result)
    
    # Also search for a trending topic
    print("\n\nSearching for current trending topic...")
    result2 = await search_reddit("OpenAI", subreddit="technology", sort="new", time="hour", limit=2)
    print(result2[:500] + "..." if len(result2) > 500 else result2)

async def verify_youtube():
    """Verify YouTube returns real, current results."""
    print("\n\n🎥 YOUTUBE VERIFICATION")
    print("="*50)
    
    # Search for videos uploaded today
    today = datetime.now().strftime("%Y-%m-%dT00:00:00Z")
    print(f"Searching for videos uploaded after: {today}")
    
    result = await search_youtube(
        query="news",
        published_after=today,
        order="date",
        limit=2
    )
    print("\nToday's videos:")
    print(result)

async def verify_perplexity():
    """Verify Perplexity returns real-time information."""
    print("\n\n🧠 PERPLEXITY VERIFICATION")
    print("="*50)
    
    # Ask about today's date and current events
    today = datetime.now().strftime("%B %d, %Y")
    query = f"What is happening in technology news today {today}? Give me specific current events."
    print(f"Query: {query}")
    
    result = await search_perplexity(query, max_results=5)
    print("\nPerplexity response:")
    print(result)

async def verify_google_trends():
    """Verify Google Trends with unique comparison."""
    print("\n\n📈 GOOGLE TRENDS VERIFICATION")
    print("="*50)
    
    # Create a unique combination that couldn't be pre-cached
    unique_id = generate_unique_query()
    print(f"Generated unique query: {unique_id}")
    
    # First, search for the unique term (should have no data)
    print(f"\n1. Searching trends for non-existent term: {unique_id}")
    result1 = await search_google_trends(unique_id, timeframe="now 1-H", geo="US")
    print(result1[:300] + "..." if len(result1) > 300 else result1)
    
    # Now search for real current trends
    print("\n2. Searching for real-time trend data (last hour)...")
    result2 = await search_google_trends("breaking news", timeframe="now 1-H", geo="US")
    print(result2)
    
    # Compare with timestamp
    print(f"\n3. Comparing terms with current timestamp...")
    terms = ["Python", "JavaScript", datetime.now().strftime("%Y")]
    result3 = await compare_google_trends(terms, timeframe="now 7-d", geo="US")
    print(result3[:600] + "..." if len(result3) > 600 else result3)

async def main():
    """Run all verifications."""
    print("🔬 LIVE API VERIFICATION TEST")
    print(f"📅 Timestamp: {datetime.now()}")
    print("This test proves we're making real API calls, not returning fake data.\n")
    
    try:
        await verify_reddit()
    except Exception as e:
        print(f"Reddit verification error: {e}")
    
    try:
        await verify_youtube()
    except Exception as e:
        print(f"YouTube verification error: {e}")
    
    try:
        await verify_perplexity()
    except Exception as e:
        print(f"Perplexity verification error: {e}")
    
    try:
        await verify_google_trends()
    except Exception as e:
        print(f"Google Trends verification error: {e}")
    
    print("\n\n✅ Verification complete! Check the results above to confirm:")
    print("1. Reddit shows posts from the last hour")
    print("2. YouTube shows videos uploaded today")
    print("3. Perplexity knows today's date and current events")
    print("4. Google Trends shows real-time data and rejects fake queries")

if __name__ == "__main__":
    asyncio.run(main()) 
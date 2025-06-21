#!/usr/bin/env python3
"""Comprehensive test script for implemented MCP tools."""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the server and functions
from mcp_stdio_server import (
    search_reddit, get_subreddit_posts, get_reddit_comments,
    search_youtube, get_youtube_trending,
    search_perplexity, search_web,
    search_google_trends, compare_google_trends,
    get_api_usage_stats
)

async def test_tool(name: str, func, *args, **kwargs):
    """Test a single tool and display results."""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {name}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        result = await func(*args, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Success! (Duration: {duration:.2f}s)")
        print(f"\n📊 Result Preview (first 1000 chars):")
        print("-" * 40)
        print(result[:1000] + "..." if len(result) > 1000 else result)
        print("-" * 40)
        
        # Check if result contains error indicators
        if "❌" in result:
            print("⚠️  Warning: Result contains error indicators")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("🚀 MCP Tools Comprehensive Test Suite")
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Test 1: Reddit Search
    print("\n\n" + "="*80)
    print("📱 REDDIT TOOLS TESTS")
    print("="*80)
    
    results['reddit_search'] = await test_tool(
        "Reddit Search",
        search_reddit,
        query="python programming",
        limit=5
    )
    
    # Test 2: Subreddit Posts
    results['subreddit_posts'] = await test_tool(
        "Get Subreddit Posts",
        get_subreddit_posts,
        subreddit="python",
        sort="hot",
        limit=3
    )
    
    # Test 3: Reddit Comments
    results['reddit_comments'] = await test_tool(
        "Get Reddit Comments",
        get_reddit_comments,
        post_url="https://www.reddit.com/r/Python/comments/1234567/test_post/",
        limit=5
    )
    
    # Test 4: YouTube Search
    print("\n\n" + "="*80)
    print("🎥 YOUTUBE TOOLS TESTS")
    print("="*80)
    
    results['youtube_search'] = await test_tool(
        "YouTube Search",
        search_youtube,
        query="python tutorial",
        order="viewCount",
        limit=3
    )
    
    # Test 5: YouTube Trending
    results['youtube_trending'] = await test_tool(
        "YouTube Trending",
        get_youtube_trending,
        category="28",  # Science & Technology
        region="US",
        limit=3
    )
    
    # Test 6: Perplexity Search
    print("\n\n" + "="*80)
    print("🧠 AI SEARCH TESTS")
    print("="*80)
    
    results['perplexity_search'] = await test_tool(
        "Perplexity AI Search",
        search_perplexity,
        query="What are the latest developments in AI?",
        max_results=5
    )
    
    # Test 7: Web Search (DuckDuckGo)
    results['web_search'] = await test_tool(
        "DuckDuckGo Web Search",
        search_web,
        query="Python programming best practices",
        max_results=5
    )
    
    # Test 8: Google Trends Search
    print("\n\n" + "="*80)
    print("📈 GOOGLE TRENDS TESTS")
    print("="*80)
    
    results['google_trends'] = await test_tool(
        "Google Trends Analysis",
        search_google_trends,
        query="artificial intelligence",
        timeframe="today 3-m",
        geo="US"
    )
    
    # Test 9: Google Trends Comparison
    results['google_trends_compare'] = await test_tool(
        "Google Trends Comparison",
        compare_google_trends,
        terms=["ChatGPT", "Claude", "Gemini"],
        timeframe="today 12-m",
        geo="US"
    )
    
    # Test 10: API Usage Stats
    print("\n\n" + "="*80)
    print("📊 SYSTEM TESTS")
    print("="*80)
    
    results['api_stats'] = await test_tool(
        "API Usage Statistics",
        get_api_usage_stats
    )
    
    # Summary
    print("\n\n" + "="*80)
    print("📋 TEST SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    failed_tests = total_tests - passed_tests
    
    print(f"\n✅ Passed: {passed_tests}/{total_tests}")
    print(f"❌ Failed: {failed_tests}/{total_tests}")
    print(f"📊 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\n📝 Detailed Results:")
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")
    
    # Test edge cases
    print("\n\n" + "="*80)
    print("🔧 EDGE CASE TESTS")
    print("="*80)
    
    # Test with empty query
    await test_tool(
        "Empty Query Test (YouTube)",
        search_youtube,
        query="",
        limit=1
    )
    
    # Test with very high limit
    await test_tool(
        "High Limit Test (Reddit)",
        search_reddit,
        query="test",
        limit=100  # Should be capped at 50
    )
    
    # Test with invalid parameters
    await test_tool(
        "Invalid Category (YouTube Trending)",
        get_youtube_trending,
        category="999",  # Invalid category
        region="XX",  # Invalid region
        limit=1
    )
    
    print("\n\n✨ Test suite completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
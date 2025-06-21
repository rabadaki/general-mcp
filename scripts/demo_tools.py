#!/usr/bin/env python3
"""Demonstration of all implemented MCP tools with real examples."""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the functions
from mcp_stdio_server import (
    search_reddit, get_subreddit_posts, get_reddit_comments,
    search_youtube, get_youtube_trending,
    search_perplexity, search_web,
    search_google_trends, compare_google_trends,
    get_api_usage_stats
)

async def demo_tool(name: str, func, *args, **kwargs):
    """Demo a single tool."""
    print(f"\n{'='*60}")
    print(f"🎯 Demo: {name}")
    print(f"{'='*60}")
    
    try:
        result = await func(*args, **kwargs)
        print(result)
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

async def main():
    """Run demonstrations."""
    print("🚀 MCP Tools Live Demonstration")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Reddit Search Demo
    print("\n\n" + "="*80)
    print("📱 REDDIT DEMO")
    print("="*80)
    
    await demo_tool(
        "Search Reddit for 'machine learning'",
        search_reddit,
        query="machine learning",
        limit=2
    )
    
    # 2. YouTube Search Demo
    print("\n\n" + "="*80)
    print("🎥 YOUTUBE DEMO")
    print("="*80)
    
    await demo_tool(
        "Search YouTube for 'Claude AI'",
        search_youtube,
        query="Claude AI",
        order="date",
        limit=2
    )
    
    await demo_tool(
        "Get YouTube Trending (Gaming)",
        get_youtube_trending,
        category="20",  # Gaming
        region="US",
        limit=2
    )
    
    # 3. Perplexity AI Demo
    print("\n\n" + "="*80)
    print("🧠 PERPLEXITY AI DEMO")
    print("="*80)
    
    await demo_tool(
        "Ask Perplexity about recent AI developments",
        search_perplexity,
        query="What are the latest developments in AI language models in 2024?",
        max_results=3
    )
    
    # 4. Web Search Demo
    print("\n\n" + "="*80)
    print("🌐 WEB SEARCH DEMO")
    print("="*80)
    
    await demo_tool(
        "Search web for 'Python asyncio'",
        search_web,
        query="Python asyncio tutorial",
        max_results=3
    )
    
    # 5. Google Trends Demo
    print("\n\n" + "="*80)
    print("📈 GOOGLE TRENDS DEMO")
    print("="*80)
    
    await demo_tool(
        "Analyze 'AI' trends",
        search_google_trends,
        query="AI",
        timeframe="today 1-m",
        geo="US"
    )
    
    await demo_tool(
        "Compare AI assistants popularity",
        compare_google_trends,
        terms=["ChatGPT", "Claude AI", "Gemini AI"],
        timeframe="today 3-m",
        geo="US"
    )
    
    # 6. API Stats
    print("\n\n" + "="*80)
    print("📊 FINAL STATISTICS")
    print("="*80)
    
    await demo_tool(
        "API Usage Summary",
        get_api_usage_stats
    )

if __name__ == "__main__":
    asyncio.run(main()) 
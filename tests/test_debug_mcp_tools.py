#!/usr/bin/env python3

import asyncio
import sys
import os
import json

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions from server.py
from server import (
    search_reddit, search_youtube, search_twitter,
    search_instagram, search_perplexity, search_google_trends
)

async def debug_test_tool(tool_name, tool_func, **kwargs):
    """Test a tool with detailed output"""
    print(f"\n{'='*60}")
    print(f"Testing: {tool_name}")
    print(f"Arguments: {kwargs}")
    print(f"{'='*60}")
    
    try:
        result = await tool_func(**kwargs)
        print(f"Raw result type: {type(result)}")
        print(f"Raw result: {result[:500] if isinstance(result, str) else str(result)[:500]}...")
        
        # Try to parse if it's JSON
        try:
            if isinstance(result, str):
                parsed = json.loads(result)
                print(f"\nParsed JSON structure:")
                print(json.dumps(parsed, indent=2)[:500] + "...")
        except:
            pass
            
        return result
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Run debug tests on failing tools"""
    
    # Test 1: Reddit Search (failing)
    await debug_test_tool(
        "search_reddit",
        search_reddit,
        query="python",
        limit=2
    )
    
    # Test 2: YouTube Search (failing)
    await debug_test_tool(
        "search_youtube", 
        search_youtube,
        query="python tutorial",
        limit=2
    )
    
    # Test 3: Twitter Search (failing)
    await debug_test_tool(
        "search_twitter",
        search_twitter,
        query="AI",
        limit=2
    )
    
    # Test 4: Instagram Search (failing)
    await debug_test_tool(
        "search_instagram",
        search_instagram,
        query="tech",
        limit=2
    )
    
    # Test 5: Perplexity Search (failing)
    await debug_test_tool(
        "search_perplexity",
        search_perplexity,
        query="What is machine learning?",
        max_results=2
    )
    
    # Test 6: Google Trends (failing)
    await debug_test_tool(
        "search_google_trends",
        search_google_trends,
        query="AI",
        timeframe="today 12-m",
        geo="US"
    )

if __name__ == "__main__":
    asyncio.run(main()) 
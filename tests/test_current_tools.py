#!/usr/bin/env python3
"""Test current MCP server tools to see which ones actually work"""

import json
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the MCP server
from mcp_stdio_server import MCPServer

async def test_tools():
    """Test all tools in the current MCP server"""
    server = MCPServer()
    
    print("Testing Current MCP Server Tools")
    print("=" * 50)
    
    # Get the list of tools
    print(f"\nTotal tools registered: {len(server.tools)}")
    print("\nTools found:")
    for i, tool in enumerate(server.tools, 1):
        print(f"{i}. {tool['name']}")
    
    print("\n" + "=" * 50)
    print("\nTesting each tool with minimal parameters:")
    
    # Test cases for each tool
    test_cases = {
        "search_reddit": {"query": "test", "limit": 1},
        "get_subreddit_posts": {"subreddit": "python", "limit": 1},
        "get_reddit_comments": {"post_url": "https://reddit.com/test"},
        "search_youtube": {"query": "test", "limit": 1},
        "get_youtube_trending": {"limit": 1},
        "search_twitter": {"query": "test", "limit": 1},
        "get_user_tweets": {"username": "test", "limit": 1},
        "search_tiktok": {"query": "test", "limit": 1},
        "get_tiktok_user_videos": {"username": "test", "limit": 1},
        "search_perplexity": {"query": "test"},
        "search_web": {"query": "test", "max_results": 1},
        "search_google_trends": {"query": "test"},
        "compare_google_trends": {"terms": ["test1", "test2"]},
        "get_api_usage_stats": {}
    }
    
    working = []
    placeholder = []
    broken = []
    
    for tool_name, params in test_cases.items():
        print(f"\nTesting {tool_name}...")
        
        # Create a mock message
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }
        
        try:
            result = await server.handle_message(message)
            
            if "error" in result:
                print(f"  ❌ ERROR: {result['error']['message']}")
                broken.append(tool_name)
            elif "result" in result:
                content = result["result"]["content"][0]["text"]
                
                # Check if it's a placeholder response
                if "request processed" in content.lower() or "note:" in content.lower():
                    print(f"  ⚠️  PLACEHOLDER: Returns mock response")
                    placeholder.append(tool_name)
                elif "no results found" in content or "error" in content.lower():
                    print(f"  ❌ BROKEN: {content[:100]}...")
                    broken.append(tool_name)
                else:
                    print(f"  ✅ WORKING: {content[:100]}...")
                    working.append(tool_name)
                    
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)}")
            broken.append(tool_name)
    
    print("\n" + "=" * 50)
    print("\nSUMMARY:")
    print(f"✅ Working tools: {len(working)}")
    for tool in working:
        print(f"   - {tool}")
    
    print(f"\n⚠️  Placeholder tools (not really working): {len(placeholder)}")
    for tool in placeholder:
        print(f"   - {tool}")
    
    print(f"\n❌ Broken tools: {len(broken)}")
    for tool in broken:
        print(f"   - {tool}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_tools()) 
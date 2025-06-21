#!/usr/bin/env python3
"""Test script to verify which MCP tools are working"""

import json
import subprocess
import sys

def test_mcp_tool(tool_name, params=None):
    """Test a single MCP tool"""
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params or {}
        },
        "id": 1
    }
    
    try:
        # Run the MCP server with the request
        process = subprocess.Popen(
            ["python3", "mcp_stdio_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send request and get response
        stdout, stderr = process.communicate(input=json.dumps(request))
        
        # Parse response
        if stdout:
            for line in stdout.split('\n'):
                if line.strip() and line.startswith('{'):
                    try:
                        response = json.loads(line)
                        if 'result' in response:
                            return True, "Success"
                        elif 'error' in response:
                            return False, f"Error: {response['error'].get('message', 'Unknown error')}"
                    except json.JSONDecodeError:
                        continue
        
        return False, f"No valid response (stderr: {stderr[:100]})"
        
    except Exception as e:
        return False, f"Exception: {str(e)}"

# Test all 14 tools
tools_to_test = [
    ("search_reddit", {"query": "test", "limit": 1}),
    ("get_subreddit_posts", {"subreddit": "python", "limit": 1}),
    ("get_reddit_comments", {"post_id": "test123"}),
    ("search_youtube", {"query": "test", "max_results": 1}),
    ("get_youtube_trending", {"region_code": "US", "max_results": 1}),
    ("search_twitter", {"query": "test", "max_results": 1}),
    ("get_user_tweets", {"username": "test", "max_results": 1}),
    ("search_tiktok", {"query": "test", "count": 1}),
    ("get_tiktok_user_videos", {"username": "test", "count": 1}),
    ("search_perplexity", {"query": "test"}),
    ("search_web", {"query": "test", "max_results": 1}),
    ("search_google_trends", {"query": "test"}),
    ("compare_google_trends", {"queries": ["test1", "test2"]}),
    ("get_api_usage_stats", {})
]

print("Testing MCP Server Tools")
print("=" * 50)

# First, activate venv
import os
venv_python = os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python')
if os.path.exists(venv_python):
    sys.executable = venv_python

working_tools = []
broken_tools = []

for tool_name, params in tools_to_test:
    print(f"\nTesting {tool_name}...", end=" ")
    success, message = test_mcp_tool(tool_name, params)
    
    if success:
        print("✅ WORKING")
        working_tools.append(tool_name)
    else:
        print(f"❌ FAILED - {message}")
        broken_tools.append((tool_name, message))

print("\n" + "=" * 50)
print(f"\nSummary:")
print(f"Working tools: {len(working_tools)}/14")
print(f"Broken tools: {len(broken_tools)}/14")

if working_tools:
    print(f"\n✅ Working: {', '.join(working_tools)}")

if broken_tools:
    print(f"\n❌ Broken:")
    for tool, error in broken_tools:
        print(f"  - {tool}: {error}") 
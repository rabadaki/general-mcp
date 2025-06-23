#!/usr/bin/env python3
"""Test script to verify tools/list request works properly."""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your server URL
AUTH_TOKEN = "mcp_token_-18230977600116918"  # Your auth token

def test_initialize():
    """Test the initialize endpoint."""
    print("1. Testing initialize endpoint...")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "0.1.0"
            }
        }
    }
    
    response = requests.post(f"{BASE_URL}/mcp", json=payload, headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_tools_list():
    """Test the tools/list endpoint."""
    print("\n2. Testing tools/list endpoint...")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    response = requests.post(f"{BASE_URL}/mcp", json=payload, headers=headers)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        tools = data.get("result", {}).get("tools", [])
        print(f"   Tools found: {len(tools)}")
        if tools:
            print("   First few tools:")
            for i, tool in enumerate(tools[:3]):
                print(f"     - {tool['name']}: {tool['description'][:50]}...")
    else:
        print(f"   Error: {response.text}")
    
    return response.status_code == 200

def test_sse_connection():
    """Test SSE connection (should only receive pings)."""
    print("\n3. Testing SSE connection...")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Accept": "text/event-stream"
    }
    
    # Make a quick request to test SSE endpoint
    response = requests.get(f"{BASE_URL}/mcp", headers=headers, stream=True, timeout=2)
    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('Content-Type')}")
    
    # Read first few lines
    lines_read = 0
    for line in response.iter_lines(decode_unicode=True):
        if line and lines_read < 3:
            print(f"   Received: {line}")
            lines_read += 1
        if lines_read >= 3:
            break
            
    response.close()
    return response.status_code == 200

if __name__ == "__main__":
    print("Testing MCP Server...")
    print(f"Server: {BASE_URL}")
    print(f"Token: {AUTH_TOKEN[:20]}...")
    print("-" * 50)
    
    # Run tests
    init_ok = test_initialize()
    tools_ok = test_tools_list()
    sse_ok = test_sse_connection()
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print(f"  ✅ Initialize: {'PASS' if init_ok else 'FAIL'}")
    print(f"  ✅ Tools/List: {'PASS' if tools_ok else 'FAIL'}")
    print(f"  ✅ SSE Stream: {'PASS' if sse_ok else 'FAIL'}")
    
    if init_ok and tools_ok and sse_ok:
        print("\n🎉 All tests passed! The server is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
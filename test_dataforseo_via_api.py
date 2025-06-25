#!/usr/bin/env python3
"""Test DataForSEO endpoints via the deployed API."""

import httpx
import asyncio
import json

async def test_via_api():
    """Test DataForSEO endpoints through our deployed service."""
    
    # First, let's create a simple test by calling the SERP tool
    test_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search",
            "arguments": {
                "query": "test dataforseo access",
                "limit": 1
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://general-mcp-production.up.railway.app/message",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        result = response.json()
        print("SERP Test Response:")
        print(json.dumps(result, indent=2))
        
        # Now test keyword research
        keyword_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "keyword_research",
                "arguments": {
                    "keywords": ["blockchain analytics"]
                }
            }
        }
        
        response2 = await client.post(
            "https://general-mcp-production.up.railway.app/message",
            json=keyword_payload,
            headers={"Content-Type": "application/json"}
        )
        
        result2 = response2.json()
        print("\n\nKeyword Research Test Response:")
        print(json.dumps(result2, indent=2))

if __name__ == "__main__":
    asyncio.run(test_via_api())
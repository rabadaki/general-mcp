#!/usr/bin/env python3
"""Test each DataForSEO endpoint individually with proper error handling."""

import asyncio
import json
import httpx

async def test_endpoint(endpoint_name, payload):
    """Test a single endpoint via our API."""
    test_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": endpoint_name,
            "arguments": payload
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://general-mcp-production.up.railway.app/message",
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            return result
        except Exception as e:
            return {"error": str(e)}

async def main():
    """Test all endpoints systematically."""
    
    tests = [
        {
            "name": "get_ranked_keywords",
            "payload": {"domain": "nansen.ai", "limit": 1},
            "description": "DataForSEO Labs - Ranked Keywords"
        },
        {
            "name": "get_historical_rankings", 
            "payload": {"domain": "nansen.ai"},
            "description": "DataForSEO Labs - Historical Rankings"
        },
        {
            "name": "get_top_pages",
            "payload": {"domain": "nansen.ai", "limit": 1},
            "description": "DataForSEO Labs - Top Pages"
        },
        {
            "name": "search_serp",
            "payload": {"query": "test", "limit": 1},
            "description": "DataForSEO SERP"
        },
        {
            "name": "keyword_research",
            "payload": {"keywords": ["test"]},
            "description": "DataForSEO Keywords"
        },
        {
            "name": "onpage_seo_audit",
            "payload": {"target": "nansen.ai", "max_crawl_pages": 1},
            "description": "DataForSEO OnPage"
        }
    ]
    
    print("🔍 Testing DataForSEO Endpoints Individually...\n")
    
    for test in tests:
        print(f"📋 Testing: {test['description']}")
        print(f"   Tool: {test['name']}")
        
        result = await test_endpoint(test['name'], test['payload'])
        
        if "error" in result:
            if result["error"]["code"] == -32601:
                print(f"   ❌ Tool not found: {test['name']}")
            else:
                print(f"   ❌ Error: {result['error']['message']}")
        elif "result" in result:
            content = result["result"]["content"][0]["text"]
            if "❌" in content:
                # Extract the actual error
                error_part = content.split("❌")[1].split("\n")[0].strip()
                print(f"   ❌ API Error: {error_part}")
            elif "API error" in content:
                print(f"   ❌ DataForSEO API Error")
            elif content.startswith("✅") or "results" in content.lower():
                print(f"   ✅ SUCCESS - Working!")
            else:
                print(f"   ⚠️ Unclear result: {content[:100]}...")
        else:
            print(f"   ⚠️ Unexpected response format")
        
        print()
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    print("📊 Test complete!")

if __name__ == "__main__":
    asyncio.run(main())
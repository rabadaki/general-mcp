#!/usr/bin/env python3
"""Test DataForSEO API endpoint access via deployed service."""

import httpx
import asyncio
import json

async def make_dataforseo_request(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make a request to DataForSEO API."""
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        print("❌ DataForSEO credentials not found in environment")
        return None
    
    auth = base64.b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    url = f"https://api.dataforseo.com/v3/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            return response.json()
        except Exception as e:
            print(f"Error calling {endpoint}: {str(e)}")
            return None

async def test_endpoints():
    """Test various DataForSEO endpoints."""
    print("🔍 Testing DataForSEO API Endpoint Access...\n")
    
    # Test endpoints with appropriate payloads
    test_cases = [
        {
            "name": "Ranked Keywords (Labs)",
            "endpoint": "dataforseo_labs/google/ranked_keywords/live",
            "payload": [{"target": "nansen.ai", "location_code": 2840, "language_code": "en", "limit": 1}]
        },
        {
            "name": "Historical Rankings (Labs)",
            "endpoint": "dataforseo_labs/google/historical_rank_overview/live",
            "payload": [{"target": "nansen.ai", "location_code": 2840, "language_code": "en"}]
        },
        {
            "name": "Top Pages (Labs)",
            "endpoint": "dataforseo_labs/google/top_pages/live",
            "payload": [{"target": "nansen.ai", "location_code": 2840, "language_code": "en", "limit": 1}]
        },
        {
            "name": "Keywords Suggestions (Labs)",
            "endpoint": "dataforseo_labs/google/keyword_suggestions/live",
            "payload": [{"keyword": "blockchain", "location_code": 2840, "language_code": "en", "limit": 1}]
        },
        {
            "name": "Search Volume (Keywords Data)",
            "endpoint": "keywords_data/google_ads/search_volume/live",
            "payload": [{"keywords": ["blockchain"], "location_name": "United States", "language_code": "en"}]
        },
        {
            "name": "SERP Results",
            "endpoint": "serp/google/organic/live",
            "payload": [{"keyword": "blockchain", "location_name": "United States", "language_code": "en", "depth": 1}]
        },
        {
            "name": "OnPage Audit",
            "endpoint": "on_page/task_post",
            "payload": [{"target": "nansen.ai", "max_crawl_pages": 1}]
        }
    ]
    
    for test in test_cases:
        print(f"\n📋 Testing: {test['name']}")
        print(f"   Endpoint: {test['endpoint']}")
        
        response = await make_dataforseo_request(test['endpoint'], test['payload'])
        
        if not response:
            print("   ❌ No response received")
            continue
        
        # Check overall response status
        status_code = response.get("status_code", 0)
        status_message = response.get("status_message", "")
        
        if status_code == 20000:
            print("   ✅ SUCCESS - Endpoint is available!")
            # Check task results
            tasks = response.get("tasks", [])
            if tasks and tasks[0].get("status_code") == 20000:
                print("   ✅ Task executed successfully")
            elif tasks:
                task_status = tasks[0].get("status_code", 0)
                task_message = tasks[0].get("status_message", "Unknown")
                print(f"   ⚠️ Task status: {task_status} - {task_message}")
        elif status_code == 40101:
            print("   ❌ INSUFFICIENT CREDITS")
        elif status_code == 40102:
            print("   ❌ PLAN LIMITATION - This endpoint is not available on your plan")
        elif status_code == 40401:
            print("   ❌ AUTHENTICATION FAILED")
        else:
            print(f"   ⚠️ Status {status_code}: {status_message}")
    
    print("\n\n📊 Summary:")
    print("Check the results above to see which endpoints are available on your DataForSEO plan.")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
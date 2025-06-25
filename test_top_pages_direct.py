#!/usr/bin/env python3
"""Direct test of DataForSEO top_pages endpoint to understand the exact error."""

import asyncio
import httpx
import json
import os
import base64

DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")

async def test_top_pages_direct():
    """Test the top_pages endpoint directly."""
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        print("❌ No DataForSEO credentials in environment")
        return
    
    # Test different domains
    test_domains = ["google.com", "amazon.com", "nansen.ai"]
    
    for domain in test_domains:
        print(f"\n🔍 Testing top_pages for {domain}")
        
        credentials = base64.b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json"
        }
        
        payload = [{
            "target": domain,
            "location_code": 2840,  # United States
            "language_code": "en",
            "limit": 1
        }]
        
        url = "https://api.dataforseo.com/v3/dataforseo_labs/google/top_pages/live"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                print(f"   📡 Making request to: {url}")
                print(f"   📋 Payload: {payload}")
                
                response = await client.post(url, json=payload, headers=headers)
                
                print(f"   📊 HTTP Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Response received")
                    print(f"   📄 Response keys: {list(result.keys())}")
                    
                    if "tasks" in result:
                        tasks = result["tasks"]
                        print(f"   📋 Tasks count: {len(tasks)}")
                        
                        if tasks:
                            task = tasks[0]
                            status_code = task.get("status_code", "Unknown")
                            status_message = task.get("status_message", "Unknown")
                            print(f"   📊 Task status: {status_code} - {status_message}")
                            
                            if status_code == 20000:
                                print(f"   ✅ SUCCESS! Data available for {domain}")
                            elif status_code == 40102:
                                print(f"   ❌ Plan doesn't support this endpoint")
                            elif status_code == 40101:
                                print(f"   ❌ Insufficient credits")
                            else:
                                print(f"   ⚠️ Other status: {status_code}")
                        else:
                            print(f"   ❌ No tasks in response")
                    else:
                        print(f"   ❌ No 'tasks' key in response")
                        print(f"   📄 Full response: {str(result)[:200]}...")
                        
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                    print(f"   📄 Response: {response.text[:200]}...")
                    
            except httpx.TimeoutException:
                print(f"   ⏰ Request timed out for {domain}")
            except Exception as e:
                print(f"   💥 Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_top_pages_direct())
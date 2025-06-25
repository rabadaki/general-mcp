#!/usr/bin/env python3
"""
Step 3: Test the exact function as it would appear in server.py
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

# Mock the server environment
DATAFORSEO_LOGIN = "test_login"
DATAFORSEO_PASSWORD = "test_password"

def log_api_usage(service, endpoint, count, cost_estimate=0):
    print(f"LOG: {service} {endpoint} {count} items, cost: ${cost_estimate}")

async def make_dataforseo_request(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Mock DataForSEO request"""
    print(f"MOCK API CALL: {endpoint}")
    print(f"PAYLOAD: {payload}")
    
    # Return mock success response
    return {
        "tasks": [{
            "status_code": 20000,
            "result": [{
                "id": "mock_task_12345"
            }]
        }]
    }

def extract_domain_for_onpage(target: str) -> str:
    domain = target.replace('https://', '').replace('http://', '').replace('www.', '')
    domain = domain.split('/')[0].split('?')[0]
    return domain

async def onpage_seo_audit(
    target: str,
    max_crawl_pages: int = 100,
    crawl_delay: int = 1,
    enable_javascript: bool = True,
    respect_sitemap: bool = True,
    check_spell: bool = True
) -> str:
    """Exact OnPage function as it would be in server.py"""
    log_api_usage("DataForSEO", "onpage", max_crawl_pages, cost_estimate=0.05)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ No credentials"
    
    # Extract domain properly
    domain = extract_domain_for_onpage(target)
    
    # Create payload
    task_payload = [{
        "target": domain,
        "max_crawl_pages": min(max_crawl_pages, 1000),
        "crawl_delay": crawl_delay,
        "enable_javascript": enable_javascript,
        "respect_sitemap": respect_sitemap,
        "check_spell": check_spell,
        "tag": f"onpage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }]
    
    try:
        # Make API call
        task_data = await make_dataforseo_request("on_page/task_post/", task_payload)
        
        if not task_data or "tasks" not in task_data:
            return f"❌ OnPage audit task creation failed for '{domain}'"
        
        task = task_data["tasks"][0]
        if task.get("status_code") != 20000:
            return f"❌ OnPage API error: {task.get('status_message', 'Unknown error')}"
        
        task_result = task.get("result", [])
        if not task_result:
            return f"❌ No task result received for OnPage audit"
        
        task_id = task_result[0].get("id") if task_result else None
        if not task_id:
            return f"❌ No task ID received for OnPage audit"
        
        # Return immediately
        return f"✅ OnPage audit initiated for {domain}, Task ID: {task_id}"
            
    except Exception as e:
        return f"❌ OnPage audit error for '{domain}': {str(e)[:100]}..."

# Test the exact function
if __name__ == "__main__":
    async def test():
        result = await onpage_seo_audit("https://example.com")
        print(result)
    
    asyncio.run(test())
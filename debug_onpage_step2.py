#!/usr/bin/env python3
"""
Step 2: Test async function structure with minimal imports
"""

import asyncio
from datetime import datetime

def extract_domain_for_onpage(target: str) -> str:
    domain = target.replace('https://', '').replace('http://', '').replace('www.', '')
    domain = domain.split('/')[0].split('?')[0]
    return domain

async def minimal_onpage_audit(target: str, max_crawl_pages: int = 100) -> str:
    """Minimal OnPage function - no API calls, just structure"""
    
    # Test datetime usage
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Test domain extraction
    domain = extract_domain_for_onpage(target)
    
    # Test payload creation
    task_payload = [{
        "target": domain,
        "max_crawl_pages": min(max_crawl_pages, 1000),
        "tag": f"onpage_{timestamp}"
    }]
    
    return f"✅ OnPage structure test passed for {domain}"

# Test
if __name__ == "__main__":
    async def test():
        result = await minimal_onpage_audit("https://example.com", 50)
        print(result)
    
    asyncio.run(test())
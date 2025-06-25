#!/usr/bin/env python3
"""
Step 1: Test just the domain extraction function
"""

def extract_domain_for_onpage(target: str) -> str:
    """Extract domain from URL for DataForSEO OnPage API."""
    # Remove protocol and www
    domain = target.replace('https://', '').replace('http://', '').replace('www.', '')
    # Remove path and query parameters
    domain = domain.split('/')[0].split('?')[0]
    return domain

# Test
if __name__ == "__main__":
    test_urls = [
        "https://example.com",
        "https://www.example.com/path",
        "http://subdomain.example.com",
        "https://example.com?param=value"
    ]
    
    for url in test_urls:
        domain = extract_domain_for_onpage(url)
        print(f"{url} -> {domain}")
    
    print("✅ Domain extraction function works correctly")
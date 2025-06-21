import sys
import os

# Set the API key directly
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

sys.path.append('/Users/Amos/general-mcp')

# Import server AFTER setting environment variable
import server
import asyncio

async def test():
    # Test searching for tweets about AI sorted by Top
    print("Testing search_twitter for 'artificial intelligence' (sorted by Top)...")
    print("=" * 60)
    
    result = await server.search_twitter('artificial intelligence', limit=5, sort='Top')
    print(result)
    
    print("\n" + "=" * 60)
    print("\nNow testing with a different query - 'OpenAI' (sorted by Top):")
    print("=" * 60)
    
    result2 = await server.search_twitter('OpenAI', limit=3, sort='Top')
    print(result2)

asyncio.run(test()) 
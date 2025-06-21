import sys
import os

# Set the API key directly
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

sys.path.append('/Users/Amos/general-mcp')

# Import server AFTER setting environment variable
import server
import asyncio

async def test():
    # Test getting profile for Elon Musk
    print("Testing get_twitter_profile for @elonmusk...")
    print("=" * 60)
    
    result = await server.get_twitter_profile('elonmusk')
    print(result)
    
    print("\n" + "=" * 60)
    print("\nNow testing with followers included:")
    print("=" * 60)
    
    result2 = await server.get_twitter_profile('elonmusk', get_followers=True)
    print(result2)

asyncio.run(test()) 
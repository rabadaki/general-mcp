import sys
import os

# Set the API key directly
os.environ['APIFY_TOKEN'] = 'apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM'

sys.path.append('/Users/Amos/general-mcp')

# Import server AFTER setting environment variable
import server
import asyncio

async def test():
    # Test getting tweets from Elon Musk's timeline
    print("Testing get_user_tweets for @elonmusk...")
    print("=" * 60)
    
    result = await server.get_user_tweets('elonmusk', limit=5)
    print(result)
    
    print("\n" + "=" * 60)
    print("\nNow testing with a different user - @OpenAI:")
    print("=" * 60)
    
    result2 = await server.get_user_tweets('OpenAI', limit=3)
    print(result2)

asyncio.run(test()) 
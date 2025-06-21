import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.append('/Users/Amos/general-mcp')
from server import get_user_tweets
import asyncio

async def test():
    # Test getting tweets from Elon Musk's timeline
    print("Testing get_user_tweets for @elonmusk...")
    print("=" * 60)
    
    result = await get_user_tweets('elonmusk', limit=5)
    print(result)
    
    print("\n" + "=" * 60)
    print("\nNow testing with a different user - @OpenAI:")
    print("=" * 60)
    
    result2 = await get_user_tweets('OpenAI', limit=3)
    print(result2)

asyncio.run(test()) 
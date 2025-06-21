import asyncio
import sys
sys.path.append('/Users/Amos/general-mcp')

from mcp_stdio_server import search_reddit

async def test_reddit_search():
    print("Testing Reddit search for 'python programming'...")
    result = await search_reddit(
        query="python programming",
        limit=3
    )
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_reddit_search()) 
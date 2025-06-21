import asyncio
import os
import sys
sys.path.append('/Users/Amos/general-mcp')

async def test_tiktok():
    try:
        from server import get_tiktok_user_videos
        print("Starting TikTok test...")
        result = await get_tiktok_user_videos('mrbeast', 3)
        print(f"SUCCESS: {result}")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tiktok()) 
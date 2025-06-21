import re

with open('server.py', 'r') as f:
    content = f.read()

# Find all tool names
tool_names = re.findall(r'"name":\s*"([^"]+)"', content)

print(f"Current tools ({len(tool_names)} total):")
print("=" * 50)

for i, tool in enumerate(tool_names, 1):
    print(f"{i:2d}. {tool}")

print("\n" + "=" * 50)
print("\nWorking tools (based on our testing):")
working = [
    "search_reddit",
    "get_subreddit_posts", 
    "get_reddit_comments",
    "search_web",
    "get_api_usage_stats",
    "search_youtube",
    "get_youtube_trending",
    "search_perplexity",
    "search_google_trends",
    "compare_google_trends",
    "search_twitter",
    "get_twitter_profile",
    "search_tiktok",
    "get_tiktok_user_videos"
]

for tool in working:
    print(f"✅ {tool}")
    
print(f"\nTotal working: {len(working)}")

print("\nNon-working/Incomplete tools:")
non_working = [t for t in tool_names if t not in working]
for tool in non_working:
    print(f"❌ {tool}")
    
print(f"\nTotal non-working: {len(non_working)}") 
import re

import os
os.chdir('..')
with open('mcp_stdio_server.py', 'r') as f:
    content = f.read()

# Find all tool names
tool_names = re.findall(r'"name":\s*"([^"]+)"', content)

# Filter out non-tool entries
tool_names = [t for t in tool_names if t != "General Search"]

print(f"Total MCP Tools: {len(tool_names)}")
print("=" * 50)

# List of working tools based on our testing
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
    "get_tiktok_user_videos",
    "search_instagram",
    "get_instagram_profile",
    "search_serp",
    "keyword_research", 
    "competitor_analysis"
]

print("\n✅ Working Tools:")
for i, tool in enumerate(working, 1):
    if tool in tool_names:
        print(f"{i:2d}. {tool}")
    
print(f"\nTotal working: {len([t for t in working if t in tool_names])}")

print("\n❌ Non-working/Incomplete Tools:")
non_working = [t for t in tool_names if t not in working]
for i, tool in enumerate(non_working, 1):
    print(f"{i:2d}. {tool}")
    
print(f"\nTotal non-working: {len(non_working)}")

print(f"\n📊 Summary:")
print(f"- Total tools: {len(tool_names)}")
print(f"- Working: {len([t for t in working if t in tool_names])}")
print(f"- Non-working: {len(non_working)}")
print(f"- Missing from original 22: {22 - len(tool_names)}") 
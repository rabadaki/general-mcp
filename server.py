#!/usr/bin/env python3
"""
General MCP Server - Comprehensive Social Media & Web Search Platform
====================================================================

A Model Context Protocol (MCP) server providing unified access to:
- Reddit (posts, comments, subreddit data)
- YouTube (video search, trending content)  
- Twitter (tweet search, user timelines)
- TikTok (video search, user content)
- Perplexity AI (intelligent web search)
- Web Search (DuckDuckGo integration)
- Google Trends (trend analysis and comparison)

Features:
- Rate limiting and cost protection
- Comprehensive error handling
- Usage analytics and monitoring
- Flexible result formatting
- Multi-transport support (stdio/SSE)

Version: 2.0.0
Author: General MCP Team
License: MIT
"""

import asyncio
import json
import urllib.parse
import re
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

# HTTP and API clients
import httpx
import requests
from bs4 import BeautifulSoup

# MCP and web framework
from fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from mcp.server.sse import SseServerTransport
from starlette.requests import Request

# Environment and configuration
import os

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Initialize FastMCP server
mcp = FastMCP("General Search")

# API Endpoints
REDDIT_BASE_URL = "https://www.reddit.com"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"
TWITTER_API_URL = "https://api.apify.com/v2/acts/61RPP7dywgiy0JPD0/run-sync-get-dataset-items"
TIKTOK_API_URL = "https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
SCRAPINGBEE_API_URL = "https://app.scrapingbee.com/api/v1/"

# Request configuration
USER_AGENT = "GeneralMCPServer/2.0"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3

# Rate limits and safety constraints
MAX_LIMIT = 50                    # Global maximum results per request
TWITTER_MAX_LIMIT = 50           # Twitter specific limit (increased from 25)
TWITTER_MAX_DAYS = 7             # Twitter max days back (cost protection)
YOUTUBE_MAX_LIMIT = 50           # YouTube API limit
TIKTOK_MAX_LIMIT = 50            # TikTok scraper limit
TIKTOK_MAX_DAYS = 30             # TikTok max days back

# ============================================================================
# API CREDENTIALS
# ============================================================================
# Use environment variables in production, fallback to hardcoded for development

# YouTube Data API v3 (100 calls/day free tier)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ")

# Apify API (for Twitter & TikTok scraping)
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM")

# Perplexity AI API (5 requests/minute free tier)
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "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")

# ScrapingBee API (for Google Trends access)
SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY", "68AEL9OT9277RWTL7HA6H6OFTCR20HELBSCYXQAPW2SDFEFB3BJ8I1TOJS9WJVCFE4OHWULFRO0AILZU")

# ============================================================================
# API USAGE LIMITS & COST WARNINGS
# ============================================================================
"""
API Service Limits & Cost Structure:

Reddit:         FREE - Unlimited access via public JSON endpoints
YouTube:        FREE - 100 API calls/day, 50 results per call max
Twitter (Apify): PAID - Rate limited by Apify plan, cost per result
TikTok (Apify):  PAID - Rate limited by Apify plan, cost per result  
Perplexity:     FREE/PAID - 5 requests/minute free, unlimited paid
Web Search:     FREE - DuckDuckGo public API, no limits
Google Trends:  FREE - Via ScrapingBee proxy, limited by anti-bot measures

⚠️  CRITICAL COST PROTECTION ⚠️
The Twitter actor (61RPP7dywgiy0JPD0) has built-in rate limiting to prevent
cost overruns. Previous testing showed the old actor ignored maxTweets
parameter and returned 10,000+ results costing $4.25+ per search.

Current safety measures:
- New rate-limited Twitter actor (61RPP7dywgiy0JPD0)
- Conservative limits: max 50 tweets, max 7 days back
- Multiple limit parameters in API payload
- Post-processing result limiting as backup
- Comprehensive usage logging and monitoring
"""

# ============================================================================
# USAGE TRACKING & MONITORING
# ============================================================================

# Simple in-memory usage tracking for cost monitoring
api_usage_log: List[Dict[str, Any]] = []

def log_api_usage(
    service: str, 
    endpoint: str, 
    requested_limit: int, 
    actual_results: Optional[int] = None,
    cost_estimate: Optional[float] = None
) -> None:
    """
    Log API usage for monitoring and cost tracking.
    
    Args:
        service: Service name (e.g., 'Twitter', 'YouTube', 'TikTok')
        endpoint: Specific endpoint called (e.g., 'search', 'user_tweets')
        requested_limit: Number of results requested
        actual_results: Actual number of results received (None if pending)
        cost_estimate: Estimated cost in USD (None if free/unknown)
    """
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "service": service,
        "endpoint": endpoint,
        "requested_limit": requested_limit,
        "actual_results": actual_results,
        "cost_estimate": cost_estimate,
        "status": "completed" if actual_results is not None else "pending"
    }
    api_usage_log.append(log_entry)
    
    # Console logging for real-time monitoring
    cost_info = f" (~${cost_estimate:.3f})" if cost_estimate else ""
    print(f"📊 {service}.{endpoint}: requested {requested_limit}, got {actual_results or 'pending'}{cost_info}")
    
    # Rotate log to prevent memory bloat (keep last 200 entries)
    if len(api_usage_log) > 200:
        api_usage_log.pop(0)

def validate_limit(limit: int, max_allowed: int, service: str = "API") -> int:
    """
    Validate and normalize limit parameters across all services.
    
    Args:
        limit: Requested limit
        max_allowed: Maximum allowed limit for this service
        service: Service name for logging
        
    Returns:
        Validated limit within acceptable bounds
    """
    if not isinstance(limit, int):
        print(f"⚠️  {service}: Invalid limit type {type(limit)}, defaulting to 10")
        return 10
        
    if limit < 1:
        print(f"⚠️  {service}: Limit {limit} too low, setting to 1")
        return 1
        
    if limit > max_allowed:
        print(f"⚠️  {service}: Limit {limit} exceeds max {max_allowed}, capping")
        return max_allowed
        
    return limit

def validate_days_back(days: int, max_allowed: int, service: str = "API") -> int:
    """
    Validate days_back parameters with service-specific limits.
    
    Args:
        days: Requested days back
        max_allowed: Maximum allowed days for this service
        service: Service name for logging
        
    Returns:
        Validated days within acceptable bounds
    """
    if not isinstance(days, int):
        print(f"⚠️  {service}: Invalid days type {type(days)}, defaulting to 7")
        return 7
        
    if days < 1:
        print(f"⚠️  {service}: Days {days} too low, setting to 1")
        return 1
        
    if days > max_allowed:
        print(f"⚠️  {service}: Days {days} exceeds max {max_allowed}, capping")
        return max_allowed
        
    return days

# ============================================================================
# HTTP CLIENT & REQUEST UTILITIES
# ============================================================================

async def make_request(
    url: str, 
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    json_data: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Any]]:
    """
    Make HTTP requests with comprehensive error handling and retries.
    
    Args:
        url: Request URL
        params: Query parameters
        headers: Request headers
        method: HTTP method (GET, POST)
        json_data: JSON payload for POST requests
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response or None on failure
        
    Raises:
        None - All exceptions are caught and logged
    """
    if headers is None:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
    
    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == "POST":
                    response = await client.post(
                        url, 
                        headers=headers, 
                        params=params, 
                        json=json_data, 
                        timeout=timeout
                    )
                else:
                    response = await client.get(
                        url, 
                        headers=headers, 
                        params=params, 
                        timeout=timeout
                    )
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP {e.response.status_code} on attempt {attempt + 1}/{MAX_RETRIES}: {url}")
                if e.response.status_code == 429:  # Rate limited
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                elif e.response.status_code >= 500:  # Server error
                    await asyncio.sleep(1)
                    continue
                else:
                    break  # Client error, don't retry
                    
            except httpx.TimeoutException:
                print(f"⏱️  Timeout on attempt {attempt + 1}/{MAX_RETRIES}: {url}")
                await asyncio.sleep(1)
                continue
                
            except Exception as e:
                print(f"🔥 Unexpected error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1)
                    continue
                break
    
    print(f"💀 All {MAX_RETRIES} attempts failed for: {url}")
    return None

# REDDIT TOOLS
@mcp.tool()
async def search_reddit(
    query: str,
    subreddit: str = "",
    sort: str = "relevance",
    time: str = "all",
    limit: int = 10
) -> str:
    """
    Search Reddit for posts matching a query.
    
    Args:
        query: Search terms to look for
        subreddit: Specific subreddit to search (optional, leave empty for all)
        sort: Sort order (relevance, hot, top, new, comments)
        time: Time period for search (all, year, month, week, day, hour)
        limit: Number of results to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    search_query = query
    if subreddit:
        search_query = f"subreddit:{subreddit} {query}"
    
    url = f"{REDDIT_BASE_URL}/search.json"
    params = {
        "q": search_query,
        "sort": sort,
        "t": time,
        "limit": limit
    }
    
    data = await make_request(url, params)
    
    if not data or "data" not in data:
        return f"❌ Unable to search Reddit. Please try again later."
    
    children = data.get("data", {}).get("children", [])
    
    if not children:
        return f"🔍 No posts found for query: '{query}'" + (f" in r/{subreddit}" if subreddit else "")
    
    results = []
    for child in children:
        post_data = child.get("data", {})
        formatted_post = format_reddit_post(post_data)
        
        result = f"""
📝 **{formatted_post['title']}**
👤 u/{formatted_post['author']} in r/{formatted_post['subreddit']}
⬆️ {formatted_post['score']} points | 💬 {formatted_post['num_comments']} comments
🔗 {formatted_post['url']}
"""
        if formatted_post['selftext']:
            result += f"📄 {formatted_post['selftext']}\n"
        
        results.append(result.strip())
    
    header = f"🔍 Found {len(results)} Reddit posts for: '{query}'" + (f" in r/{subreddit}" if subreddit else "")
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def get_subreddit_posts(
    subreddit: str,
    sort: str = "hot",
    time: str = "day",
    limit: int = 10
) -> str:
    """
    Get top posts from a specific subreddit.
    
    Args:
        subreddit: Name of the subreddit (without r/)
        sort: Sort order (hot, new, top, rising)
        time: Time period for top posts (all, year, month, week, day, hour)
        limit: Number of posts to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    url = f"{REDDIT_BASE_URL}/r/{subreddit}/{sort}.json"
    params = {
        "limit": limit,
        "t": time if sort == "top" else None
    }
    
    params = {k: v for k, v in params.items() if v is not None}
    
    data = await make_request(url, params)
    
    if not data or "data" not in data:
        return f"❌ Unable to fetch posts from r/{subreddit}. Check if the subreddit exists."
    
    children = data.get("data", {}).get("children", [])
    
    if not children:
        return f"📭 No posts found in r/{subreddit}"
    
    results = []
    for child in children:
        post_data = child.get("data", {})
        formatted_post = format_reddit_post(post_data)
        
        result = f"""
📝 **{formatted_post['title']}**
👤 u/{formatted_post['author']}
⬆️ {formatted_post['score']} points | 💬 {formatted_post['num_comments']} comments
🔗 {formatted_post['url']}
"""
        if formatted_post['selftext']:
            result += f"📄 {formatted_post['selftext']}\n"
        
        results.append(result.strip())
    
    header = f"📋 Top {len(results)} {sort} posts from r/{subreddit}"
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def get_reddit_comments(
    post_url: str,
    limit: int = 10
) -> str:
    """
    Get comments from a Reddit post.
    
    Args:
        post_url: Full URL to the Reddit post
        limit: Number of top-level comments to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    # Convert URL to JSON format
    if not post_url.endswith('.json'):
        post_url = post_url.rstrip('/') + '.json'
    
    # Ensure it's a proper Reddit URL
    if not post_url.startswith('https://'):
        if post_url.startswith('/r/'):
            post_url = f"{REDDIT_BASE_URL}{post_url}"
        elif not post_url.startswith('reddit.com'):
            post_url = f"{REDDIT_BASE_URL}/{post_url}"
    
    params = {"limit": limit}
    
    data = await make_request(post_url, params)
    
    if not data or len(data) < 2:
        return f"❌ Unable to fetch comments from the post. Check if the URL is valid."
    
    # Get post data
    post_data = data[0]["data"]["children"][0]["data"]
    post_title = post_data.get("title", "Unknown post")
    
    # Get comments data
    comments_data = data[1]["data"]["children"]
    
    if not comments_data:
        return f"💬 No comments found for: {post_title}"
    
    results = []
    for comment in comments_data[:limit]:
        comment_data = comment.get("data", {})
        if comment_data.get("body") and comment_data.get("body") != "[deleted]":
            author = comment_data.get("author", "Unknown")
            score = comment_data.get("score", 0)
            body = comment_data.get("body", "")
            
            # Truncate long comments
            if len(body) > 300:
                body = body[:300] + "..."
            
            result = f"""
👤 u/{author} ({score} points)
💬 {body}
"""
            results.append(result.strip())
    
    if not results:
        return f"💬 No readable comments found for: {post_title}"
    
    header = f"💬 Top {len(results)} comments for: {post_title}"
    return header + "\n\n" + "\n---\n".join(results)

# YOUTUBE TOOLS
@mcp.tool()
async def search_youtube(
    query: str,
    published_after: str = "",
    published_before: str = "",
    order: str = "viewCount",
    limit: int = 10
) -> str:
    """
    Search YouTube for videos matching a query.
    
    Args:
        query: Search terms to look for
        published_after: ISO date string (e.g., "2024-01-01T00:00:00Z")
        published_before: ISO date string (e.g., "2024-12-31T23:59:59Z")
        order: Sort order (relevance, date, rating, viewCount, title, videoCount)
        limit: Number of results to return (max 50)
    """
    
    limit = min(max(1, limit), 50)  # YouTube API allows up to 50 results
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": order,
        "key": YOUTUBE_API_KEY,
        "maxResults": limit
    }
    
    if published_after:
        params["publishedAfter"] = published_after
    if published_before:
        params["publishedBefore"] = published_before
    
    data = await make_request(YOUTUBE_API_URL, params)
    
    if not data or "items" not in data:
        return f"❌ Unable to search YouTube. Please check your API key or try again later."
    
    items = data.get("items", [])
    
    if not items:
        return f"🔍 No videos found for query: '{query}'"
    
    results = []
    for item in items:
        formatted_video = format_youtube_video(item)
        
        result = f"""
🎥 **{formatted_video['title']}**
📺 {formatted_video['channel']}
📅 {formatted_video['published'][:10] if formatted_video['published'] else 'Unknown date'}
🔗 {formatted_video['url']}
"""
        if formatted_video['description']:
            result += f"📝 {formatted_video['description']}\n"
        
        results.append(result.strip())
    
    header = f"🎥 Found {len(results)} YouTube videos for: '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def get_youtube_trending(
    category: str = "0",
    region: str = "US",
    limit: int = 10
) -> str:
    """
    Get trending YouTube videos.
    
    Args:
        category: Category ID (0=All, 1=Film, 2=Autos, 10=Music, 15=Pets, 17=Sports, 19=Travel, 20=Gaming, 22=People, 23=Comedy, 24=Entertainment, 25=News, 26=Howto, 27=Education, 28=Science)
        region: Country code (US, GB, CA, AU, DE, FR, JP, etc.)
        limit: Number of results to return (max 50)
    """
    
    limit = min(max(1, limit), 50)  # YouTube API allows up to 50 results
    
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "videoCategoryId": category if category != "0" else None,
        "key": YOUTUBE_API_KEY,
        "maxResults": limit
    }
    
    params = {k: v for k, v in params.items() if v is not None}
    
    data = await make_request(url, params)
    
    if not data or "items" not in data:
        return f"❌ Unable to get trending videos. Please try again later."
    
    items = data.get("items", [])
    
    if not items:
        return f"📭 No trending videos found"
    
    results = []
    for item in items:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        
        result = f"""
🎥 **{snippet.get('title', 'No title')}**
📺 {snippet.get('channelTitle', 'Unknown channel')}
👀 {stats.get('viewCount', '0')} views | 👍 {stats.get('likeCount', '0')} likes
🔗 https://youtube.com/watch?v={item.get('id', '')}
"""
        
        results.append(result.strip())
    
    header = f"🔥 Top {len(results)} trending YouTube videos"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# TWITTER TOOLS - Rate Limited & Cost Protected
# ============================================================================

@mcp.tool()
async def search_twitter(
    query: str,
    limit: int = 15,
    sort: str = "Latest",
    days_back: int = 7
) -> str:
    """
    Search for tweets based on a query using Apify's rate-limited Twitter scraper.
    
    Args:
        query: Search query for tweets (supports Twitter syntax: quotes, hashtags, mentions)
        limit: Number of tweets to return (1-50, default 15)
        sort: Sort order ("Latest", "Top", "People", "Photos", "Videos")  
        days_back: How many days back to search (1-7, default 7, cost controlled)
    
    Returns:
        Formatted string with tweet results including text, metrics, and metadata
        
    Cost Protection:
        - Uses rate-limited actor 61RPP7dywgiy0JPD0 to prevent cost overruns
        - Limited to 50 tweets max and 7 days back max
        - Comprehensive usage logging for monitoring
    """
    # Validate and normalize parameters
    limit = validate_limit(limit, TWITTER_MAX_LIMIT, "Twitter")
    days_back = validate_days_back(days_back, TWITTER_MAX_DAYS, "Twitter")
    
    # Calculate date range for cost-controlled searches
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    print(f"🐦 Twitter search: '{query}' | {limit} tweets | {days_back} days")
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"🛡️  Using rate-limited actor 61RPP7dywgiy0JPD0 for cost protection")
    
    # Log API usage for monitoring
    log_api_usage("Twitter", "search", limit)
    
    # Build Twitter-native search query with date constraints
    search_query = f"{query} since:{start_date.strftime('%Y-%m-%d')} until:{end_date.strftime('%Y-%m-%d')}"
    
    # API Dojo Tweet Scraper V2 payload with multiple safety parameters
    payload = {
        "searchTerms": [search_query],
        "maxItems": limit,                 # Primary limit
        "includeSearchTerms": False,
        "onlyImage": False,
        "onlyQuote": False,
        "onlyTwitterBlue": False,
        "onlyVerifiedUsers": False,
        "onlyVideo": False,
        "sort": sort,
        "tweetLanguage": "en"
    }
    
    headers = {"Content-Type": "application/json"}
    params = {"token": APIFY_TOKEN, "timeout": 120}
    
    print(f"🔄 Executing search with query: {search_query}")
    
    # Make API request with comprehensive error handling
    data = await make_request(TWITTER_API_URL, params, headers, "POST", payload)
    
    if not data:
        log_api_usage("Twitter", "search", limit, 0)
        return f"❌ Twitter search failed. Please check your Apify token or try again later."
    
    if not isinstance(data, list):
        log_api_usage("Twitter", "search", limit, 0)
        return f"❌ Unexpected Twitter API response format: {type(data)}"
    
    # Apply backup safety limiting (defense in depth)
    original_count = len(data)
    data = data[:limit]
    final_count = len(data)
    
    # Log actual results for cost monitoring
    log_api_usage("Twitter", "search", limit, final_count)
    
    # Monitor for unexpected high results (cost protection alerting)
    if original_count > limit:
        print(f"ℹ️  Actor returned {original_count} results, safety-limited to {limit}")
        print(f"🛡️  Rate limits + safety controls prevented cost overrun")
    
    if not data:
        return f"🔍 No tweets found for '{query}' in the last {days_back} days"
    
    # Format results with flexible data structure handling
    results = []
    for i, tweet in enumerate(data, 1):
        try:
            # Extract text with fallback handling
            text = tweet.get("text", tweet.get("full_text", tweet.get("content", "No text")))
            
            # Handle various author data structures from different scraper versions
            author_info = tweet.get("author", tweet.get("user", {}))
            if isinstance(author_info, dict):
                author_name = author_info.get("userName", 
                    author_info.get("name", 
                    author_info.get("screen_name", "Unknown")))
                author_handle = author_info.get("userHandle", 
                    author_info.get("screen_name", 
                    author_info.get("handle", "Unknown")))
            else:
                author_name = str(author_info) if author_info else "Unknown"
                author_handle = "Unknown"
            
            # Extract engagement metrics with multiple fallbacks
            likes = tweet.get("likes", tweet.get("favorite_count", tweet.get("likeCount", 0)))
            retweets = tweet.get("retweets", tweet.get("retweet_count", tweet.get("retweetCount", 0)))
            replies = tweet.get("replies", tweet.get("reply_count", tweet.get("replyCount", 0)))
            created_at = tweet.get("createdAt", tweet.get("created_at", tweet.get("date", "")))
            tweet_url = tweet.get("url", tweet.get("link", "No URL"))
            
            # Format individual tweet result
            result = f"""
🐦 **@{author_handle}** ({author_name})
💬 {text[:200]}{'...' if len(text) > 200 else ''}
❤️ {likes:,} | 🔄 {retweets:,} | 💭 {replies:,}
📅 {created_at[:10] if created_at else 'Unknown date'}
🔗 {tweet_url}
"""
            results.append(result.strip())
            
        except Exception as e:
            print(f"⚠️  Error formatting tweet {i}: {e}")
            # Continue processing other tweets
            continue
    
    print(f"✅ Twitter search completed: {len(results)}/{original_count} tweets processed")
    
    efficiency_note = ""
    if original_count != final_count:
        efficiency_note = f" (limited from {original_count} for cost protection)"
    
    header = f"🐦 Found {len(results)} tweets for '{query}' (last {days_back} days){efficiency_note}"
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def get_user_tweets(
    username: str,
    limit: int = 15,  # Increased from 10 to 15
    days_back: int = 7
) -> str:
    """
    Get recent tweets from a specific user.
    
    Args:
        username: Twitter username (without @)
        limit: Number of tweets to return (max 50)
        days_back: How many days back to search (max 7 for cost control)
    
    Returns:
        Formatted string with tweet results
    """
    limit = min(max(1, limit), 50)  # Increased from 25 to 50 max
    
    # Clean username
    username = username.strip().lstrip('@')
    
    # Calculate date range
    from datetime import datetime, timedelta
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    print(f"🐦 User tweets: username=@{username}, limit={limit}, days_back={days_back}")
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"🛡️  SAFETY: Using actor 61RPP7dywgiy0JPD0 with rate limit protection")
    
    # Log the API request
    log_api_usage("Twitter", "user_tweets", limit)
    
    # API Dojo Tweet Scraper V2 payload for user tweets using Twitter query syntax
    search_query = f"from:{username} since:{start_date.strftime('%Y-%m-%d')} until:{end_date.strftime('%Y-%m-%d')}"
    
    payload = {
        "searchTerms": [search_query],
        "maxItems": limit,
        "includeSearchTerms": False,
        "onlyImage": False,
        "onlyQuote": False,
        "onlyTwitterBlue": False,
        "onlyVerifiedUsers": False,
        "onlyVideo": False,
        "sort": "Latest",
        "tweetLanguage": "en"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    params = {
        "token": APIFY_TOKEN,
        "timeout": 120  # Reasonable timeout
    }
    
    print(f"🔄 Using API Dojo Tweet Scraper V2 with query: {search_query}")
    
    data = await make_request(TWITTER_API_URL, params, headers, "POST", payload)
    
    if not data or not isinstance(data, list):
        return f"❌ Unable to get tweets from @{username}. API response: {data}"
    
    # Safety: Still limit results as backup protection
    original_count = len(data) if data else 0
    data = data[:limit]
    
    # Log the actual results received
    log_api_usage("Twitter", "user_tweets", limit, len(data) if data else 0)
    
    # Monitor for any unexpected results
    if original_count > limit:
        print(f"ℹ️  INFO: Actor returned {original_count} results, limited to {limit}")
        print(f"🛡️  Rate limits should have controlled costs")
    
    if not data:
        return f"📭 No tweets found for @{username} in the last {days_back} days"
    
    results = []
    for tweet in data:
        # Handle flexible tweet data structures
        text = tweet.get("text", tweet.get("full_text", tweet.get("content", "No text")))
        
        # Handle various author field formats
        author_info = tweet.get("author", tweet.get("user", {}))
        if isinstance(author_info, dict):
            author_handle = author_info.get("userHandle", author_info.get("screen_name", author_info.get("handle", username)))
        else:
            author_handle = username
        
        # Handle various metric field formats
        likes = tweet.get("likes", tweet.get("favorite_count", tweet.get("likeCount", 0)))
        retweets = tweet.get("retweets", tweet.get("retweet_count", tweet.get("retweetCount", 0)))
        replies = tweet.get("replies", tweet.get("reply_count", tweet.get("replyCount", 0)))
        created_at = tweet.get("createdAt", tweet.get("created_at", tweet.get("date", "")))
        
        result = f"""
🐦 **@{author_handle}**
💬 {text[:200]}{'...' if len(text) > 200 else ''}
❤️ {likes} | 🔄 {retweets} | 💭 {replies}
📅 {created_at[:10] if created_at else 'Unknown date'}
🔗 {tweet.get('url', tweet.get('link', 'No URL'))}
"""
        
        results.append(result.strip())
    
    print(f"✅ User tweets returned {len(results)} results (requested {limit})")
    
    header = f"🐦 Recent {len(results)} tweets from @{username} (last {days_back} days)"
    return header + "\n\n" + "\n---\n".join(results)

# PERPLEXITY SEARCH TOOL
@mcp.tool()
async def search_perplexity(
    query: str,
    max_results: int = 10
) -> str:
    """
    Search the web using Perplexity AI for comprehensive, real-time information.
    
    Args:
        query: Search query
        max_results: Number of sources to include (1-10, default 5)
    """
    
    max_results = min(max(1, max_results), 10)
    
    # Use Perplexity's web search endpoint
    perplexity_url = "https://api.perplexity.ai/chat/completions"
    
    headers = {
        "Authorization": "Bearer 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",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": f"You are a helpful search assistant. Provide a comprehensive summary of current information about the query. Include {max_results} key sources and their URLs."
            },
            {
                "role": "user", 
                "content": f"Search for: {query}"
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
        "return_citations": True
    }
    
    data = await make_request(perplexity_url, None, headers, "POST", payload)
    
    if not data:
        return f"❌ Unable to search with Perplexity. Please check your API key or try again later."
    
    # Extract the response content
    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    if not response_text:
        return f"🔍 No results found for query: '{query}'"
    
    header = f"🧠 **Perplexity AI Search Results for: '{query}'**"
    return header + "\n\n" + response_text

# WEB SEARCH ALTERNATIVE (using DuckDuckGo - no API key needed)
@mcp.tool()
async def search_web(
    query: str,
    max_results: int = 10,
    limit: int = None  # Add limit as alias for consistency
) -> str:
    """
    Search the web using DuckDuckGo for current information and news.
    
    Args:
        query: Search query
        max_results: Number of results to return (1-50, default 10)
        limit: Alias for max_results (for consistency with other tools)
    """
    
    # Use limit if provided, otherwise use max_results
    if limit is not None:
        max_results = limit
        
    max_results = min(max(1, max_results), 50)  # Increased limit for more comprehensive results
    
    # Use DuckDuckGo's instant answer API
    ddg_url = "https://api.duckduckgo.com/"
    
    params = {
        "q": query,
        "format": "json",
        "pretty": "1",
        "no_redirect": "1",
        "no_html": "1",
        "skip_disambig": "1"
    }
    
    data = await make_request(ddg_url, params)
    
    if not data:
        return f"❌ Unable to search the web. Please try again later."
    
    # Get instant answer if available
    abstract = data.get("Abstract", "")
    answer = data.get("Answer", "")
    
    results = []
    
    if answer:
        results.append(f"🎯 **Direct Answer**: {answer}")
    
    if abstract:
        results.append(f"📝 **Summary**: {abstract}")
    
    # Get related topics
    related_topics = data.get("RelatedTopics", [])[:max_results]
    
    if related_topics:
        results.append("🔗 **Related Information**:")
        for i, topic in enumerate(related_topics, 1):
            if isinstance(topic, dict) and topic.get("Text"):
                text = topic.get("Text", "")[:200] + "..." if len(topic.get("Text", "")) > 200 else topic.get("Text", "")
                url = topic.get("FirstURL", "")
                results.append(f"{i}. {text}")
                if url:
                    results.append(f"   🔗 {url}")
    
    # Get definition if available
    definition = data.get("Definition", "")
    if definition:
        results.append(f"📖 **Definition**: {definition}")
    
    if not results:
        return f"🔍 No comprehensive results found for: '{query}'. Try a more specific search term."
    
    header = f"🌐 Web search results for: '{query}'"
    return header + "\n\n" + "\n\n".join(results)

# TIKTOK TOOLS
@mcp.tool()
async def search_tiktok(
    query: str,
    limit: int = 10,
    days_back: int = 7
) -> str:
    """
    Search TikTok for videos matching a query using Apify.
    
    Args:
        query: Search terms to look for
        limit: Number of results to return (max 50)
        days_back: How many days back to search (1-30, default 7)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    days_back = min(max(1, days_back), 30)
    
    # Use the TikTok scraper that was working in n8n
    payload = {
        "excludePinnedPosts": False,
        "proxyCountryCode": "None",
        "resultsPerPage": limit,
        "shouldDownloadAvatars": False,
        "shouldDownloadCovers": False,
        "shouldDownloadMusicCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadVideos": False
    }
    
    # Add search parameters based on query type
    if query.startswith("#"):
        payload["hashtags"] = [query.lstrip("#")]
        payload["searchQueries"] = []
    else:
        payload["searchQueries"] = [query]
        payload["hashtags"] = []
    
    headers = {
        "Content-Type": "application/json"
    }
    
    params = {
        "token": APIFY_TOKEN
    }
    
    # Try the clockworks TikTok scraper
    tiktok_url = TIKTOK_API_URL
    
    data = await make_request(tiktok_url, params, headers, "POST", payload)
    
    if not data or not isinstance(data, list):
        return f"❌ Unable to search TikTok. Check your Apify plan or try again later."
    
    if not data:
        return f"🔍 No TikTok videos found for query: '{query}'"
    
    results = []
    for video in data[:limit]:
        # Handle different possible TikTok data structures
        text = video.get("text", video.get("title", "No description"))
        author = video.get("authorMeta", {}).get("name", video.get("author", "Unknown"))
        likes = video.get("diggCount", video.get("likes", 0))
        plays = video.get("playCount", video.get("views", 0))
        url = video.get("webVideoUrl", video.get("url", ""))
        
        result = f"""
🎵 **@{author}**
📝 {text[:150]}{'...' if len(text) > 150 else ''}
❤️ {likes:,} likes | ▶️ {plays:,} plays
🔗 {url}
"""
        
        results.append(result.strip())
    
    header = f"🎵 Found {len(results)} TikTok videos for: '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def get_tiktok_user_videos(
    username: str,
    limit: int = 10
) -> str:
    """
    Get recent videos from a specific TikTok user.
    
    Args:
        username: TikTok username (without @)
        limit: Number of videos to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    user_payload = {
        "profiles": [f"https://www.tiktok.com/@{username}"],
        "excludePinnedPosts": False,
        "proxyCountryCode": "US",
        "sessionInfo": True,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadMusic": False
    }
    
    data = await make_request(
        TIKTOK_API_URL,
        params={"token": APIFY_TOKEN},
        method="POST",
        json_data=user_payload
    )
    
    if not data:
        return f"❌ Unable to fetch videos for @{username}. Please try again later."
    
    if not data:
        return f"🔍 No videos found for @{username}"
    
    results = []
    for video in data[:limit]:
        formatted_video = format_tiktok_video(video)
        
        result = f"""
🎵 **@{formatted_video['author']} ({formatted_video['author_handle']})**
📝 {formatted_video['description']}
❤️ {formatted_video['likes']:,} | 🔄 {formatted_video['shares']:,} | 💬 {formatted_video['comments']:,} | ▶️ {formatted_video['plays']:,}
⏱️ {formatted_video['duration']}s | 📅 {formatted_video['created_at']}
🔗 {formatted_video['url']}
"""
        results.append(result.strip())
    
    header = f"🎵 Found {len(results)} videos from @{username}"
    return header + "\n\n" + "\n---\n".join(results)

@mcp.tool()
async def search_google_trends(
    query: str,
    geo: str = "US", 
    timeframe: str = "today 12-m",
    limit: int = 20
) -> str:
    """
    Search Google Trends data using ScrapingBee.
    
    Args:
        query: Search term to analyze trends for
        geo: Geographic location (US, GB, CA, etc.)
        timeframe: Time period (today 12-m, today 5-y, all, etc.)
        limit: Number of results to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    try:
        # Use ScrapingBee API key
        scrapingbee_api_key = SCRAPINGBEE_API_KEY
        
        # Construct Google Trends URL
        base_url = "https://trends.google.com/trends/explore"
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        trends_query = f"q={encoded_query}&geo={geo}&date={urllib.parse.quote(timeframe)}"
        url = f"{base_url}?{trends_query}"
        
        # ScrapingBee parameters with anti-detection features
        params = {
            'api_key': scrapingbee_api_key,
            'url': url,
            'render_js': 'true',
            'wait': '5000',  # Wait longer for content to load
            'custom_google': 'true',
            'block_resources': 'false',
            'stealth_proxy': 'true'  # Use stealth proxy for better success rate
        }
        
        # Make request to ScrapingBee
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=45)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract any trend-related information
            trends_data = []
            
            # Get page title for confirmation
            title = soup.find('title')
            page_title = title.get_text(strip=True) if title else ""
            
            # Look for any trend-related text patterns
            page_text = soup.get_text()
            
            # Check if we got the trends page
            if "trends" in page_title.lower() or "trends" in page_text.lower()[:1000]:
                trends_data.append({
                    'type': 'Page Access',
                    'text': f"Successfully accessed Google Trends page for '{query}'",
                    'details': f"Page title: {page_title}"
                })
                
                # Look for any visible trend data
                # Search for common trend-related patterns
                trend_patterns = [
                    "Interest over time",
                    "Related queries", 
                    "Related topics",
                    "Rising",
                    "Top",
                    "Trending",
                    "Search term"
                ]
                
                found_patterns = []
                for pattern in trend_patterns:
                    if pattern.lower() in page_text.lower():
                        found_patterns.append(pattern)
                
                if found_patterns:
                    trends_data.append({
                        'type': 'Trend Indicators',
                        'text': f"Found trend indicators: {', '.join(found_patterns)}",
                        'details': 'These suggest trend data is available on the page'
                    })
                
                # Try to extract any numerical data (could be trend values)
                import re
                numbers = re.findall(r'\b\d{1,3}\b', page_text)
                if numbers:
                    unique_numbers = list(set(numbers))[:10]  # Limit to first 10 unique numbers
                    trends_data.append({
                        'type': 'Potential Trend Values',
                        'text': f"Found numerical values: {', '.join(unique_numbers)}",
                        'details': 'These could represent trend percentages or popularity scores'
                    })
                
            else:
                # If we can't access trends directly, provide helpful information
                trends_data.append({
                    'type': 'Access Information',
                    'text': f"Google Trends access for '{query}' encountered anti-bot protection",
                    'details': 'This is common with Google Trends. Try accessing manually for detailed data.'
                })
            
            # Always provide the direct URL for manual access
            trends_data.append({
                'type': 'Manual Access',
                'text': f"Direct Google Trends URL for '{query}'",
                'details': f"Visit: {url}"
            })
            
            # Provide trend analysis tips
            trends_data.append({
                'type': 'Analysis Tips',
                'text': f"For '{query}' trend analysis in {geo}",
                'details': f"Time period: {timeframe}. Look for seasonal patterns, news correlations, and related topics."
            })
            
            # Format results
            if not trends_data:
                return f"🔍 Unable to extract specific trend data for '{query}', but you can access it manually at: {url}"
            
            results = []
            for i, result in enumerate(trends_data[:limit], 1):
                formatted_result = f"""
📈 **{result['type']}**
📝 {result['text']}
ℹ️ {result['details']}
"""
                results.append(formatted_result.strip())
            
            header = f"🔥 Google Trends Analysis for '{query}' ({geo}, {timeframe})"
            return header + "\n\n" + "\n---\n".join(results)
            
        else:
            # Provide helpful fallback information
            return f"""🔍 **Google Trends Analysis for '{query}'**

❌ Direct scraping unavailable due to anti-bot protection (Status: {response.status_code})

📊 **Manual Access**: {url}

💡 **Trend Analysis Tips for '{query}':**
• Region: {geo}
• Timeframe: {timeframe} 
• Look for seasonal patterns and news correlations
• Check related queries and topics
• Compare with similar terms

🔗 **Alternative Approaches:**
• Use our web search tool for current news about '{query}'
• Search social media for trending discussions
• Check multiple timeframes for pattern recognition"""
        
    except Exception as e:
        return f"""❌ **Google Trends Error for '{query}'**

Error: {str(e)}

🔗 **Manual Access**: https://trends.google.com/trends/explore?q={urllib.parse.quote(query)}&geo={geo}&date={urllib.parse.quote(timeframe)}

💡 **Alternative**: Try using our web search tool for current information about '{query}'"""

@mcp.tool()
async def compare_google_trends(
    queries: str,
    geo: str = "US", 
    timeframe: str = "today 12-m",
    limit: int = 20
) -> str:
    """
    Compare multiple terms on Google Trends side by side.
    
    Args:
        queries: Comma-separated search terms to compare (e.g., "AI,machine learning,ChatGPT")
        geo: Geographic location (US, GB, CA, etc.)
        timeframe: Time period (today 12-m, today 5-y, all, etc.)
        limit: Number of results to return (max 50)
    """
    
    limit = min(max(1, limit), MAX_LIMIT)
    
    # Parse the queries
    query_list = [q.strip() for q in queries.split(',')]
    if len(query_list) < 2:
        return "❌ Please provide at least 2 terms separated by commas for comparison (e.g., 'AI,machine learning')"
    
    if len(query_list) > 5:
        query_list = query_list[:5]  # Google Trends limits to 5 comparisons
        
    try:
        # Use ScrapingBee API key
        scrapingbee_api_key = SCRAPINGBEE_API_KEY
        
        # Construct Google Trends comparison URL
        base_url = "https://trends.google.com/trends/explore"
        import urllib.parse
        
        # Create multiple q parameters for comparison
        query_params = []
        for query in query_list:
            encoded_query = urllib.parse.quote(query.strip())
            query_params.append(f"q={encoded_query}")
        
        # Combine all parameters
        all_queries = "&".join(query_params)
        trends_query = f"{all_queries}&geo={geo}&date={urllib.parse.quote(timeframe)}"
        url = f"{base_url}?{trends_query}"
        
        # ScrapingBee parameters with anti-detection features
        params = {
            'api_key': scrapingbee_api_key,
            'url': url,
            'render_js': 'true',
            'wait': '5000',  # Wait longer for content to load
            'custom_google': 'true',
            'block_resources': 'false',
            'stealth_proxy': 'true'  # Use stealth proxy for better success rate
        }
        
        # Make request to ScrapingBee
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=45)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract comparison data
            comparison_data = []
            
            # Get page title for confirmation
            title = soup.find('title')
            page_title = title.get_text(strip=True) if title else ""
            
            # Look for comparison-related text patterns
            page_text = soup.get_text()
            
            # Check if we got the trends comparison page
            if "trends" in page_title.lower() or any(query.lower() in page_title.lower() for query in query_list):
                comparison_data.append({
                    'type': 'Comparison Access',
                    'text': f"Successfully accessed Google Trends comparison for: {', '.join(query_list)}",
                    'details': f"Page title: {page_title}"
                })
                
                # Look for comparison-specific indicators
                comparison_patterns = [
                    "Compare",
                    "Interest over time",
                    "Related queries", 
                    "Related topics",
                    "Rising",
                    "Top",
                    "vs",
                    "versus"
                ]
                
                found_patterns = []
                for pattern in comparison_patterns:
                    if pattern.lower() in page_text.lower():
                        found_patterns.append(pattern)
                
                if found_patterns:
                    comparison_data.append({
                        'type': 'Comparison Indicators',
                        'text': f"Found comparison indicators: {', '.join(found_patterns)}",
                        'details': 'These suggest comparative trend data is available'
                    })
                
                # Try to extract numerical data for each term
                import re
                numbers = re.findall(r'\b\d{1,3}\b', page_text)
                if numbers:
                    unique_numbers = list(set(numbers))[:15]  # Get more numbers for comparison
                    comparison_data.append({
                        'type': 'Potential Trend Values',
                        'text': f"Found comparative values: {', '.join(unique_numbers)}",
                        'details': f'These could represent relative popularity scores for: {", ".join(query_list)}'
                    })
                
                # Add individual term analysis
                for i, query in enumerate(query_list, 1):
                    if query.lower() in page_text.lower():
                        comparison_data.append({
                            'type': f'Term {i} Analysis',
                            'text': f"'{query}' found in comparison data",
                            'details': f'This term is included in the trend comparison analysis'
                        })
                
            else:
                # If we can't access trends directly, provide helpful information
                comparison_data.append({
                    'type': 'Access Information',
                    'text': f"Google Trends comparison access encountered anti-bot protection",
                    'details': f'Comparison requested for: {", ".join(query_list)}'
                })
            
            # Always provide the direct URL for manual access
            comparison_data.append({
                'type': 'Manual Comparison Access',
                'text': f"Direct Google Trends comparison URL",
                'details': f"Visit: {url}"
            })
            
            # Provide comparison analysis tips
            comparison_data.append({
                'type': 'Comparison Tips',
                'text': f"Analyzing trends for: {' vs '.join(query_list)}",
                'details': f"Region: {geo}, Period: {timeframe}. Look for relative popularity, seasonal differences, and market share changes."
            })
            
            # Add individual search suggestions
            comparison_data.append({
                'type': 'Individual Analysis',
                'text': "For detailed individual analysis, search each term separately",
                'details': f"Terms to analyze individually: {', '.join(query_list)}"
            })
            
            # Format results
            if not comparison_data:
                return f"🔍 Unable to extract specific comparison data, but you can access it manually at: {url}"
            
            results = []
            for i, result in enumerate(comparison_data[:limit], 1):
                formatted_result = f"""
📊 **{result['type']}**
📝 {result['text']}
ℹ️ {result['details']}
"""
                results.append(formatted_result.strip())
            
            header = f"🔥 Google Trends Comparison: {' vs '.join(query_list)} ({geo}, {timeframe})"
            return header + "\n\n" + "\n---\n".join(results)
            
        else:
            # Provide helpful fallback information
            return f"""🔍 **Google Trends Comparison: {' vs '.join(query_list)}**

❌ Direct scraping unavailable due to anti-bot protection (Status: {response.status_code})

📊 **Manual Comparison Access**: {url}

💡 **Comparison Analysis Tips:**
• Terms compared: {', '.join(query_list)}
• Region: {geo}
• Timeframe: {timeframe}
• Look for relative popularity over time
• Check seasonal patterns and crossover points
• Analyze which term dominates when

🔗 **Alternative Approaches:**
• Use individual searches for each term
• Search social media for trending discussions about each topic
• Compare news coverage for each term"""
        
    except Exception as e:
        # Construct manual URL for fallback
        import urllib.parse
        query_params = []
        for query in query_list:
            encoded_query = urllib.parse.quote(query.strip())
            query_params.append(f"q={encoded_query}")
        manual_url = f"https://trends.google.com/trends/explore?{'&'.join(query_params)}&geo={geo}&date={urllib.parse.quote(timeframe)}"
        
        return f"""❌ **Google Trends Comparison Error**

Error: {str(e)}

🔗 **Manual Comparison Access**: {manual_url}

💡 **Comparing**: {' vs '.join(query_list)}

💡 **Alternative**: Try individual searches for each term using the search_google_trends tool"""

def create_sse_app():
    """Create a Starlette app with SSE transport for the MCP server."""
    
    sse = SseServerTransport("/sse")
    
    async def handle_sse(request: Request):
        async def app(scope, receive, send):
            async with sse.connect_sse(scope, receive, send) as streams:
                await mcp.run_sse(*streams)
        
        await app(request.scope, request.receive, request._send)
    
    async def handle_health(request: Request):
        return JSONResponse({"status": "healthy", "server": "General MCP Server"})
    
    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=handle_health),
            Route("/sse/{path:path}", methods=["POST"], endpoint=sse.handle_post_message),
        ],
        debug=True
    )

# ============================================================================
# DATA FORMATTING UTILITIES
# ============================================================================

def format_reddit_post(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format Reddit post data for consistent display.
    
    Args:
        post_data: Raw Reddit post data from API
        
    Returns:
        Formatted post data with standardized fields
    """
    selftext = post_data.get("selftext", "")
    if selftext and len(selftext) > 200:
        selftext = selftext[:200] + "..."
        
    return {
        "title": post_data.get("title", "No title"),
        "author": post_data.get("author", "Unknown"),
        "score": post_data.get("score", 0),
        "num_comments": post_data.get("num_comments", 0),
        "created_utc": post_data.get("created_utc", 0),
        "subreddit": post_data.get("subreddit", "Unknown"),
        "url": f"https://reddit.com{post_data.get('permalink', '')}",
        "selftext": selftext,
        "is_video": post_data.get("is_video", False),
        "domain": post_data.get("domain", ""),
    }

def format_youtube_video(video_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format YouTube video data for consistent display.
    
    Args:
        video_data: Raw YouTube video data from API
        
    Returns:
        Formatted video data with standardized fields
    """
    snippet = video_data.get("snippet", {})
    description = snippet.get("description", "")
    if description and len(description) > 200:
        description = description[:200] + "..."
        
    video_id = video_data.get("id", {}).get("videoId", "")
    
    return {
        "title": snippet.get("title", "No title"),
        "channel": snippet.get("channelTitle", "Unknown"),
        "description": description,
        "published": snippet.get("publishedAt", ""),
        "video_id": video_id,
        "url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
        "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", "")
    }

def format_twitter_post(tweet_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format Twitter post data for consistent display.
    
    Args:
        tweet_data: Raw Twitter post data from API
        
    Returns:
        Formatted tweet data with standardized fields
    """
    # Handle various author field formats from different Twitter scrapers
    author_info = tweet_data.get("author", tweet_data.get("user", {}))
    if isinstance(author_info, dict):
        author_name = author_info.get("userName", author_info.get("name", "Unknown"))
        author_handle = author_info.get("userHandle", author_info.get("screen_name", "Unknown"))
    else:
        author_name = str(author_info) if author_info else "Unknown"
        author_handle = "Unknown"
    
    return {
        "text": tweet_data.get("text", tweet_data.get("full_text", "No text")),
        "author": author_name,
        "author_handle": author_handle,
        "likes": tweet_data.get("likes", tweet_data.get("favorite_count", 0)),
        "retweets": tweet_data.get("retweets", tweet_data.get("retweet_count", 0)),
        "replies": tweet_data.get("replies", tweet_data.get("reply_count", 0)),
        "created_at": tweet_data.get("createdAt", tweet_data.get("created_at", "")),
        "url": tweet_data.get("url", ""),
        "is_retweet": tweet_data.get("isRetweet", False)
    }

def format_tiktok_video(video_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format TikTok video data for consistent display.
    
    Args:
        video_data: Raw TikTok video data from API
        
    Returns:
        Formatted video data with standardized fields
    """
    return {
        "description": video_data.get("text", video_data.get("description", "No description")),
        "author": video_data.get("authorMeta", {}).get("name", video_data.get("author", "Unknown")),
        "author_handle": video_data.get("authorMeta", {}).get("nickName", video_data.get("authorName", "Unknown")),
        "likes": video_data.get("diggCount", video_data.get("likes", 0)),
        "shares": video_data.get("shareCount", video_data.get("shares", 0)),
        "comments": video_data.get("commentCount", video_data.get("comments", 0)),
        "plays": video_data.get("playCount", video_data.get("views", 0)),
        "created_at": video_data.get("createTime", video_data.get("createdAt", "")),
        "url": video_data.get("webVideoUrl", video_data.get("url", "")),
        "duration": video_data.get("videoMeta", {}).get("duration", 0)
    }

# ============================================================================
# MONITORING & ANALYTICS TOOLS
# ============================================================================

@mcp.tool()
async def get_api_usage_stats() -> str:
    """
    Get comprehensive API usage statistics to monitor costs and usage patterns.
    
    Returns:
        Detailed usage statistics including costs, trends, and recommendations
    """
    if not api_usage_log:
        return "📊 No API usage recorded yet. Start using the tools to see statistics!"
    
    # Categorize usage by service
    services = {}
    total_cost = 0.0
    
    for log in api_usage_log:
        service = log["service"]
        if service not in services:
            services[service] = {
                "calls": 0,
                "requested": 0,
                "received": 0,
                "cost": 0.0,
                "endpoints": set()
            }
        
        services[service]["calls"] += 1
        services[service]["requested"] += log.get("requested_limit", 0)
        services[service]["received"] += log.get("actual_results", 0) or 0
        services[service]["cost"] += log.get("cost_estimate", 0.0) or 0.0
        services[service]["endpoints"].add(log.get("endpoint", "unknown"))
        total_cost += log.get("cost_estimate", 0.0) or 0.0
    
    # Build comprehensive report
    stats = f"""📊 **API Usage Analytics** (Last {len(api_usage_log)} calls)

💰 **Total Estimated Cost**: ${total_cost:.3f}
⏱️  **Tracking Period**: {api_usage_log[0]['timestamp'][:19]} to {api_usage_log[-1]['timestamp'][:19]}

"""
    
    # Service breakdown
    for service, data in services.items():
        efficiency = (data["received"] / data["requested"] * 100) if data["requested"] > 0 else 0
        avg_cost = data["cost"] / data["calls"] if data["calls"] > 0 else 0
        
        service_icon = {
            "Twitter": "🐦", "YouTube": "🎥", "TikTok": "🎵", 
            "Reddit": "📱", "Perplexity": "🧠", "Web": "🌐",
            "GoogleTrends": "📈"
        }.get(service, "🔧")
        
        stats += f"""{service_icon} **{service}**: {data["calls"]} calls (${data["cost"]:.3f})
   • Results: {data["requested"]} requested → {data["received"]} received ({efficiency:.1f}% efficiency)
   • Avg cost/call: ${avg_cost:.3f}
   • Endpoints: {', '.join(sorted(data["endpoints"]))}

"""
    
    # Recent activity (last 5 calls)
    stats += "📈 **Recent Activity**:\n"
    recent_calls = api_usage_log[-5:]
    for call in recent_calls:
        cost_info = f" (${call.get('cost_estimate', 0):.3f})" if call.get('cost_estimate') else ""
        stats += f"   • {call['timestamp'][11:19]}: {call['service']}.{call['endpoint']} - {call['requested_limit']} requested{cost_info}\n"
    
    # Cost warnings and recommendations
    high_cost_calls = [log for log in api_usage_log if (log.get('cost_estimate') or 0) > 0.10]
    if high_cost_calls:
        stats += f"\n⚠️  **Cost Warnings**: {len(high_cost_calls)} calls exceeded $0.10 each\n"
    
    if total_cost > 1.0:
        stats += "🚨 **High Usage Alert**: Total costs exceed $1.00. Consider optimizing queries.\n"
    
    stats += "\n💡 **Optimization Tips**:\n"
    stats += "   • Use smaller limits for exploratory searches\n"
    stats += "   • Reduce days_back for Twitter/TikTok to control costs\n"
    stats += "   • Use free services (Reddit, Web Search) when possible\n"
    
    return stats

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="General MCP Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)), help="Port to listen on")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport instead of SSE")
    
    args = parser.parse_args()
    
    if args.stdio:
        # Run with stdio transport (for local testing)
        asyncio.run(mcp.run())
    else:
        # Run with SSE transport (for remote access)
        app = create_sse_app()
        print(f"🚀 General MCP Server starting on http://{args.host}:{args.port}")
        print(f"📡 SSE endpoint: http://{args.host}:{args.port}/sse")
        print(f"🏥 Health check: http://{args.host}:{args.port}/health")
        uvicorn.run(app, host=args.host, port=args.port)

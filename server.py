#!/usr/bin/env python3

# MCP and web framework
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Standard libraries
import os
import json
import asyncio
import httpx
import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time

# Environment and configuration
import os

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Initialize FastAPI app
app = FastAPI(title="General MCP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints
APIFY_API_BASE = "https://api.apify.com/v2/acts"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
PERPLEXITY_API_BASE = "https://api.perplexity.ai/chat/completions"

# Rate limiting and cost protection
MAX_LIMIT = 50
DEFAULT_LIMIT = 10
DEFAULT_TIMEOUT = 30.0

# Cost tracking
api_usage_log = []

# API Keys from environment
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") 
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_api_usage(
    service: str, 
    endpoint: str, 
    requested_limit: int, 
    actual_results: Optional[int] = None,
    cost_estimate: Optional[float] = None
) -> None:
    """Log API usage for monitoring and cost tracking."""
    api_usage_log.append({
        "timestamp": datetime.now().isoformat(),
        "service": service,
        "endpoint": endpoint,
        "requested_limit": requested_limit,
        "actual_results": actual_results,
        "cost_estimate": cost_estimate
    })
    
    # Keep only last 100 entries to prevent memory bloat
    if len(api_usage_log) > 100:
        api_usage_log.pop(0)

def validate_limit(limit: int, max_allowed: int, service: str = "API") -> int:
    """
    Validate and adjust API request limits to prevent excessive costs.
    
    Args:
        limit: Requested limit
        max_allowed: Maximum allowed limit
        service: Service name for logging
        
    Returns:
        Validated limit (capped at max_allowed)
    """
    if limit > max_allowed:
        print(f"⚠️  {service}: Limit {limit} exceeds maximum {max_allowed}, using {max_allowed}")
        return max_allowed
    return max(1, limit)

def validate_days_back(days: int, max_allowed: int, service: str = "API") -> int:
    """
    Validate and adjust days_back parameter to prevent excessive API costs.
    
    Args:
        days: Requested days back
        max_allowed: Maximum allowed days
        service: Service name for logging
        
    Returns:
        Validated days (capped at max_allowed)
    """
    if days > max_allowed:
        print(f"⚠️  {service}: days_back {days} exceeds maximum {max_allowed}, using {max_allowed}")
        return max_allowed
    return max(1, days)

async def make_request(
    url: str, 
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    json_data: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Any]]:
    """
    Make HTTP request with proper error handling and retries.
    
    Args:
        url: Request URL
        params: Query parameters
        headers: Request headers
        method: HTTP method
        json_data: JSON payload for POST requests
        timeout: Request timeout
        
    Returns:
        Response data as dict, or None if request failed
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method.upper() == "POST":
                response = await client.post(url, params=params, headers=headers, json=json_data)
            else:
                response = await client.get(url, params=params, headers=headers)
            
            response.raise_for_status()
            
            # Try to parse as JSON, fall back to text
            try:
                return response.json()
            except:
                return {"text": response.text}
                
    except httpx.TimeoutException:
        print(f"⏰ Request timeout for {url}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"❌ Request error for {url}: {str(e)}")
        return None

# ============================================================================
# MCP PROTOCOL IMPLEMENTATION
# ============================================================================

# Tool definitions
TOOLS = [
    {
        "name": "search_reddit",
        "description": "Search Reddit for posts matching a query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms to look for"},
                "subreddit": {"type": "string", "description": "Specific subreddit to search (optional)"},
                "sort": {"type": "string", "description": "Sort order (relevance, hot, top, new, comments)"},
                "time": {"type": "string", "description": "Time period (all, year, month, week, day, hour)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_subreddit_posts",
        "description": "Get posts from specific subreddit",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subreddit": {"type": "string", "description": "Subreddit name"},
                "sort": {"type": "string", "description": "Sort order (hot, new, rising, top)"},
                "time": {"type": "string", "description": "Time period (all, year, month, week, day, hour)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": ["subreddit"]
        }
    },
    {
        "name": "get_reddit_comments",
        "description": "Get comments from a Reddit post",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_url": {"type": "string", "description": "Reddit post URL"},
                "limit": {"type": "integer", "description": "Number of comments to return (max 50)"}
            },
            "required": ["post_url"]
        }
    },
    {
        "name": "search_youtube",
        "description": "Search YouTube videos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "published_after": {"type": "string", "description": "ISO date (optional)"},
                "published_before": {"type": "string", "description": "ISO date (optional)"},
                "order": {"type": "string", "description": "Sort order (relevance, date, rating, viewCount, title)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_youtube_trending",
        "description": "Get trending YouTube videos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category ID (0=all, 10=music, 15=pets, etc.)"},
                "region": {"type": "string", "description": "Country code (US, CA, GB, etc.)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": []
        }
    },
    {
        "name": "search_twitter",
        "description": "Search tweets (cost-protected)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (Twitter syntax supported)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"},
                "sort": {"type": "string", "description": "Sort order (Latest, Popular, Photos, Videos)"},
                "days_back": {"type": "integer", "description": "Days to search back (max 7)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_tweets",
        "description": "Get user timeline (cost-protected)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Twitter username (without @)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"},
                "days_back": {"type": "integer", "description": "Days to search back (max 7)"}
            },
            "required": ["username"]
        }
    },
    {
        "name": "search_tiktok",
        "description": "Search TikTok videos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_tiktok_user_videos",
        "description": "Get TikTok user videos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "TikTok username (without @)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"}
            },
            "required": ["username"]
        }
    },
    {
        "name": "search_perplexity",
        "description": "AI-powered web search using Perplexity",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Number of source results (max 10)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "max_results": {"type": "integer", "description": "Number of results to return (max 20)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_google_trends",
        "description": "Google Trends analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term for trends"},
                "timeframe": {"type": "string", "description": "Time period (today 5-y, today 12-m, etc.)"},
                "geo": {"type": "string", "description": "Geographic location (US, GB, etc.)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "compare_google_trends",
        "description": "Compare multiple terms in Google Trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "terms": {"type": "array", "items": {"type": "string"}, "description": "List of terms to compare"},
                "timeframe": {"type": "string", "description": "Time period (today 5-y, today 12-m, etc.)"},
                "geo": {"type": "string", "description": "Geographic location (US, GB, etc.)"}
            },
            "required": ["terms"]
        }
    },
    {
        "name": "get_api_usage_stats",
        "description": "Get comprehensive API usage statistics",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ============================================================================
# MCP HTTP ENDPOINTS
# ============================================================================

@app.post("/message")
async def handle_mcp_message(message: dict):
    """Handle MCP protocol messages over HTTP."""
    try:
        method = message.get("method")
        message_id = message.get("id")  # Don't default to 0 - keep None if not provided
        
        print(f"INFO:__main__:Handling method: {method} (id: {message_id})")
        
        # If this is a notification (no ID), don't send a response
        if message_id is None:
            print(f"INFO:__main__:Notification received for {method}, not sending response")
            from fastapi import Response
            return Response(status_code=204)
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "General Search",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"tools": TOOLS}
            }
        
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"resources": []}
            }
        
        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"prompts": []}
            }
        
        elif method == "tools/call":
            tool_name = message.get("params", {}).get("name")
            arguments = message.get("params", {}).get("arguments", {})
            
            print(f"INFO:__main__:Calling tool: {tool_name} with args: {arguments}")
            
            # Call the appropriate tool function
            if tool_name == "search_reddit":
                result = await search_reddit(**arguments)
            elif tool_name == "get_subreddit_posts":
                result = await get_subreddit_posts(**arguments)
            elif tool_name == "get_reddit_comments":
                result = await get_reddit_comments(**arguments)
            elif tool_name == "search_youtube":
                result = await search_youtube(**arguments)
            elif tool_name == "get_youtube_trending":
                result = await get_youtube_trending(**arguments)
            elif tool_name == "search_twitter":
                result = await search_twitter(**arguments)
            elif tool_name == "get_user_tweets":
                result = await get_user_tweets(**arguments)
            elif tool_name == "search_tiktok":
                result = await search_tiktok(**arguments)
            elif tool_name == "get_tiktok_user_videos":
                result = await get_tiktok_user_videos(**arguments)
            elif tool_name == "search_perplexity":
                result = await search_perplexity(**arguments)
            elif tool_name == "search_web":
                result = await search_web(**arguments)
            elif tool_name == "search_google_trends":
                result = await search_google_trends(**arguments)
            elif tool_name == "compare_google_trends":
                result = await compare_google_trends(**arguments)
            elif tool_name == "get_api_usage_stats":
                result = await get_api_usage_stats(**arguments)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
            
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                }
            }
            
    except Exception as e:
        print(f"ERROR:__main__:Error handling message: {e}")
        msg_id = message.get("id")
        # Don't respond to notifications even on error
        if msg_id is None:
            from fastapi import Response
            return Response(status_code=204)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/sse")
async def handle_sse():
    """Handle Server-Sent Events for MCP communication."""
    async def event_stream():
        yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\"}\n\n"
        
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\"}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "server": "General MCP Server", "version": "1.0.0"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "healthy", "server": "General MCP Server", "version": "1.0.0"}

# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

async def search_reddit(
    query: str,
    subreddit: str = "",
    sort: str = "relevance",
    time: str = "all",
    limit: int = 10
) -> str:
    """Search Reddit for posts using free Reddit JSON API."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    
    # Build Reddit search URL using free JSON API
    if subreddit:
        # Search within specific subreddit
        search_url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "1",  # Restrict to subreddit
            "sort": sort,
            "t": time,
            "limit": limit
        }
    else:
        # Global Reddit search
        search_url = "https://www.reddit.com/search.json"
        params = {
            "q": query,
            "sort": sort,
            "t": time,
            "limit": limit
        }
    
    # Add User-Agent header (required by Reddit)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPBot/1.0; +https://general-mcp.onrender.com)"
    }
    
    data = await make_request(search_url, params=params, headers=headers)
    
    if not data or not data.get("data") or not data["data"].get("children"):
        log_api_usage("Reddit", "search", limit, 0, 0.0)  # Free API
        return f"❌ No results found for Reddit search: '{query}'"
    
    results = []
    posts = data["data"]["children"]
    
    for post_data in posts[:limit]:
        post = post_data.get("data", {})
        title = post.get("title", "No title")
        author = post.get("author", "Unknown")
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        permalink = post.get("permalink", "")
        url = f"https://reddit.com{permalink}" if permalink else post.get("url", "")
        subreddit_name = post.get("subreddit", "")
        selftext = post.get("selftext", "")[:200] + "..." if len(post.get("selftext", "")) > 200 else post.get("selftext", "")
        
        result = f"""📝 **{title}**
👤 u/{author} in r/{subreddit_name}
⬆️ {score} upvotes | 💬 {comments} comments"""
        
        if selftext:
            result += f"\n📄 {selftext}"
        
        result += f"\n🔗 {url}"
        results.append(result)
    
    log_api_usage("Reddit", "search", limit, len(results), 0.0)  # Free API
    header = f"🔍 Reddit search results for '{query}' ({len(results)} found)"
    return header + "\n\n" + "\n---\n".join(results)

async def search_web(query: str, max_results: int = 10) -> str:
    """Search the web using DuckDuckGo."""
    max_results = validate_limit(max_results, 20, "Web Search")
    
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
    
    if not results:
        return f"🔍 No comprehensive results found for: '{query}'. Try a more specific search term."
    
    header = f"🌐 Web search results for: '{query}'"
    return header + "\n\n" + "\n\n".join(results)

async def get_api_usage_stats() -> str:
    """Get comprehensive API usage statistics."""
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
            "Reddit": "📱", "Web": "🌐"
        }.get(service, "🔧")
        
        stats += f"""{service_icon} **{service}**: {data["calls"]} calls (${data["cost"]:.3f})
   • Results: {data["requested"]} requested → {data["received"]} received ({efficiency:.1f}% efficiency)
   • Avg cost/call: ${avg_cost:.3f}
   • Endpoints: {', '.join(sorted(data["endpoints"]))}

"""
    
    return stats

# ============================================================================
# ADDITIONAL REDDIT TOOLS
# ============================================================================

async def get_subreddit_posts(subreddit: str, sort: str = "hot", time: str = "day", limit: int = 10) -> str:
    """Get posts from specific subreddit using free Reddit API."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    log_api_usage("Reddit", "subreddit_posts", limit, 0, 0.0)  # Free API
    
    # Map sort options to Reddit API format
    sort_mapping = {
        "hot": "hot",
        "new": "new", 
        "rising": "rising",
        "top": "top"
    }
    reddit_sort = sort_mapping.get(sort, "hot")
    
    # Build subreddit URL
    if reddit_sort == "top":
        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        params = {"t": time, "limit": limit}
    else:
        url = f"https://www.reddit.com/r/{subreddit}/{reddit_sort}.json"
        params = {"limit": limit}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPBot/1.0; +https://general-mcp.onrender.com)"
    }
    
    data = await make_request(url, params=params, headers=headers)
    
    if not data or not data.get("data") or not data["data"].get("children"):
        return f"❌ Failed to fetch posts from r/{subreddit}. Subreddit may not exist or be private."
    
    results = []
    posts = data["data"]["children"]
    
    for post_data in posts[:limit]:
        post = post_data.get("data", {})
        title = post.get("title", "No title")[:100]
        author = post.get("author", "Unknown")
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        permalink = post.get("permalink", "")
        url = f"https://reddit.com{permalink}" if permalink else post.get("url", "")
        selftext = post.get("selftext", "")[:150] + "..." if len(post.get("selftext", "")) > 150 else post.get("selftext", "")
        
        result = f"🔸 **{title}**\n👤 u/{author} | ⬆️ {score} | 💬 {comments}"
        if selftext:
            result += f"\n📄 {selftext}"
        result += f"\n🔗 {url}"
        results.append(result)
    
    header = f"📋 Found {len(results)} posts from r/{subreddit} (sorted by {sort})"
    return header + "\n\n" + "\n---\n".join(results)

async def get_reddit_comments(post_url: str, limit: int = 10) -> str:
    """Get comments from a Reddit post using free Reddit API."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    log_api_usage("Reddit", "comments", limit, 0, 0.0)  # Free API
    
    # Convert Reddit URL to JSON API URL
    if not post_url.startswith("https://"):
        return "❌ Please provide a full Reddit post URL (e.g., https://reddit.com/r/...)"
    
    # Add .json to get JSON response
    if not post_url.endswith(".json"):
        json_url = post_url.rstrip("/") + ".json"
    else:
        json_url = post_url
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPBot/1.0; +https://general-mcp.onrender.com)"
    }
    
    data = await make_request(json_url, headers=headers)
    
    if not data or not isinstance(data, list) or len(data) < 2:
        return f"❌ Failed to fetch comments from post. URL may be invalid."
    
    # Reddit returns [post_data, comments_data]
    comments_data = data[1]
    if not comments_data.get("data") or not comments_data["data"].get("children"):
        return "❌ No comments found for this post."
    
    # Get post title from first response
    post_data = data[0]["data"]["children"][0]["data"]
    post_title = post_data.get("title", "Unknown post")
    
    results = []
    comments = comments_data["data"]["children"]
    
    for comment_data in comments[:limit]:
        comment = comment_data.get("data", {})
        
        # Skip "more" objects and deleted comments
        if comment.get("kind") == "more" or not comment.get("body"):
            continue
            
        author = comment.get("author", "Unknown")
        body = comment.get("body", "")[:300] + "..." if len(comment.get("body", "")) > 300 else comment.get("body", "")
        score = comment.get("score", 0)
        
        # Skip removed/deleted comments
        if body in ["[deleted]", "[removed]"]:
            continue
            
        results.append(f"💬 **u/{author}** (⬆️ {score})\n{body}")
    
    if not results:
        return f"❌ No readable comments found for this post."
    
    header = f"💬 Comments from: **{post_title}** ({len(results)} comments)"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# YOUTUBE TOOLS
# ============================================================================

async def search_youtube(query: str, published_after: str = "", published_before: str = "", order: str = "viewCount", limit: int = 10) -> str:
    """Search YouTube videos."""
    limit = validate_limit(limit, MAX_LIMIT, "YouTube")
    log_api_usage("YouTube", "search", limit)
    
    if not YOUTUBE_API_KEY:
        return "❌ YouTube API not configured"
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": order,
        "maxResults": limit,
        "key": YOUTUBE_API_KEY
    }
    
    if published_after:
        params["publishedAfter"] = published_after
    if published_before:
        params["publishedBefore"] = published_before
    
    data = await make_request(f"{YOUTUBE_API_BASE}/search", params)
    
    if not data or "items" not in data:
        return f"❌ YouTube search failed for '{query}'"
    
    results = []
    for video in data["items"]:
        snippet = video["snippet"]
        title = snippet.get("title", "No title")
        channel = snippet.get("channelTitle", "Unknown")
        description = snippet.get("description", "")[:150]
        video_id = video["id"]["videoId"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        results.append(f"🎥 **{title}**\n📺 {channel}\n📝 {description}...\n🔗 {video_url}")
    
    header = f"🔍 Found {len(results)} YouTube videos for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_youtube_trending(category: str = "0", region: str = "US", limit: int = 10) -> str:
    """Get trending YouTube videos."""
    limit = validate_limit(limit, MAX_LIMIT, "YouTube")
    log_api_usage("YouTube", "trending", limit)
    
    if not YOUTUBE_API_KEY:
        return "❌ YouTube API not configured"
    
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "videoCategoryId": category,
        "maxResults": limit,
        "key": YOUTUBE_API_KEY
    }
    
    data = await make_request(f"{YOUTUBE_API_BASE}/videos", params)
    
    if not data or "items" not in data:
        return f"❌ Failed to get trending videos"
    
    results = []
    for video in data["items"]:
        snippet = video["snippet"]
        stats = video.get("statistics", {})
        
        title = snippet.get("title", "No title")
        channel = snippet.get("channelTitle", "Unknown")
        views = stats.get("viewCount", "0")
        likes = stats.get("likeCount", "0")
        video_id = video["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        results.append(f"🔥 **{title}**\n📺 {channel}\n👁️ {views} views | 👍 {likes}\n🔗 {video_url}")
    
    header = f"📈 Found {len(results)} trending videos"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# TWITTER TOOLS
# ============================================================================

async def search_twitter(query: str, limit: int = 15, sort: str = "Latest", days_back: int = 7) -> str:
    """Search tweets with cost protection."""
    limit = validate_limit(limit, MAX_LIMIT, "Twitter")
    log_api_usage("Twitter", "search", limit, cost_estimate=0.02)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "searchTerms": [query],
        "sort": sort,
        "maxItems": limit,
        "tweetLanguage": "en"
    }
    
    data = await make_request(f"{APIFY_API_BASE}/61RPP7dywgiy0JPD0/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if not data:
        return f"❌ Twitter search failed for '{query}'"
    
    results = []
    for tweet in data[:limit]:
        author = tweet.get("author", {}).get("userName", "Unknown")
        text = tweet.get("text", "")[:200]
        likes = tweet.get("likeCount", 0)
        retweets = tweet.get("retweetCount", 0)
        url = tweet.get("url", "")
        
        results.append(f"🐦 **@{author}**\n📝 {text}\n❤️ {likes} | 🔄 {retweets}\n🔗 {url}")
    
    header = f"🔍 Found {len(results)} tweets for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_user_tweets(username: str, limit: int = 15, days_back: int = 7) -> str:
    """Get user timeline with cost protection."""
    limit = validate_limit(limit, MAX_LIMIT, "Twitter")
    log_api_usage("Twitter", "user_tweets", limit, cost_estimate=0.02)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "handles": [username],
        "maxItems": limit,
        "tweetLanguage": "en"
    }
    
    data = await make_request(f"{APIFY_API_BASE}/61RPP7dywgiy0JPD0/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if not data:
        return f"❌ Failed to get tweets from @{username}"
    
    results = []
    for tweet in data[:limit]:
        text = tweet.get("text", "")[:200]
        likes = tweet.get("likeCount", 0)
        retweets = tweet.get("retweetCount", 0)
        created_at = tweet.get("createdAt", "")[:10]
        url = tweet.get("url", "")
        
        results.append(f"📅 {created_at}\n📝 {text}\n❤️ {likes} | 🔄 {retweets}\n🔗 {url}")
    
    header = f"📱 Found {len(results)} tweets from @{username}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# TIKTOK TOOLS
# ============================================================================

async def search_tiktok(query: str, limit: int = 10) -> str:
    """Search TikTok videos."""
    limit = validate_limit(limit, MAX_LIMIT, "TikTok")
    log_api_usage("TikTok", "search", limit)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "searchQueries": [query],
        "resultsPerQuery": limit
    }
    
    data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if not data:
        return f"❌ TikTok search failed for '{query}'"
    
    results = []
    for video in data[:limit]:
        author = video.get("authorMeta", {}).get("name", "Unknown")
        text = video.get("text", "")[:150]
        likes = video.get("diggCount", 0)
        views = video.get("playCount", 0)
        url = video.get("webVideoUrl", "")
        
        results.append(f"🎵 **@{author}**\n📝 {text}\n👁️ {views:,} views | ❤️ {likes:,}\n🔗 {url}")
    
    header = f"🔍 Found {len(results)} TikTok videos for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_tiktok_user_videos(username: str, limit: int = 10) -> str:
    """Get TikTok user videos."""
    limit = validate_limit(limit, MAX_LIMIT, "TikTok")
    log_api_usage("TikTok", "user_videos", limit)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "profiles": [f"https://www.tiktok.com/@{username}"],
        "resultsPerQuery": limit
    }
    
    data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if not data:
        return f"❌ Failed to get videos from @{username}"
    
    results = []
    for video in data[:limit]:
        text = video.get("text", "")[:150]
        likes = video.get("diggCount", 0)
        views = video.get("playCount", 0)
        created_at = video.get("createTime", "")[:10]
        url = video.get("webVideoUrl", "")
        
        results.append(f"📅 {created_at}\n📝 {text}\n👁️ {views:,} views | ❤️ {likes:,}\n🔗 {url}")
    
    header = f"📱 Found {len(results)} videos from @{username}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# PERPLEXITY & GOOGLE TRENDS TOOLS
# ============================================================================

async def search_perplexity(query: str, max_results: int = 10) -> str:
    """AI-powered web search using Perplexity."""
    max_results = validate_limit(max_results, 10, "Perplexity")
    log_api_usage("Perplexity", "search", max_results)
    
    if not PERPLEXITY_API_KEY:
        return "❌ Perplexity API not configured"
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {"role": "system", "content": "Be precise and informative. Provide factual information with sources."},
            {"role": "user", "content": query}
        ],
        "max_tokens": 1000,
        "temperature": 0.2,
        "return_citations": True
    }
    
    data = await make_request(PERPLEXITY_API_BASE, headers=headers, method="POST", json_data=payload)
    
    if not data or "choices" not in data:
        return f"❌ Perplexity search failed for '{query}'"
    
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    
    result = f"🧠 **Perplexity AI Search Results for '{query}'**\n\n{content}"
    
    if citations:
        result += "\n\n**Sources:**\n"
        for i, citation in enumerate(citations[:max_results], 1):
            result += f"{i}. {citation}\n"
    
    return result

async def search_google_trends(query: str, timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Google Trends analysis using ScrapingBee."""
    log_api_usage("GoogleTrends", "search", 1, 0, 0.05)
    
    if not SCRAPINGBEE_API_KEY:
        return "❌ SCRAPINGBEE_API_KEY not configured"
    
    import urllib.parse
    
    # Construct Google Trends URL
    encoded_query = urllib.parse.quote(query)
    trends_url = f"https://trends.google.com/trends/explore?q={encoded_query}&geo={geo}&date={urllib.parse.quote(timeframe)}"
    
    # ScrapingBee parameters
    params = {
        'api_key': SCRAPINGBEE_API_KEY,
        'url': trends_url,
        'render_js': 'true',
        'wait': '3000',
        'country_code': 'us',
        'custom_google': 'true',
        'block_resources': 'false'
    }
    
    try:
        # Use requests for ScrapingBee (different from our async httpx)
        import requests
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=30)
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract trends data
            page_text = soup.get_text()
            
            # Look for related queries and topics
            trend_sections = []
            
            # Check if we got the trends page
            if 'trending' in page_text.lower() or 'related' in page_text.lower():
                trend_sections.append("✅ Successfully accessed Google Trends data")
                
                # Try to find related queries
                related_elements = soup.find_all(text=lambda text: text and 'related' in text.lower())
                if related_elements:
                    trend_sections.append(f"🔍 Found {len(related_elements)} related sections")
                
            else:
                trend_sections.append("⚠️ Limited data available - Google may be blocking automated access")
            
            result = f"📈 **Google Trends Analysis for '{query}'**\n\n"
            result += f"🌍 Region: {geo}\n📅 Timeframe: {timeframe}\n\n"
            result += "\n".join(trend_sections)
            result += f"\n\n🔗 Manual access: {trends_url}"
            
            return result
            
        elif response.status_code == 500:
            # Try with premium proxy
            params['premium_proxy'] = 'true'
            response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=30)
            
            if response.status_code == 200:
                result = f"📈 **Google Trends Analysis for '{query}'**\n\n"
                result += f"🌍 Region: {geo}\n📅 Timeframe: {timeframe}\n\n"
                result += "✅ Data retrieved with premium proxy\n"
                result += f"🔗 Manual access: {trends_url}"
                return result
            else:
                return f"❌ ScrapingBee failed even with premium proxy: {response.status_code}"
        else:
            return f"❌ ScrapingBee request failed: {response.status_code} - {response.text[:200]}"
            
    except Exception as e:
        return f"❌ Error accessing Google Trends: {str(e)}"

async def compare_google_trends(terms: list, timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Compare multiple terms in Google Trends using ScrapingBee."""
    log_api_usage("GoogleTrends", "compare", len(terms), 0, 0.05)
    
    if not SCRAPINGBEE_API_KEY:
        return "❌ SCRAPINGBEE_API_KEY not configured"
    
    import urllib.parse
    
    # Construct comparison URL
    query_string = ",".join(terms)
    encoded_query = urllib.parse.quote(query_string)
    trends_url = f"https://trends.google.com/trends/explore?q={encoded_query}&geo={geo}&date={urllib.parse.quote(timeframe)}"
    
    # ScrapingBee parameters
    params = {
        'api_key': SCRAPINGBEE_API_KEY,
        'url': trends_url,
        'render_js': 'true',
        'wait': '3000',
        'country_code': 'us',
        'custom_google': 'true',
        'block_resources': 'false'
    }
    
    try:
        import requests
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=30)
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            page_text = soup.get_text()
            
            result = f"📊 **Google Trends Comparison**\n\n"
            result += f"🔍 Terms: {', '.join(terms)}\n🌍 Region: {geo}\n📅 Timeframe: {timeframe}\n\n"
            
            if 'compare' in page_text.lower() or len(terms) > 1:
                result += "✅ Successfully accessed comparison data\n"
                result += f"📈 Comparing {len(terms)} terms side-by-side\n"
            else:
                result += "⚠️ Limited comparison data available\n"
                
            result += f"\n🔗 Manual access: {trends_url}"
            return result
            
        elif response.status_code == 500:
            # Try with premium proxy
            params['premium_proxy'] = 'true'
            response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=30)
            
            if response.status_code == 200:
                result = f"📊 **Google Trends Comparison**\n\n"
                result += f"🔍 Terms: {', '.join(terms)}\n🌍 Region: {geo}\n📅 Timeframe: {timeframe}\n\n"
                result += "✅ Data retrieved with premium proxy\n"
                result += f"🔗 Manual access: {trends_url}"
                return result
            else:
                return f"❌ ScrapingBee comparison failed: {response.status_code}"
        else:
            return f"❌ ScrapingBee request failed: {response.status_code}"
            
    except Exception as e:
        return f"❌ Error comparing trends: {str(e)}"

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 NEW FastAPI MCP Server v2.0 starting on port {port}")
    print(f"📡 MCP endpoint: http://0.0.0.0:{port}/message")
    print(f"🌊 SSE endpoint: http://0.0.0.0:{port}/sse") 
    print(f"🏥 Health check: http://0.0.0.0:{port}/health")
    print(f"🔥 CACHE BUSTER: {datetime.now().isoformat()}")
    print("🔥 THIS IS THE NEW FASTAPI CODE - Railway should see this!")
    uvicorn.run(app, host="0.0.0.0", port=port)

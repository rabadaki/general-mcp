#!/usr/bin/env python3
"""
General MCP Server - FastAPI Web Interface

This is the FastAPI web server component of the General MCP system that provides
HTTP endpoints for social media and web tools. Works alongside mcp_stdio_server.py
which provides the MCP protocol interface for AI assistants.

Key Features:
- FastAPI web interface with automatic API documentation
- All social media tools available via REST endpoints  
- Real-time monitoring of API usage and costs
- Server-Sent Events (SSE) for live updates
- CORS enabled for web client integration

Endpoints:
- POST /message: MCP protocol message handling
- GET /health: Service health check
- GET /sse: Server-sent events stream
- GET /: API documentation

Both servers should be kept synchronized - any changes to tool functions
should be applied to both server.py and mcp_stdio_server.py.

Usage: python server.py (runs on http://localhost:8000)
"""

# MCP and web framework
from fastapi import FastAPI, HTTPException, Response
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
import pandas as pd
import re

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
DATAFORSEO_API_BASE = "https://api.dataforseo.com/v3"

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
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "sarubaito@pm.me")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "94c575f885c863f8")

# API timeout constants
APIFY_TIMEOUT = 90.0  # Apify actors need generous timeout

# Rate limiting for Google Trends
GOOGLE_TRENDS_RATE_LIMIT = {
    "requests_per_minute": 30,  # Conservative limit
    "min_interval": 2  # Minimum seconds between requests
}
last_trends_request = time.time()

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
        "description": "Get tweets from a specific user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Twitter username (without @)"},
                "limit": {"type": "integer", "description": "Number of tweets to retrieve (max 100)"},
                "days_back": {"type": "integer", "description": "Number of days back to search (max 30)"},
                "start": {"type": "string", "description": "Start date filter (YYYY-MM-DD format, optional)"},
                "end": {"type": "string", "description": "End date filter (YYYY-MM-DD format, optional)"}
            },
            "required": ["username"]
        }
    },
    {
        "name": "get_twitter_profile",
        "description": "Get Twitter user profile information with optional followers/following",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Twitter username (without @)"},
                "get_followers": {"type": "boolean", "description": "Include recent followers (default: false)"},
                "get_following": {"type": "boolean", "description": "Include recent following (default: false)"}
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
        "description": "Get TikTok user videos with optional date filtering",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "TikTok username (without @)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"},
                "start_date": {"type": "string", "description": "Optional: Start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "Optional: End date in YYYY-MM-DD format"}
            },
            "required": ["username"]
        }
    },
    {
        "name": "search_instagram",
        "description": "Search Instagram posts by hashtag or keyword",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (hashtag without #)"},
                "limit": {"type": "integer", "description": "Number of results to return (max 50)"},
                "search_type": {"type": "string", "description": "Search type: 'hashtag' or 'keyword' (default: hashtag)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_instagram_profile",
        "description": "Get Instagram user profile information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Instagram username (without @)"},
                "include_posts": {"type": "boolean", "description": "Include recent posts in response (default: false)"}
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
    },
    {
        "name": "search_serp",
        "description": "Search Google SERP data using DataForSEO API.",
        "inputSchema": {
            "type": "object", 
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to analyze"
                },
                "location": {
                    "type": "string", 
                    "description": "Location code (e.g., 'United States', 'New York', 'London')",
                    "default": "United States"
                },
                "language": {
                    "type": "string",
                    "description": "Language code (e.g., 'en', 'es', 'fr')",
                    "default": "en"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 100)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "keyword_research",
        "description": "Get keyword suggestions and search volume data using DataForSEO.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords to research (max 10)"
                },
                "location": {
                    "type": "string",
                    "description": "Location code for search volume data",
                    "default": "United States"
                },
                "language": {
                    "type": "string", 
                    "description": "Language code",
                    "default": "en"
                }
            },
            "required": ["keywords"]
        }
    },
    {
        "name": "competitor_analysis",
        "description": "Analyze competitor rankings and backlinks using DataForSEO.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to analyze (e.g., 'example.com')"
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Type of analysis (organic, backlinks, competitors)",
                    "default": "organic"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 10
                }
            },
            "required": ["domain"]
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
            return {"__notification__": True}
        
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
            elif tool_name == "get_twitter_profile":
                result = await get_twitter_profile(**arguments)
            elif tool_name == "search_tiktok":
                result = await search_tiktok(**arguments)
            elif tool_name == "get_tiktok_user_videos":
                result = await get_tiktok_user_videos(**arguments)
            elif tool_name == "search_instagram":
                result = await search_instagram(**arguments)
            elif tool_name == "get_instagram_profile":
                result = await get_instagram_profile(**arguments)
            
            elif tool_name == "search_perplexity":
                result = await search_perplexity(**arguments)
            elif tool_name == "search_google_trends":
                result = await search_google_trends(**arguments)
            elif tool_name == "compare_google_trends":
                result = await compare_google_trends(**arguments)
            elif tool_name == "get_api_usage_stats":
                result = await get_api_usage_stats(**arguments)
            elif tool_name == "search_serp":
                result = await search_serp(**arguments)
            elif tool_name == "keyword_research":
                result = await keyword_research(**arguments)
            elif tool_name == "competitor_analysis":
                result = await competitor_analysis(**arguments)
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
            return {"__notification__": True}
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
        try:
            # Send immediate ping
            yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\"}\n\n"
            
            # Test rapid pings
            await asyncio.sleep(1)
            yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\", \"test\": 1}\n\n"
            
            await asyncio.sleep(1) 
            yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\", \"test\": 2}\n\n"
            
            await asyncio.sleep(1)
            yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"ping\", \"test\": 3}\n\n"
            
            # Keep connection alive with longer intervals
            while True:
                await asyncio.sleep(10)  # Shorter for debugging
                yield "data: {\"jsonrpc\": \"2.0\", \"method\": \"keepalive\"}\n\n"
                
        except Exception as e:
            print(f"SSE Error: {e}")
            yield f"data: {{\"jsonrpc\": \"2.0\", \"method\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",
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
    
    # Build search URL based on provided parameters
    if subreddit:
        # Search within specific subreddit
        search_url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "sort": sort,
            "t": time,
            "limit": limit
        }
        params["restrict_sr"] = "on"
    else:
        search_url = "https://www.reddit.com/search.json"
        params = {
            "q": query,
            "sort": sort,
            "t": time,
            "limit": limit
        }
    
    # Add more realistic headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
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
    
    # Add more realistic headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
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
    
    log_api_usage("Reddit", "subreddit_posts", limit, len(results), 0.0)  # Free API
    header = f"📋 Found {len(results)} posts from r/{subreddit} (sorted by {sort})"
    return header + "\n\n" + "\n---\n".join(results)

async def get_reddit_comments(post_url: str, limit: int = 10) -> str:
    """Get comments from a Reddit post"""
    try:
        # Extract subreddit and post ID from URL
        # URL format: https://www.reddit.com/r/subreddit/comments/post_id/title/
        url_pattern = r'reddit\.com/r/([^/]+)/comments/([^/]+)'
        match = re.search(url_pattern, post_url)
        
        if not match:
            return json.dumps({"error": "Invalid Reddit URL format", "status": "error"})
        
        subreddit = match.group(1)
        post_id = match.group(2)
        
        # Use Reddit's JSON API - correct format based on research
        json_url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; MCP-Server/1.0)'
        }
        
        timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(json_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Reddit returns array with [post_data, comments_data]
                if len(data) >= 2:
                    comments_data = data[1]['data']['children']
                    comments = []
                    
                    for comment in comments_data[:limit]:
                        comment_data = comment.get('data', {})
                        if comment_data.get('body'):  # Skip deleted/removed comments
                            comments.append({
                                "author": comment_data.get('author', 'unknown'),
                                "body": comment_data.get('body', ''),
                                "score": comment_data.get('score', 0),
                                "created_utc": comment_data.get('created_utc', 0),
                                "permalink": f"https://reddit.com{comment_data.get('permalink', '')}" if comment_data.get('permalink') else ""
                            })
                    
                    return json.dumps({
                        "success": True,
                        "comments": comments,
                        "count": len(comments),
                        "post_url": post_url
                    }, indent=2)
                else:
                    return json.dumps({"success": False, "error": "Invalid response format"})
            else:
                return json.dumps({"success": False, "error": f"HTTP {response.status_code}", "url": json_url})
    
    except Exception as e:
        return json.dumps({"success": False, "error": f"Exception: {str(e)}"})

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
    """Search Twitter posts using Apify"""
    try:
        apify_token = os.environ.get('APIFY_TOKEN')
        if not apify_token:
            return json.dumps({"error": "APIFY_TOKEN not found in environment variables", "status": "error"})
        
        url = "https://api.apify.com/v2/acts/61RPP7dywgiy0JPD0/run-sync-get-dataset-items"
        headers = {"Authorization": f"Bearer {apify_token}"}
        
        data = {
            "twitterHandles": [],
            "maxItems": min(limit, 50),
            "searchTerms": [query],
            "sort": sort,
            "customMapFunction": "(object) => { return {...object} }"
        }
        
        timeout = httpx.Timeout(90.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 201:
                items = response.json()
                if isinstance(items, list) and items:
                    tweets = []
                    for item in items[:limit]:
                        tweet = {
                            "text": item.get("full_text", item.get("text", ""))[:200] + "..." if len(item.get("full_text", item.get("text", ""))) > 200 else item.get("full_text", item.get("text", "")),
                            "author": item.get("author", {}).get("username", "unknown"),
                            "likes": item.get("favorite_count", 0),
                            "retweets": item.get("retweet_count", 0),
                            "replies": item.get("reply_count", 0),
                            "url": item.get("url", ""),
                            "created_at": item.get("created_at", "")
                        }
                        tweets.append(tweet)
                    
                    return json.dumps({
                        "success": True,
                        "tweets": tweets,
                        "count": len(tweets),
                        "query": query
                    }, indent=2)
                else:
                    return json.dumps({"success": False, "error": "No tweets found", "query": query})
            else:
                return json.dumps({"success": False, "error": f"API error: {response.status_code}", "response": response.text[:500]})
    
    except Exception as e:
        import traceback
        return json.dumps({"success": False, "error": f"Exception in search_twitter: {str(e)}", "traceback": traceback.format_exc()})

async def get_user_tweets(username: str, limit: int = 15, days_back: int = 7, start: str = None, end: str = None) -> str:
    """Get tweets from a specific user using Apify"""
    try:
        apify_token = os.environ.get('APIFY_TOKEN')
        if not apify_token:
            return json.dumps({"error": "APIFY_TOKEN not found in environment variables", "status": "error"})
        
        # IMPORTANT: Using correct Twitter actor 61RPP7dywgiy0JPD0 (NOT V38PZzpEgOfeeWvZY)
        url = "https://api.apify.com/v2/acts/61RPP7dywgiy0JPD0/run-sync-get-dataset-items"
        headers = {"Authorization": f"Bearer {apify_token}"}
        
        # Minimal payload by default
        data = {
            "twitterHandles": [username],
            "maxItems": min(limit, 50),
            "sort": "Latest",
            "customMapFunction": "(object) => { return {...object} }"
        }
        
        # Add optional date filters only if provided
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        
        timeout = httpx.Timeout(90.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 201:
                items = response.json()
                
                # Filter for actual tweets (items with 'text' field)
                tweets = [item for item in items if 'text' in item]
                
                return json.dumps({
                    "success": True,
                    "count": len(tweets),
                    "user": username,
                    "date_filter": {"start": start, "end": end} if start or end else None,
                    "tweets": [
                        {
                            "text": tweet.get("text", ""),
                            "author": tweet.get("author", {}).get("userName", username),
                            "created_at": tweet.get("createdAt", ""),
                            "like_count": tweet.get("likeCount", 0),
                            "retweet_count": tweet.get("retweetCount", 0),
                            "reply_count": tweet.get("replyCount", 0),
                            "url": tweet.get("url", "")
                        }
                        for tweet in tweets[:limit]
                    ]
                })
            else:
                return json.dumps({
                    "error": f"Apify API error: {response.status_code}",
                    "message": response.text[:200],
                    "status": "error"
                })
                
    except Exception as e:
        import traceback
        return json.dumps({"error": f"Exception in get_user_tweets: {str(e)}", "traceback": traceback.format_exc(), "status": "error"})

async def get_twitter_profile(username: str, get_followers: bool = False, get_following: bool = False) -> str:
    """Get Twitter user profile information."""
    log_api_usage("Twitter", "profile", 1, cost_estimate=0.01)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "customMapFunction": "(object) => { return {...object} }",
        "getFollowers": get_followers,
        "getFollowing": get_following,
        "getRetweeters": False,
        "includeUnavailableUsers": False,
        "maxItems": 10 if get_followers or get_following else 1,
        "startUrls": [
            "https://twitter.com"
        ],
        "twitterHandles": [
            username
        ]
    }
    
    # IMPORTANT: Using correct Twitter actor 61RPP7dywgiy0JPD0 (NOT V38PZzpEgOfeeWvZY)
    data = await make_request(f"{APIFY_API_BASE}/61RPP7dywgiy0JPD0/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    if not data:
        return f"❌ Failed to get profile for @{username}"
    
    # First item should be the main user
    if not data or data[0].get("userName") != username:
        return f"❌ Could not find profile data for @{username}"
    
    profile = data[0]
    
    result = f"""👤 **Twitter Profile: @{profile.get('userName', 'Unknown')}**

📛 **Name**: {profile.get('name', 'Unknown')}
{'✅ **Verified**' if profile.get('isVerified') else ''}
📝 **Bio**: {profile.get('description', 'No bio')}
📍 **Location**: {profile.get('location', 'Not specified')}

📊 **Stats**:
👥 **Followers**: {profile.get('followers', 0):,}
👤 **Following**: {profile.get('following', 0):,}
📝 **Tweets**: {profile.get('statusesCount', 0):,}
❤️ **Likes**: {profile.get('favouritesCount', 0):,}

📅 **Joined**: {profile.get('createdAt', 'Unknown')}
🔗 **Profile**: {profile.get('url', '')}
"""
    
    if get_followers and len(data) > 1:
        result += "\n\n👥 **Recent Followers**:\n"
        for follower in data[1:6]:  # Show max 5 followers
            if follower.get('followerOf') == username:
                result += f"• @{follower.get('userName')} - {follower.get('name')} ({follower.get('followers', 0):,} followers)\n"
    
    if get_following and len(data) > 1:
        result += "\n\n👤 **Recently Following**:\n"
        for following in data[1:6]:  # Show max 5 following
            if following.get('followingOf') == username:
                result += f"• @{following.get('userName')} - {following.get('name')} ({following.get('followers', 0):,} followers)\n"
    
    return result

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
        "resultsPerPage": limit,
        "hashtags": [],
        "excludePinnedPosts": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadVideos": False,
        "profileScrapeSections": ["videos"],
        "profileSorting": "popular",
        "searchSection": "",
        "maxProfilesPerQuery": 50
    }
    
    data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if data is None:
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

async def get_tiktok_user_videos(username: str, limit: int = 10, start_date: str = None, end_date: str = None) -> str:
    """Get TikTok user videos with optional date filtering."""
    limit = validate_limit(limit, MAX_LIMIT, "TikTok")
    log_api_usage("TikTok", "user_videos", limit)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    # Use the complete working schema 
    payload = {
        "excludePinnedPosts": False,
        "profiles": [username],
        "resultsPerPage": limit,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadVideos": False,
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "searchSection": "",
        "maxProfilesPerQuery": 10
    }
    
    # Add optional date filtering
    if end_date:
        payload["newestPostDate"] = end_date
    if start_date:
        payload["oldestPostDateUnified"] = start_date
    
    # Use 90 second timeout as requested
    try:
        data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=90)
        
        if data is None or len(data) == 0:
            return f"❌ No videos found for @{username}. This could be due to:\n• Private account\n• No videos posted\n• TikTok rate limiting\n• Username not found"
    except Exception as e:
        return f"❌ TikTok API error for @{username}: {str(e)}"
    
    results = []
    for video in data[:limit]:
        text = video.get("text", "")[:150]
        likes = video.get("diggCount", 0)
        views = video.get("playCount", 0)
        created_at = video.get("createTime", "")[:10]
        url = video.get("webVideoUrl", "") or video.get("videoUrl", "")
        
        results.append(f"📅 {created_at}\n📝 {text}\n👁️ {views:,} views | ❤️ {likes:,}\n🔗 {url}")
    
    date_filter = ""
    if start_date or end_date:
        date_filter = f" ({start_date or 'start'} to {end_date or 'latest'})"
    
    header = f"📱 Found {len(results)} videos from @{username}{date_filter}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# INSTAGRAM TOOLS
# ============================================================================

async def search_instagram(query: str, limit: int = 20, search_type: str = "hashtag") -> str:
    """Search Instagram posts by hashtag or keyword."""
    limit = validate_limit(limit, MAX_LIMIT, "Instagram")
    log_api_usage("Instagram", "search", limit, cost_estimate=0.03)
    
    try:
        apify_token = os.environ.get('APIFY_TOKEN')
        if not apify_token:
            return json.dumps({"error": "APIFY_TOKEN not found in environment variables", "status": "error"})
        
        url = "https://api.apify.com/v2/acts/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items"
        headers = {"Authorization": f"Bearer {apify_token}"}
        
        payload = {
            "search": query,
            "searchType": search_type,
            "resultsType": "posts",
            "resultsLimit": limit,
            "searchLimit": 1,
            "addParentData": False
        }
        
        # Instagram actor takes longer, so increase timeout
        timeout = httpx.Timeout(45.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 201:
                items = response.json()
                
                # Handle nested results structure
                posts = []
                if items and isinstance(items, list) and len(items) > 0:
                    first_item = items[0]
                    
                    # Check for different nested structures
                    if 'topPosts' in first_item and first_item['topPosts']:
                        posts = first_item['topPosts'][:limit]
                    elif 'posts' in first_item and first_item['posts']:
                        posts = first_item['posts'][:limit]
                    else:
                        # Look for any list that contains post-like objects
                        for key, value in first_item.items():
                            if isinstance(value, list) and value and isinstance(value[0], dict):
                                if any(field in value[0] for field in ['caption', 'text', 'ownerUsername', 'username']):
                                    posts = value[:limit]
                                    break
                
                if not posts:
                    return json.dumps({
                        "error": f"No Instagram posts found for #{query}",
                        "status": "error",
                        "debug_info": f"Response structure: {list(items[0].keys()) if items else 'empty'}"
                    })
                
                # Format the posts
                formatted_posts = []
                for post in posts:
                    formatted_post = {
                        "username": post.get("ownerUsername") or post.get("username", "Unknown"),
                        "caption": post.get("caption") or post.get("text", "")[:200],
                        "likes": post.get("likesCount") or post.get("likes", 0),
                        "comments": post.get("commentsCount") or post.get("comments", 0),
                        "type": post.get("type", "post"),
                        "url": post.get("url") or post.get("link", ""),
                        "created_at": post.get("timestamp") or post.get("createdAt", "")
                    }
                    formatted_posts.append(formatted_post)
                
                return json.dumps({
                    "success": True,
                    "count": len(formatted_posts),
                    "query": query,
                    "search_type": search_type,
                    "posts": formatted_posts
                })
            else:
                return json.dumps({
                    "error": f"Instagram API error: {response.status_code}",
                    "message": response.text[:200],
                    "status": "error"
                })
                
    except Exception as e:
        return json.dumps({"error": f"Exception in search_instagram: {str(e)}", "status": "error"})

async def get_instagram_profile(username: str, include_posts: bool = False) -> str:
    """Get Instagram user profile information."""
    log_api_usage("Instagram", "profile", 1, cost_estimate=0.02)
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured"
    
    payload = {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "details",
        "resultsLimit": 1
    }
    
    data = await make_request(f"{APIFY_API_BASE}/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST")
    
    if not data or len(data) == 0:
        return f"❌ Failed to get profile for @{username}"
    
    profile = data[0]
    
    result = f"""📸 **Instagram Profile: @{profile.get('username', username)}**

📛 **Name**: {profile.get('fullName', 'Unknown')}
{'✅ **Verified**' if profile.get('verified') else ''}
📝 **Bio**: {profile.get('biography', 'No bio')}
🔗 **Website**: {profile.get('website', 'None')}

📊 **Stats**:
👥 **Followers**: {profile.get('followersCount', 0):,}
👤 **Following**: {profile.get('followsCount', 0):,}
📸 **Posts**: {profile.get('postsCount', 0):,}

🔗 **Profile**: {profile.get('url', f'https://instagram.com/{username}')}
"""
    
    if include_posts and profile.get('latestPosts'):
        result += "\n\n📸 **Recent Posts**:\n"
        for i, post in enumerate(profile['latestPosts'][:5], 1):
            caption = post.get('caption', '')[:50] + '...' if post.get('caption') else 'No caption'
            likes = post.get('likesCount', 0)
            result += f"{i}. {caption} (❤️ {likes:,})\n"
    
    return result

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

async def wait_for_rate_limit():
    """Implement rate limiting for Google Trends requests."""
    global last_trends_request
    now = time.time()
    time_since_last = now - last_trends_request
    if time_since_last < GOOGLE_TRENDS_RATE_LIMIT["min_interval"]:
        delay = GOOGLE_TRENDS_RATE_LIMIT["min_interval"] - time_since_last
        await asyncio.sleep(delay)
    last_trends_request = time.time()

async def search_google_trends(query: str, timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Google Trends analysis using pytrends library."""
    try:
        from pytrends.request import TrendReq
        from pytrends.exceptions import TooManyRequestsError
        import pandas as pd
        import time
        # Use local log_api_usage function
        
        print("🔄 Initializing pytrends with retries...")
        # Try with retries and cookie approach
        pytrends = TrendReq(
            hl='en-US',
            tz=360,
            timeout=(10,30),
            retries=5,
            backoff_factor=2.0,
            requests_args={
                'verify': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            }
        )
        
        print("⏳ Waiting before request...")
        time.sleep(2)  # Reduced initial wait
        
        print(f"🔍 Building payload for: {query}")
        try:
            pytrends.build_payload([query], timeframe=timeframe, geo=geo)
            print("✅ Payload built successfully")
        except TooManyRequestsError as e:
            # log_api_usage("Google Trends", "search", 1, 0, 0.0)
            return """❌ Google Trends is currently rate limiting requests (Error 429).

This is a common issue with the unofficial Google Trends API. Here are some alternatives:

1. **Wait and retry later** - Rate limits usually reset after a few hours
2. **Use a VPN or proxy** - Change your IP address to bypass the limit
3. **Try alternative services**:
   - SerpApi Google Trends API (paid, but reliable)
   - Glimpse API (paid, provides real search volumes)
   - DataForSEO Trends API (aggregates data from multiple sources)

For now, please try again later or consider using one of the alternative services."""
        except Exception as e:
            print(f"❌ Error building payload: {str(e)}")
            # Try one more time with longer wait
            print("⏳ Retrying with longer wait...")
            time.sleep(30)
            try:
                pytrends.build_payload([query], timeframe=timeframe, geo=geo)
            except TooManyRequestsError:
                # log_api_usage("Google Trends", "search", 1, 0, 0.0)
                return "❌ Google Trends is rate limiting. Please try again later."
        
        print("⏳ Waiting after payload build...")
        time.sleep(2)
        
        print("📊 Getting interest over time data...")
        data = pytrends.interest_over_time()
        
        if data is None or data.empty:
            return "❌ No trend data available for this query"
            
        if query not in data.columns:
            return f"❌ Query data not found. Available columns: {data.columns.tolist()}"
        
        latest_value = data[query].iloc[-1]
        
        # Try to get related queries with error handling
        try:
            related = pytrends.related_queries()
            top_related = []
            rising_related = []
            
            if related and query in related:
                if 'top' in related[query] and isinstance(related[query]['top'], pd.DataFrame) and not related[query]['top'].empty:
                    top_related = related[query]['top']['query'].tolist()[:5]
                if 'rising' in related[query] and isinstance(related[query]['rising'], pd.DataFrame) and not related[query]['rising'].empty:
                    rising_related = related[query]['rising']['query'].tolist()[:5]
        except:
            top_related = []
            rising_related = []
        
        # Format the response
        response = [
            f"📈 Current trend value for '{query}': {latest_value}",
            "",
            "🔝 Top related searches:" if top_related else "🔝 No top related searches available",
            *[f"  • {q}" for q in top_related],
            "",
            "📈 Rising related searches:" if rising_related else "📈 No rising related searches available",
            *[f"  • {q}" for q in rising_related]
        ]
        
        # log_api_usage("Google Trends", "search", 1, 1, 0.0)
        return "\n".join(response)
        
    except TooManyRequestsError as e:
        print(f"❌ Rate limit error: {str(e)}")
        # log_api_usage("Google Trends", "search", 1, 0, 0.0)
        return """❌ Google Trends is currently rate limiting requests (Error 429).

This is a common issue with the unofficial Google Trends API. Here are some alternatives:

1. **Wait and retry later** - Rate limits usually reset after a few hours
2. **Use a VPN or proxy** - Change your IP address to bypass the limit
3. **Try alternative services**:
   - SerpApi Google Trends API (paid, but reliable)
   - Glimpse API (paid, provides real search volumes)
   - DataForSEO Trends API (aggregates data from multiple sources)

For now, please try again later or consider using one of the alternative services."""
    except Exception as e:
        print(f"❌ Error in search_google_trends: {str(e)}")
        # log_api_usage("Google Trends", "search", 1, 0, 0.0)
        return f"❌ Error analyzing trends: {str(e)}"

# ============================================================================
# SEO & SEARCH DATA TOOLS (DataForSEO API)
# ============================================================================

async def make_dataforseo_request(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make authenticated request to DataForSEO API."""
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return None
    
    import base64
    credentials = base64.b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json"
    }
    
    url = f"{DATAFORSEO_API_BASE}/{endpoint}"
    return await make_request(url, headers=headers, method="POST", json_data=payload, timeout=30.0)

async def search_serp(query: str, location: str = "United States", language: str = "en", limit: int = 10) -> str:
    """Search Google SERP data using DataForSEO API."""
    limit = validate_limit(limit, 100, "DataForSEO")
    log_api_usage("DataForSEO", "serp", limit, cost_estimate=0.0025)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return f"🔍 SERP search for '{query}'\n\n⚠️ **DataForSEO API Required**\nTo enable SERP analysis, configure DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.\n\n📊 **Search processed successfully**\n📝 Query: {query}\n🌍 Location: {location}\n🗣️ Language: {language}\n🔢 Limit: {limit}"
    
    # DataForSEO SERP API payload
    payload = [{
        "keyword": query,
        "location_name": location,
        "language_code": language,
        "device": "desktop",
        "os": "windows"
    }]
    
    data = await make_dataforseo_request("serp/google/organic/live/advanced", payload)
    
    if not data or "tasks" not in data:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ SERP search failed for '{query}'"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ SERP API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [{}])[0].get("items", [])[:limit]
    
    if not results:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ No SERP results found for '{query}'"
    
    formatted_results = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")[:200] + "..." if len(result.get("description", "")) > 200 else result.get("description", "")
        position = result.get("rank_absolute", i)
        
        formatted_results.append(f"**{position}. {title}**\n🔗 {url}\n📝 {description}")
    
    log_api_usage("DataForSEO", "serp", limit, len(results), 0.0025)
    header = f"🔍 **SERP Results for '{query}'** ({location}, {language})\n\nFound {len(results)} organic results"
    return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

async def keyword_research(keywords: List[str], location: str = "United States", language: str = "en") -> str:
    """Get keyword suggestions and search volume data using DataForSEO."""
    if len(keywords) > 10:
        keywords = keywords[:10]
    
    log_api_usage("DataForSEO", "keywords", len(keywords), cost_estimate=len(keywords) * 0.001)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return f"🔍 Keyword research for {len(keywords)} keywords\n\n⚠️ **DataForSEO API Required**\nTo enable keyword research, configure DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.\n\n📊 **Research processed successfully**\n📝 Keywords: {', '.join(keywords)}\n🌍 Location: {location}\n🗣️ Language: {language}"
    
    # DataForSEO Keywords API payload
    payload = [{
        "keywords": keywords,
        "location_name": location,
                    "language_code": language
    }]
    
    data = await make_dataforseo_request("keywords_data/google_ads/search_volume/live", payload)
    
    if not data or "tasks" not in data:
        log_api_usage("DataForSEO", "keywords", len(keywords), 0, len(keywords) * 0.001)
        return f"❌ Keyword research failed for {len(keywords)} keywords"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        log_api_usage("DataForSEO", "keywords", len(keywords), 0, len(keywords) * 0.001)
        return f"❌ Keywords API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [])
    
    if not results:
        log_api_usage("DataForSEO", "keywords", len(keywords), 0, len(keywords) * 0.001)
        return f"❌ No keyword data found"
    
    formatted_results = []
    for result in results:
        keyword = result.get("keyword", "Unknown")
        volume = result.get("search_volume", 0)
        competition = result.get("competition", "Unknown")
        cpc = result.get("cpc", 0)
        
        formatted_results.append(f"🔍 **{keyword}**\n📊 Volume: {volume:,}/month\n💰 CPC: ${cpc:.2f}\n🎯 Competition: {competition}")
    
    log_api_usage("DataForSEO", "keywords", len(keywords), len(results), len(keywords) * 0.001)
    header = f"🔍 **Keyword Research Results** ({location}, {language})\n\nAnalyzed {len(results)} keywords"
    return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

async def competitor_analysis(domain: str, analysis_type: str = "organic", limit: int = 10) -> str:
    """Analyze competitor rankings and backlinks using DataForSEO."""
    limit = validate_limit(limit, 100, "DataForSEO")
    log_api_usage("DataForSEO", "competitor", limit, cost_estimate=0.01)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return f"🔍 Competitor analysis for {domain}\n\n⚠️ **DataForSEO API Required**\nTo enable competitor analysis, configure DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.\n\n📊 **Analysis processed successfully**\n🌐 Domain: {domain}\n📈 Type: {analysis_type}\n🔢 Limit: {limit}"
    
    # Choose endpoint based on analysis type
    if analysis_type == "backlinks":
        endpoint = "backlinks/domain_pages/live"
        payload = [{
            "target": domain,
            "limit": limit
        }]
    elif analysis_type == "competitors":
        endpoint = "dataforseo_labs/google/competitors_domain/live"
        payload = [{
            "target": domain,
            "location_name": "United States",
            "language_code": "en",
            "limit": limit
        }]
    else:  # organic
        endpoint = "dataforseo_labs/google/domain_rank_overview/live"
        payload = [{
            "target": domain,
            "location_name": "United States", 
            "language_code": "en"
        }]
    
    data = await make_dataforseo_request(endpoint, payload)
    
    if not data or "tasks" not in data:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        return f"❌ Competitor analysis failed for {domain}"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        return f"❌ Competitor API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [])
    
    if not results:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        return f"❌ No {analysis_type} data found for {domain}"
    
    if analysis_type == "organic":
        # Domain overview data
        overview = results[0]
        metrics = overview.get("metrics", {})
        
        result = f"🌐 **Domain Overview: {domain}**\n\n"
        result += f"📊 **Organic Metrics**:\n"
        result += f"🔍 Keywords: {metrics.get('organic_keywords', 0):,}\n"
        result += f"👁️ Traffic: {metrics.get('organic_traffic', 0):,}/month\n"
        result += f"💰 Traffic Cost: ${metrics.get('organic_cost', 0):,.2f}\n"
        result += f"📈 Avg Position: {metrics.get('organic_avg_position', 0):.1f}\n"
        
        return result
        
    elif analysis_type == "competitors":
        # Competitor domains
        formatted_results = []
        for i, result in enumerate(results[:limit], 1):
            competitor = result.get("domain", "Unknown")
            keywords = result.get("intersections", 0)
            traffic = result.get("organic_traffic", 0)
            
            formatted_results.append(f"**{i}. {competitor}**\n🔍 Shared Keywords: {keywords:,}\n👁️ Traffic: {traffic:,}/month")
        
        header = f"🎯 **Top Competitors for {domain}**\n\nFound {len(results)} competitor domains"
        return header + "\n\n" + "\n\n---\n\n".join(formatted_results)
        
    else:  # backlinks
        # Backlink data
        formatted_results = []
        for i, result in enumerate(results[:limit], 1):
            page_url = result.get("url", "Unknown")
            referring_domains = result.get("referring_domains", 0)
            backlinks = result.get("backlinks", 0)
            
            formatted_results.append(f"**{i}. {page_url}**\n🔗 Backlinks: {backlinks:,}\n🌐 Ref Domains: {referring_domains:,}")
        
        header = f"🔗 **Top Backlinked Pages for {domain}**\n\nFound {len(results)} pages"
        return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

async def compare_google_trends(terms: List[str], timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Compare multiple terms on Google Trends."""
    try:
        from pytrends.request import TrendReq
        from pytrends.exceptions import TooManyRequestsError
        import pandas as pd
        import time
        # Use local log_api_usage function
        
        # Input validation
        if not terms:
            # log_api_usage("Google Trends", "compare", 0, 0, 0.0)
            return "❌ No terms provided for comparison"
        if len(terms) > 5:
            # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
            return "❌ Maximum 5 terms can be compared at once"
            
        # Initialize with retries and better headers
        pytrends = TrendReq(
            hl='en-US',
            tz=360,
            timeout=(10,30),
            retries=5,
            backoff_factor=2.0,
            requests_args={
                'verify': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            }
        )
        
        # Wait before request
        time.sleep(2)
        
        print(f"🔍 Comparing trends for: {', '.join(terms)}")
        
        # Build the payload with retry logic
        try:
            pytrends.build_payload(terms, timeframe=timeframe, geo=geo)
        except TooManyRequestsError:
            # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
            return """❌ Google Trends is currently rate limiting requests (Error 429).

This is a common issue with the unofficial Google Trends API. Here are some alternatives:

1. **Wait and retry later** - Rate limits usually reset after a few hours
2. **Use a VPN or proxy** - Change your IP address to bypass the limit
3. **Try alternative services**:
   - SerpApi Google Trends API (paid, but reliable)
   - Glimpse API (paid, provides real search volumes)
   - DataForSEO Trends API (aggregates data from multiple sources)

For now, please try again later or consider using one of the alternative services."""
        except Exception as e:
            print(f"❌ First attempt failed: {str(e)}")
            print("⏳ Retrying with longer wait...")
            time.sleep(30)
            try:
                pytrends.build_payload(terms, timeframe=timeframe, geo=geo)
            except TooManyRequestsError:
                # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
                return "❌ Google Trends is rate limiting. Please try again later."
        
        # Wait after payload
        time.sleep(2)
        
        # Get interest over time data
        data = pytrends.interest_over_time()
        
        if data is None or data.empty:
            # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
            return "❌ No trend data available for these terms"
            
        # Get the most recent values for each term
        latest_values = {}
        averages = {}
        
        for term in terms:
            if term in data.columns:
                latest_values[term] = data[term].iloc[-1]
                averages[term] = data[term].mean()
            else:
                latest_values[term] = "N/A"
                averages[term] = "N/A"
        
        # Format the response
        response = [
            "📊 Trend Comparison:",
            "",
            "Current values:"
        ]
        
        # Add current values
        for term in terms:
            if latest_values[term] != "N/A":
                response.append(f"  • {term}: {latest_values[term]:.1f}")
            else:
                response.append(f"  • {term}: N/A")
            
        response.extend([
            "",
            "Average values:"
        ])
        
        # Add average values
        for term in terms:
            if averages[term] != "N/A":
                response.append(f"  • {term}: {averages[term]:.1f}")
            else:
                response.append(f"  • {term}: N/A")
            
        # log_api_usage("Google Trends", "compare", len(terms), 1, 0.0)
        return "\n".join(response)
        
    except TooManyRequestsError:
        print(f"❌ Rate limit error in compare_google_trends")
        # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
        return """❌ Google Trends is currently rate limiting requests (Error 429).

This is a common issue with the unofficial Google Trends API. Here are some alternatives:

1. **Wait and retry later** - Rate limits usually reset after a few hours
2. **Use a VPN or proxy** - Change your IP address to bypass the limit
3. **Try alternative services**:
   - SerpApi Google Trends API (paid, but reliable)
   - Glimpse API (paid, provides real search volumes)
   - DataForSEO Trends API (aggregates data from multiple sources)

For now, please try again later or consider using one of the alternative services."""
    except Exception as e:
        print(f"Error in compare_google_trends: {str(e)}")
        # log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
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

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
from fastapi import FastAPI, HTTPException, Response, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.base import BaseHTTPMiddleware  # Not needed currently
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

# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"🌐 {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    if request.url.path not in ["/health"]:  # Don't spam logs with health checks only
        print(f"📋 Query params: {dict(request.query_params)}")
        print(f"📋 Headers: {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        print(f"⏱️ Request {request.method} {request.url.path} completed in {duration:.3f}s with status {response.status_code}")
        
        if response.status_code == 404:
            print(f"❌ 404 Not Found: {request.method} {request.url.path}")
        elif response.status_code >= 400:
            print(f"❌ {response.status_code} Error: {request.method} {request.url.path}")
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 Request {request.method} {request.url.path} failed after {duration:.3f}s: {str(e)}")
        raise

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

# Progress tracking for long-running operations
progress_trackers = {}
connected_sse_clients = set()

# SSE notification queue
notification_queue = asyncio.Queue()

# API Keys from environment
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") 
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "sarubaito@pm.me")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "94c575f885c863f8")

# API timeout constants
APIFY_TIMEOUT = 90.0  # Apify actors need generous timeout

# MCP Authentication
MCP_API_KEY = os.environ.get("MCP_API_KEY", "mcp-general-server-key-2024")  # Default key for testing

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
    },
    {
        "name": "lighthouse_audit",
        "description": "Run a comprehensive Lighthouse audit on a website.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Website URL to audit"
                },
                "strategy": {
                    "type": "string",
                    "description": "Audit strategy (desktop, mobile)",
                    "default": "desktop"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "lighthouse_performance_score",
        "description": "Get just the performance score for a website.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Website URL to check"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "lighthouse_bulk_audit",
        "description": "Run Lighthouse audits on multiple URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^https?://.*",
                        "minLength": 7
                    },
                    "description": "List of URLs to audit (max 5)",
                    "maxItems": 5,
                    "minItems": 1
                }
            },
            "required": ["urls"]
        }
    },
    {
        "name": "onpage_seo_audit",
        "description": "Comprehensive site-wide technical SEO analysis. Creates new audit or retrieves existing results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Website URL to analyze (e.g., 'https://example.com')"
                },
                "task_id": {
                    "type": "string",
                    "description": "Existing task ID to retrieve results. If provided, retrieves results instead of creating new task."
                },
                "max_crawl_pages": {
                    "type": "integer",
                    "description": "Maximum pages to crawl (for new tasks)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                }
            },
            "required": ["target"]
        }
    },
    {
        "name": "test_dataforseo_endpoints",
        "description": "Test DataForSEO API endpoint access to check plan capabilities",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to test with",
                    "default": "nansen.ai"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_ranked_keywords",
        "description": "Get all keywords a domain ranks for with position, volume, and difficulty data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to analyze (e.g., 'example.com')"
                },
                "location": {
                    "type": "string",
                    "description": "Target location",
                    "default": "United States"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum keywords to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                }
            },
            "required": ["domain"]
        }
    },
    {
        "name": "get_historical_rankings",
        "description": "Get historical ranking trends showing keyword portfolio growth over time",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to analyze (e.g., 'example.com')"
                },
                "location": {
                    "type": "string",
                    "description": "Target location",
                    "default": "United States"
                }
            },
            "required": ["domain"]
        }
    },
    {
        "name": "get_top_pages",
        "description": "Get top performing pages by organic traffic and keyword rankings",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to analyze (e.g., 'example.com')"
                },
                "location": {
                    "type": "string",
                    "description": "Target location",
                    "default": "United States"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum pages to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100
                }
            },
            "required": ["domain"]
        }
    }
]

# ============================================================================
# PROGRESS TRACKING AND NOTIFICATIONS
# ============================================================================

async def send_progress_notification(request_id: str, progress: float, total: float = 1.0, message: str = None):
    """Send progress notification for long-running operations"""
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/progress",
        "params": {
            "progressToken": str(request_id),
            "progress": progress,
            "total": total
        }
    }
    if message:
        notification["params"]["message"] = message
    
    # Queue notification for SSE clients
    await notification_queue.put(notification)
    print(f"📊 Progress: {progress}/{total} for request {request_id}")

async def send_tools_changed_notification():
    """Notify clients that tool list has changed"""
    notification = {
        "jsonrpc": "2.0", 
        "method": "notifications/tools/list_changed"
    }
    await notification_queue.put(notification)
    print("🔧 Sent tools/list_changed notification")

async def send_log_notification(level: str, message: str, data: dict = None):
    """Send log notification to clients"""
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/log",
        "params": {
            "level": level,  # "info", "warning", "error"
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    }
    if data:
        notification["params"]["data"] = data
    
    await notification_queue.put(notification)

# ============================================================================
# MCP HTTP ENDPOINTS
# ============================================================================

async def handle_mcp_message_internal(message: dict):
    """Internal MCP message handler for both HTTP and WebSocket."""
    # Extract authentication token from params
    params = message.get("params", {})
    claude_auth_token = params.get("_claudeMcpAuthToken")
    
    # Remove the auth token from params before processing
    if "_claudeMcpAuthToken" in params:
        params = {k: v for k, v in params.items() if k != "_claudeMcpAuthToken"}
        message["params"] = params
    
    method = message.get("method")
    message_id = message.get("id")
    
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
                    "tools": {
                        "listChanged": True,
                        "supportsProgress": True  # Enable progress for long-running tools
                    },
                    "resources": {
                        "subscribe": True,
                        "listChanged": True
                    },
                    "prompts": {
                        "listChanged": True
                    },
                    "logging": {
                        "level": "info",  # Support info, warning, error levels
                        "setLevel": True
                    },
                    "experimental": {
                        "customAuth": True  # For custom auth pattern
                    }
                },
                "serverInfo": {
                    "name": "General MCP Server",
                    "version": "1.0.0"
                },
                                    "authentication": {
                        "status": "authenticated" if claude_auth_token else "optional",
                        "method": "bearer"
                    }
            }
        }
    
    elif method == "tools/list":
        print(f"📋 Processing tools/list request (authenticated: {bool(claude_auth_token)})")
        print(f"⏱️ Starting tools/list response preparation...")
        
        # For authenticated requests, return tools as available
        tools_response = TOOLS.copy()
        
        # Add tool status if authenticated
        if claude_auth_token:
            for tool in tools_response:
                tool["enabled"] = True
                tool["authenticated"] = True
        
        print(f"✅ Returning {len(tools_response)} tools (response size: ~{len(str(tools_response))} chars)")
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"tools": tools_response}
        }
    
    elif method == "resources/list":
        print(f"📁 Processing resources/list request (authenticated: {bool(claude_auth_token)})")
        
        resources = [
            {
                "uri": "resource://api-usage-stats",
                "name": "API Usage Statistics",
                "description": "Real-time API usage and cost tracking",
                "mimeType": "application/json"
            },
            {
                "uri": "resource://server-config",
                "name": "Server Configuration",
                "description": "Current MCP server configuration and capabilities",
                "mimeType": "application/json"
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"resources": resources}
        }
    
    elif method == "prompts/list":
        print(f"💬 Processing prompts/list request (authenticated: {bool(claude_auth_token)})")
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"prompts": []}
        }
    
    elif method == "tools/call":
        tool_name = message.get("params", {}).get("name")
        arguments = message.get("params", {}).get("arguments", {})
        
        print(f"INFO:__main__:Calling tool: {tool_name} with args: {arguments}")
        
        # Long-running tools that need progress tracking
        long_running_tools = {
            "search_twitter", "search_tiktok", "search_instagram",
            "lighthouse_audit", "lighthouse_bulk_audit",
            "search_serp", "competitor_analysis"
        }
        
        # Start progress tracking for long-running tools
        if tool_name in long_running_tools and message_id:
            await send_progress_notification(message_id, 0.1, 1.0, f"Starting {tool_name}...")
            await send_log_notification("info", f"Executing long-running tool: {tool_name}")
        
        # Call the appropriate tool function
        result = None
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
        elif tool_name == "lighthouse_audit":
            result = await lighthouse_audit(**arguments)
        elif tool_name == "lighthouse_performance_score":
            result = await lighthouse_performance_score(**arguments)
        elif tool_name == "lighthouse_bulk_audit":
            result = await lighthouse_bulk_audit(**arguments)
        elif tool_name == "onpage_seo_audit":
            result = await onpage_seo_audit(**arguments)
        elif tool_name == "test_dataforseo_endpoints":
            result = await test_dataforseo_endpoints(**arguments)
        elif tool_name == "get_ranked_keywords":
            result = await get_ranked_keywords(**arguments)
        elif tool_name == "get_historical_rankings":
            result = await get_historical_rankings(**arguments)
        elif tool_name == "get_top_pages":
            result = await get_top_pages(**arguments)
        else:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
        
        # Send completion notification for long-running tools
        if tool_name in long_running_tools and message_id:
            await send_progress_notification(message_id, 1.0, 1.0, f"Completed {tool_name}")
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ],
                "isError": False  # Indicate successful completion
            }
        }
    
    elif method == "resources/read":
        resource_uri = message.get("params", {}).get("uri")
        
        if resource_uri == "resource://api-usage-stats":
            # Return current API usage statistics
            stats = await get_api_usage_stats()
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "contents": [
                        {
                            "uri": resource_uri,
                            "mimeType": "application/json",
                            "text": json.dumps(stats, indent=2)
                        }
                    ]
                }
            }
        elif resource_uri == "resource://server-config":
            # Return server configuration
            config = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "General MCP Server",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": {
                        "listChanged": True,
                        "supportsProgress": True
                    },
                    "resources": {
                        "subscribe": True,
                        "listChanged": True
                    },
                    "prompts": {
                        "listChanged": True
                    },
                    "logging": {
                        "level": "info",
                        "setLevel": True
                    }
                },
                "connectedClients": len(connected_sse_clients),
                "environment": {
                    "apify": "configured" if APIFY_TOKEN else "not configured",
                    "youtube": "configured" if YOUTUBE_API_KEY else "not configured",
                    "perplexity": "configured" if PERPLEXITY_API_KEY else "not configured",
                    "scrapingbee": "configured" if SCRAPINGBEE_API_KEY else "not configured",
                    "dataforseo": "configured"
                }
            }
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "contents": [
                        {
                            "uri": resource_uri,
                            "mimeType": "application/json",
                            "text": json.dumps(config, indent=2)
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown resource: {resource_uri}"
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

@app.post("/message")
async def handle_mcp_message(message: dict, request: Request, authorization: str = None):
    """Handle MCP protocol messages over HTTP."""
    try:
        # Extract authentication token from params or headers
        auth_token = None
        if authorization and authorization.startswith("Bearer "):
            auth_token = authorization.replace("Bearer ", "")
        
        # Check for Claude's auth token in message params
        params = message.get("params", {})
        claude_auth_token = params.get("_claudeMcpAuthToken")
        
        # Detect client type
        user_agent = request.headers.get("user-agent", "")
        client_info = message.get("params", {}).get("clientInfo", {})
        client_name = client_info.get("name", "")
        
        if "node" in user_agent or client_name == "claude-desktop":
            client_type = "🖥️ Claude Desktop"
        elif "python-httpx" in user_agent and client_name == "claude-ai":
            client_type = "🌐 Claude AI Web"
        else:
            client_type = f"❓ Unknown ({client_name})"
        
        # Log all incoming requests for debugging (but hide sensitive tokens)
        print(f"📥 HTTP request from {client_type} ({request.client.host if request.client else 'unknown'})")
        print(f"🔐 Auth token present: {bool(auth_token or claude_auth_token)}")
        
        # For tool calls, we need to validate authentication
        method = message.get("method")
        
        # Special logging for tools/list to track down the issue
        if method == "tools/list":
            print(f"🔍 FOUND tools/list request in /message endpoint!")
        else:
            print(f"🔍 Method '{method}' received in /message (not tools/list)")
        message_id = message.get("id")
        
        # Remove the auth token from params before processing (it's not part of the actual parameters)
        if "_claudeMcpAuthToken" in params:
            params = {k: v for k, v in params.items() if k != "_claudeMcpAuthToken"}
            message["params"] = params
        
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
                        "tools": {
                            "listChanged": True,
                            "supportsProgress": False
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False
                        },
                        "prompts": {
                            "listChanged": False
                        },
                        "logging": {}
                    },
                    "serverInfo": {
                        "name": "General MCP Server",
                        "version": "1.0.0"
                    },
                    "authentication": {
                        "status": "authenticated" if (auth_token or claude_auth_token) else "optional",
                        "method": "bearer"
                    }
                }
            }
        
        elif method == "tools/list":
            print(f"📋 Processing tools/list request via /message (authenticated: {bool(auth_token or claude_auth_token)})")
            # Always return tools, but mark their availability based on authentication
            tools_response = TOOLS.copy()
            
            # Mark tool availability based on authentication
            is_authenticated = bool(auth_token or claude_auth_token)
            for tool in tools_response:
                tool["enabled"] = is_authenticated
                tool["authenticated"] = is_authenticated
            
            print(f"✅ Returning {len(tools_response)} tools via /message (enabled: {is_authenticated})")
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"tools": tools_response}
            }
        
        elif method == "resources/list":
            print(f"📁 Processing resources/list request via /message (authenticated: {bool(auth_token or claude_auth_token)})")
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"resources": []}
            }
        
        elif method == "prompts/list":
            print(f"💬 Processing prompts/list request via /message (authenticated: {bool(auth_token or claude_auth_token)})")
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
            elif tool_name == "lighthouse_audit":
                result = await lighthouse_audit(**arguments)
            elif tool_name == "lighthouse_performance_score":
                result = await lighthouse_performance_score(**arguments)
            elif tool_name == "lighthouse_bulk_audit":
                result = await lighthouse_bulk_audit(**arguments)
            elif tool_name == "onpage_seo_audit":
                result = await onpage_seo_audit(**arguments)
            elif tool_name == "test_dataforseo_endpoints":
                result = await test_dataforseo_endpoints(**arguments)
            elif tool_name == "get_ranked_keywords":
                result = await get_ranked_keywords(**arguments)
            elif tool_name == "get_historical_rankings":
                result = await get_historical_rankings(**arguments)
            elif tool_name == "get_top_pages":
                result = await get_top_pages(**arguments)
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP communication."""
    await websocket.accept()
    print(f"🔌 WebSocket connected from {websocket.client}")
    
    try:
        # Send initialization message
        await websocket.send_text(json.dumps({
            "jsonrpc": "2.0",
            "method": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }))
        
        while True:
            # Wait for incoming messages
            data = await websocket.receive_text()
            print(f"📨 WebSocket received: {data}")
            
            try:
                message = json.loads(data)
                
                # Handle the message using the same logic as HTTP endpoint
                response = await handle_mcp_message_internal(message)
                
                # Send response back via WebSocket
                await websocket.send_text(json.dumps(response))
                
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0", 
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None
                }
                await websocket.send_text(json.dumps(error_response))
                
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected from {websocket.client}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        await websocket.close()

@app.post("/mcp")
async def handle_mcp_post(message: dict, request: Request):
    print(f"EARLY LOG: {datetime.now().isoformat()} from {request.client.host} UA: {request.headers.get('user-agent')}")
    try:
        # Detect client type
        user_agent = request.headers.get("user-agent", "")
        client_info = message.get("params", {}).get("clientInfo", {})
        client_name = client_info.get("name", "")
        
        # Determine if this is Claude Desktop or Claude AI Web
        if "python-httpx" in user_agent and client_name == "claude-ai":
            client_type = "🌐 Claude AI Web"
        elif "node" in user_agent or client_name == "claude-desktop":
            client_type = "🖥️ Claude Desktop"
        else:
            client_type = f"❓ Unknown ({client_name})"
        
        print(f"📨 SSE POST from {client_type} ({request.client.host if request.client else 'unknown'}): {message}")
        
        # Special logging for tools/list to track down the issue
        method = message.get("method")
        if method == "tools/list":
            print(f"🔍 FOUND tools/list request in /mcp endpoint!")
        else:
            print(f"🔍 Method '{method}' received (not tools/list)")
        
        # Extract Bearer token from Authorization header
        authorization = request.headers.get("authorization") or request.headers.get("Authorization")
        print(f"🔐 SSE Auth: {authorization}")
        
        # Extract Bearer token
        if authorization and authorization.startswith("Bearer "):
            auth_token = authorization.replace("Bearer ", "")
            print(f"✅ Valid Bearer token for SSE: {auth_token[:16]}...")
            
            # Add auth token to message params for processing
            if "params" not in message:
                message["params"] = {}
            message["params"]["_claudeMcpAuthToken"] = auth_token
        
        # Process the message using internal handler with method-specific timeout
        import asyncio
        method = message.get("method", "")
        
        # Set timeout based on method type
        if method in ["tools/list", "resources/list", "prompts/list", "initialize"]:
            timeout = 5.0  # Fast operations should be instant
        elif method == "tools/call":
            timeout = 120.0  # Tool calls can take time (Apify, Lighthouse, etc.)
        else:
            timeout = 30.0  # Default for other operations
            
        print(f"⏰ Using {timeout}s timeout for method: {method}")
        
        result = await asyncio.wait_for(
            handle_mcp_message_internal(message), 
            timeout=timeout
        )
        print(f"✅ SSE POST response: {result}")
        return result
        
    except asyncio.TimeoutError:
        print(f"⏰ SSE POST timeout for method: {message.get('method')}")
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32001,
                "message": "Request timed out"
            }
        }
    except Exception as e:
        print(f"❌ SSE POST error: {str(e)}")
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/mcp")  
async def handle_mcp_get(request: Request):
    """Handle SSE streaming for MCP notifications only."""
    # Detect client type
    user_agent = request.headers.get("user-agent", "")
    
    if "python-httpx" in user_agent:
        client_type = "🌐 Claude AI Web"
    elif "node" in user_agent:
        client_type = "🖥️ Claude Desktop"
    else:
        client_type = f"❓ Unknown"
    
    print(f"🌊 SSE connection from {client_type} ({request.client.host if request.client else 'unknown'})")
    
    # Extract Bearer token from Authorization header
    authorization = request.headers.get("authorization") or request.headers.get("Authorization")
    print(f"🔐 SSE Auth: {authorization}")
    
    # Check if Accept header requests SSE
    accept_header = request.headers.get("accept", "")
    print(f"📋 Headers: {dict(request.headers)}")
    
    # SSE stream for server-initiated notifications only
    async def event_stream():
        # Add this client to connected set
        client_id = f"sse_{request.client.host}_{int(time.time())}"
        connected_sse_clients.add(client_id)
        print(f"👥 SSE client connected: {client_id}")
        
        try:
            # Send notifications and keep connection alive
            while True:
                try:
                    # Check for queued notifications (non-blocking)
                    notification = await asyncio.wait_for(
                        notification_queue.get(), 
                        timeout=30.0  # Wait up to 30 seconds
                    )
                    # Send the notification
                    yield f"data: {json.dumps(notification)}\n\n"
                    print(f"📤 Sent notification: {notification.get('method')}")
                    
                except asyncio.TimeoutError:
                    # No notification, send ping to keep alive
                    ping = {
                        "jsonrpc": "2.0",
                        "method": "ping",
                        "params": {"timestamp": int(time.time())}
                    }
                    yield f"data: {json.dumps(ping)}\n\n"
                    
        except Exception as e:
            print(f"SSE Stream Error for {client_id}: {e}")
            error_msg = {
                "jsonrpc": "2.0",
                "method": "error",
                "params": {"message": str(e)}
            }
            yield f"data: {json.dumps(error_msg)}\n\n"
        finally:
            # Remove client on disconnect
            connected_sse_clients.discard(client_id)
            print(f"👋 SSE client disconnected: {client_id}")
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "server": "General MCP Server", "version": "1.0.0"}

@app.post("/connect")
async def mcp_connect(request: dict):
    """MCP connection endpoint for Claude AI web."""
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": True,
                    "supportsProgress": False
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": False
                },
                "prompts": {
                    "listChanged": False
                },
                "logging": {}
            },
            "serverInfo": {
                "name": "General MCP Server",
                "version": "1.0.0"
            }
        }
    }


@app.get("/v1/servers")
async def list_servers():
    """List available MCP servers."""
    return {
        "servers": [{
            "name": "General MCP Server",
            "version": "1.0.0",
            "url": "https://general-mcp-production.up.railway.app",
            "capabilities": ["tools", "resources", "prompts"]
        }]
    }

@app.get("/mcp/info")
async def mcp_info():
    """MCP server information endpoint."""
    return {
        "name": "General MCP Server", 
        "version": "1.0.0",
        "protocol": "2024-11-05",
        "capabilities": ["tools", "resources", "prompts"],
        "endpoints": {
            "message": "/message",
            "sse": "/sse",
            "health": "/health"
        },
        "auth": {
            "type": "bearer",
            "required": False
        }
    }

@app.options("/message")
async def message_options():
    """Handle CORS preflight for /message endpoint."""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.0 authorization server metadata."""
    return {
        "issuer": "https://general-mcp-production.up.railway.app",
        "authorization_endpoint": "https://general-mcp-production.up.railway.app/authorize",
        "token_endpoint": "https://general-mcp-production.up.railway.app/token",
        "registration_endpoint": "https://general-mcp-production.up.railway.app/register",
        "scopes_supported": ["mcp:read", "mcp:write"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"]
    }

@app.get("/.well-known/mcp")
async def mcp_metadata():
    """MCP server discovery metadata."""
    return {
        "server": {
            "name": "General MCP Server",
            "version": "1.0.0"
        },
        "protocol": {
            "version": "2024-11-05"
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True
        },
        "endpoints": {
            "mcp": "https://general-mcp-production.up.railway.app/mcp"
        },
        "authentication": {
            "oauth2": {
                "authorization_url": "https://general-mcp-production.up.railway.app/authorize",
                "token_url": "https://general-mcp-production.up.railway.app/token"
            }
        }
    }

@app.post("/message")
async def handle_message_post(message: dict, request: Request):
    """Handle MCP messages via POST to /message endpoint (fallback for clients that ignore metadata)."""
    print(f"📨 Received request at POST /message - forwarding to SSE handler")
    return await handle_mcp_message(message, request)

@app.post("/register")
async def oauth_register(request: dict):
    """OAuth 2.0 client registration."""
    return {
        "client_id": "mcp-client-" + str(hash(str(request)))[-8:],
        "client_secret": "mcp-secret-" + str(hash(str(request)))[-16:],
        "registration_access_token": "mcp-token-" + str(hash(str(request)))[-16:],
        "registration_client_uri": "https://general-mcp-production.up.railway.app/register"
    }

@app.get("/authorize")
async def oauth_authorize(
    response_type: str,
    client_id: str, 
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str
):
    """OAuth 2.0 authorization endpoint."""
    print(f"🔐 OAuth authorize request: client_id={client_id}, redirect_uri={redirect_uri}")
    
    # Generate authorization code
    auth_code = "mcp_auth_" + str(hash(f"{client_id}{state}"))[-16:]
    
    # Redirect back to Claude AI with authorization code
    callback_url = f"{redirect_uri}?code={auth_code}&state={state}"
    print(f"↩️ Redirecting to: {callback_url}")
    
    return RedirectResponse(url=callback_url)

@app.post("/token")
async def oauth_token(request: Request):
    """OAuth 2.0 token endpoint."""
    # OAuth token requests use form data, not JSON
    form_data = await request.form()
    
    grant_type = form_data.get("grant_type")
    code = form_data.get("code") 
    redirect_uri = form_data.get("redirect_uri")
    client_id = form_data.get("client_id")
    code_verifier = form_data.get("code_verifier")
    
    print(f"🎫 Token request: grant_type={grant_type}, code={code}, client_id={client_id}")
    print(f"📝 All form data: {dict(form_data)}")
    
    # Validate required parameters
    if not grant_type or grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Invalid grant_type")
    
    if not code or not code.startswith("mcp_auth_"):
        raise HTTPException(status_code=400, detail="Invalid authorization code")
    
    # Generate access token
    access_token = "mcp_token_" + str(hash(f"{client_id}{code}"))[-32:]
    
    return {
        "access_token": access_token,
        "token_type": "Bearer", 
        "expires_in": 3600,
        "scope": "mcp:read mcp:write",
        "mcp_endpoint": "https://general-mcp-production.up.railway.app/mcp",
        "server_info": {
            "name": "General MCP Server",
            "version": "1.0.0"
        }
    }

@app.post("/")
async def root_post():
    """Handle POST to root - redirect to /message."""
    raise HTTPException(status_code=307, detail="Use /message endpoint for MCP communication")

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
        "getFollowers": True,
        "getFollowing": True,
        "getRetweeters": True,
        "includeUnavailableUsers": False,
        "maxItems": 5,
        "startUrls": [
            "https://twitter.com"
        ],
        "twitterHandles": [
            username
        ]
    }
    
    # Using Twitter profile actor V38PZzpEgOfeeWvZY (returns multiple profiles, need to filter)
    print(f"DEBUG: Making Twitter profile API request for @{username}")
    data = await make_request(f"{APIFY_API_BASE}/V38PZzpEgOfeeWvZY/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    print(f"DEBUG: Twitter API returned data type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
    
    if not data:
        return f"❌ Failed to get profile for @{username}"
    
    # Validate data structure
    if not isinstance(data, list) or len(data) == 0:
        return f"❌ No profile data returned for @{username}"
    
    # Filter to find the correct profile (actor returns at least 5 profiles)
    profile = None
    possible_username_fields = ["userName", "username", "handle", "screen_name", "user_name"]
    
    for item in data:
        if not isinstance(item, dict):
            continue
            
        # Check all possible username fields
        for field in possible_username_fields:
            if field in item and item[field]:
                item_username = str(item[field]).lower()
                if item_username == username.lower():
                    profile = item
                    break
        
        if profile:
            break
    
    # If no matching profile found, show debug info
    if not profile:
        available_usernames = []
        for item in data[:3]:  # Show first 3 profiles for debugging
            if isinstance(item, dict):
                for field in possible_username_fields:
                    if field in item and item[field]:
                        available_usernames.append(f"@{item[field]}")
                        break
        return f"❌ Could not find profile for @{username}. Found profiles: {', '.join(available_usernames)}. Total profiles returned: {len(data)}"
    
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
        print(f"DEBUG: Making TikTok API request for @{username}")
        data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=90)
        
        print(f"DEBUG: TikTok API returned data type: {type(data)}, value: {str(data)[:200]}")
        
        # Validate data is a list and has content
        if data is None:
            return f"❌ No response from TikTok API for @{username}"
        if isinstance(data, int):
            return f"❌ TikTok API returned status code: {data} for @{username}"
        if not isinstance(data, list):
            return f"❌ Unexpected TikTok API response format for @{username}: {type(data)} - {str(data)[:100]}"
        if len(data) == 0:
            return f"❌ No videos found for @{username}. This could be due to:\n• Private account\n• No videos posted\n• TikTok rate limiting\n• Username not found"
        
        print(f"DEBUG: TikTok validation passed, processing {len(data)} items")
    except Exception as e:
        return f"❌ TikTok API error for @{username}: {str(e)}"
    
    results = []
    for video in data[:limit]:
        text = video.get("text", "")[:150]
        
        # Handle likes and views safely - convert to int and handle potential string values
        likes_raw = video.get("diggCount", 0)
        views_raw = video.get("playCount", 0)
        
        try:
            likes = int(likes_raw) if likes_raw is not None else 0
        except (ValueError, TypeError):
            likes = 0
            
        try:
            views = int(views_raw) if views_raw is not None else 0
        except (ValueError, TypeError):
            views = 0
        
        created_at = video.get("createTime", "")
        if created_at and len(str(created_at)) > 10:
            created_at = str(created_at)[:10]
        else:
            created_at = str(created_at)
            
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
        
        print("🔄 Initializing pytrends with simplified parameters...")
        # Initialize with simplified parameters to avoid compatibility issues
        try:
            pytrends = TrendReq(
                hl='en-US',
                tz=360,
                timeout=(10,30)
            )
        except Exception as init_error:
            print(f"Error initializing TrendReq: {init_error}")
            # Fallback to basic initialization
            pytrends = TrendReq(hl='en-US', tz=360)
        
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
    
    # Enhanced DataForSEO SERP API payload to capture all SERP features
    payload = [{
        "keyword": query,
        "location_name": location,
        "language_code": language,
        "device": "desktop",
        "os": "windows",
        "depth": min(limit * 2, 100),  # Request more results for better quality
        "se_domain": "google.com"
    }]
    
    data = await make_dataforseo_request("serp/google/organic/live/advanced", payload)
    
    if not data or "tasks" not in data:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ SERP search failed for '{query}'"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ SERP API error: {task.get('status_message', 'Unknown error')}"
    
    # Safely extract results with defensive programming
    result_data = task.get("result", [])
    if not result_data or not isinstance(result_data, list):
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ Invalid SERP API response structure for '{query}'"
    
    all_items = result_data[0].get("items", []) if result_data else []
    
    if not all_items:
        log_api_usage("DataForSEO", "serp", limit, 0, 0.0025)
        return f"❌ No SERP results found for '{query}'"
    
    # Separate organic results from SERP features
    organic_results = []
    serp_features = []
    
    for item in all_items:
        item_type = item.get("type", "").lower()
        
        if item_type == "organic":
            # Enhanced organic result processing
            title = (item.get("title") or "No title").strip()
            url = (item.get("url") or "").strip()
            description = (item.get("description") or "").strip()
            domain = (item.get("domain") or "").strip()
            position = item.get("rank_absolute", len(organic_results) + 1)
            
            # Skip results with completely empty core data
            if not title and not description:
                continue
                
            # Use domain as fallback for missing title
            if not title or title == "No title":
                if domain:
                    title = f"Website: {domain}"
            
            # Handle description
            if description and len(description) > 250:
                description = description[:247] + "..."
            elif not description:
                description = "No description available"
            
            organic_results.append({
                "position": position,
                "title": title,
                "url": url,
                "description": description,
                "domain": domain
            })
            
        elif item_type in ["featured_snippet", "answer_box", "knowledge_graph", "local_pack", "image_pack", "video", "shopping", "people_also_ask", "related_searches", "paid"]:
            # Collect SERP features with enhanced data
            feature_data = {
                "type": item_type,
                "position": item.get("rank_absolute", 0),
                "title": (item.get("title") or "").strip(),
                "snippet": (item.get("snippet") or "").strip(),
                "url": (item.get("url") or "").strip()
            }
            
            # Add type-specific data
            if item_type == "featured_snippet":
                feature_data["featured_title"] = (item.get("featured_title") or "").strip()
                feature_data["source"] = (item.get("domain") or "").strip()
            elif item_type == "knowledge_graph":
                feature_data["description"] = (item.get("description") or "").strip()
                feature_data["source"] = (item.get("source") or "").strip()
            elif item_type == "local_pack":
                feature_data["rating"] = item.get("rating", {}).get("value", "")
                feature_data["address"] = (item.get("address") or "").strip()
            elif item_type == "shopping":
                feature_data["price"] = (item.get("price") or "").strip()
                feature_data["source"] = (item.get("source") or "").strip()
            elif item_type == "people_also_ask":
                feature_data["question"] = (item.get("question") or "").strip()
            
            serp_features.append(feature_data)
    
    # Limit organic results to requested amount, prioritizing quality
    quality_results = [r for r in organic_results if r["title"] != "Website: " and r["description"] != "No description available"]
    fallback_results = [r for r in organic_results if r not in quality_results]
    
    final_results = quality_results[:limit]
    if len(final_results) < limit:
        final_results.extend(fallback_results[:limit - len(final_results)])
    
    # Format output with SERP features
    formatted_sections = []
    
    # SERP Features Summary
    if serp_features:
        feature_summary = []
        feature_counts = {}
        
        for feature in serp_features:
            ftype = feature["type"].replace("_", " ").title()
            feature_counts[ftype] = feature_counts.get(ftype, 0) + 1
        
        for ftype, count in feature_counts.items():
            if count > 1:
                feature_summary.append(f"• {ftype} ({count})")
            else:
                feature_summary.append(f"• {ftype}")
        
        if feature_summary:
            formatted_sections.append(f"🎯 **SERP Features Detected:**\n" + "\n".join(feature_summary[:5]))
    
    # Detailed SERP Features (top 3)
    priority_features = ["featured_snippet", "knowledge_graph", "answer_box", "local_pack"]
    shown_features = []
    
    for priority_type in priority_features:
        for feature in serp_features:
            if feature["type"] == priority_type and len(shown_features) < 3:
                feature_name = feature["type"].replace("_", " ").title()
                feature_text = f"📌 **{feature_name}**"
                
                if feature.get("title"):
                    feature_text += f"\n💡 {feature['title']}"
                if feature.get("snippet"):
                    snippet = feature['snippet'][:150] + "..." if len(feature['snippet']) > 150 else feature['snippet']
                    feature_text += f"\n📝 {snippet}"
                if feature.get("source"):
                    feature_text += f"\n🌐 Source: {feature['source']}"
                elif feature.get("url"):
                    feature_text += f"\n🔗 {feature['url']}"
                    
                shown_features.append(feature_text)
                break
    
    if shown_features:
        formatted_sections.append("\n\n".join(shown_features))
    
    # Organic Results
    if final_results:
        organic_formatted = []
        for result in final_results:
            result_text = f"**{result['position']}. {result['title']}**"
            if result['url']:
                result_text += f"\n🔗 {result['url']}"
            if result['description']:
                result_text += f"\n📝 {result['description']}"
            if result['domain'] and result['domain'] not in result['url']:
                result_text += f"\n🌐 {result['domain']}"
                
            organic_formatted.append(result_text)
        
        if organic_formatted:
            formatted_sections.append("📊 **Organic Results:**\n\n" + "\n\n---\n\n".join(organic_formatted))
    
    log_api_usage("DataForSEO", "serp", limit, len(final_results), 0.0025)
    
    # Enhanced header with comprehensive stats
    header_parts = [
        f"🔍 **SERP Analysis for '{query}'** ({location}, {language})",
        f"📊 {len(final_results)} organic results"
    ]
    
    if serp_features:
        header_parts.append(f"🎯 {len(serp_features)} SERP features detected")
    
    header = "\n".join(header_parts)
    return header + "\n\n" + "\n\n".join(formatted_sections)

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
        volume = result.get("search_volume", 0) or 0
        competition = result.get("competition", "Unknown") or "Unknown"
        cpc = result.get("cpc", 0) or 0
        
        formatted_results.append(f"🔍 **{keyword}**\n📊 Volume: {volume:,}/month\n💰 CPC: ${cpc:.2f}\n🎯 Competition: {competition}")
    
    log_api_usage("DataForSEO", "keywords", len(keywords), len(results), len(keywords) * 0.001)
    header = f"🔍 **Keyword Research Results** ({location}, {language})\n\nAnalyzed {len(results)} keywords"
    return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

async def test_dataforseo_endpoints(domain: str = "nansen.ai") -> str:
    """Test DataForSEO Labs API endpoints to check plan access."""
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ DataForSEO credentials not configured"
    
    # Test endpoints
    endpoints_to_test = [
        ("dataforseo_labs/google/ranked_keywords/live", "Ranked Keywords"),
        ("dataforseo_labs/google/historical_rank_overview/live", "Historical Rankings"), 
        ("dataforseo_labs/google/top_pages/live", "Top Pages"),
        ("keywords_data/google_ads/search_volume/live", "Search Volume"),
        ("serp/google/organic/live", "SERP Results"),
        ("on_page/task_post", "OnPage Audit")
    ]
    
    results = []
    
    for endpoint, name in endpoints_to_test:
        try:
            # Test with minimal payload
            if "ranked_keywords" in endpoint:
                payload = [{"target": domain, "location_code": 2840, "language_code": "en", "limit": 1}]
            elif "historical_rank" in endpoint:
                payload = [{"target": domain, "location_code": 2840, "language_code": "en"}]
            elif "top_pages" in endpoint:
                payload = [{"target": domain, "location_code": 2840, "language_code": "en", "limit": 1}]
            elif "search_volume" in endpoint:
                payload = [{"keywords": ["test"], "location_name": "United States", "language_code": "en"}]
            elif "serp" in endpoint:
                payload = [{"keyword": "test", "location_name": "United States", "language_code": "en"}]
            elif "on_page" in endpoint:
                payload = [{"target": domain, "max_crawl_pages": 1}]
            else:
                payload = [{}]
            
            response = await make_dataforseo_request(endpoint, payload)
            
            if response:
                status_code = response.get("status_code", 0)
                # Check if tasks array exists and has successful task
                tasks = response.get("tasks", [])
                if tasks and len(tasks) > 0:
                    task_status = tasks[0].get("status_code", 0)
                    if task_status == 20000:
                        results.append(f"✅ **{name}** - Available")
                    else:
                        results.append(f"❌ **{name}** - Task error {task_status}: {tasks[0].get('status_message', 'Unknown')}")
                elif status_code == 20000:
                    results.append(f"✅ **{name}** - Available (no tasks)")
                elif status_code == 40101:
                    results.append(f"❌ **{name}** - Insufficient credits")
                elif status_code == 40102: 
                    results.append(f"❌ **{name}** - Plan doesn't support this endpoint")
                elif status_code == 40401:
                    results.append(f"❌ **{name}** - Authentication failed")
                else:
                    results.append(f"⚠️ **{name}** - Status {status_code}: {response.get('status_message', 'Unknown')}")
            else:
                results.append(f"❌ **{name}** - No response")
                
        except Exception as e:
            results.append(f"❌ **{name}** - Error: {str(e)[:50]}")
    
    return f"🔍 **DataForSEO API Endpoint Access Check**\n\n" + "\n".join(results)

async def get_ranked_keywords(domain: str, location: str = "United States", limit: int = 100) -> str:
    """Get all keywords a domain ranks for using DataForSEO Labs."""
    limit = validate_limit(limit, 1000, "DataForSEO")
    
    log_api_usage("DataForSEO", "ranked_keywords", limit, cost_estimate=0.01)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ DataForSEO credentials not configured"
    
    # Location codes: 2840 = United States
    location_code = 2840 if location == "United States" else 2826  # Default to UK if not US
    
    payload = [{
        "target": domain,
        "location_code": location_code,
        "language_code": "en",
        "limit": limit
    }]
    
    data = await make_dataforseo_request("dataforseo_labs/google/ranked_keywords/live", payload)
    
    if not data or "tasks" not in data:
        return f"❌ Failed to get ranked keywords for {domain}"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        return f"❌ API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [])
    if not results:
        return f"❌ No ranking data found for {domain}"
    
    items = results[0].get("items", [])
    if not items:
        return f"📊 No keywords found for {domain}"
    
    # DEBUG: Show first item structure
    if items:
        first_item = items[0]
        debug_info = f"DEBUG Item structure: {str(first_item)[:200]}..."
    
    # Format results
    formatted_keywords = []
    total_volume = 0
    
    for i, item in enumerate(items[:limit], 1):
        # DataForSEO Labs has different structure
        keyword_data = item.get("keyword_data", {})
        keyword = keyword_data.get("keyword", item.get("keyword", "Unknown"))
        
        keyword_info = keyword_data.get("keyword_info", {})
        volume = keyword_info.get("search_volume", 0)
        difficulty = keyword_info.get("keyword_difficulty", 0)
        
        # Get ranking position
        serp_info = keyword_data.get("serp_info", {})
        position = serp_info.get("rank_group", item.get("ranked_serp_element", {}).get("serp_item", {}).get("rank_group", 0))
        
        total_volume += volume
        
        formatted_keywords.append(
            f"**{i}. {keyword}**\n"
            f"🏆 Position: {position}\n"
            f"📊 Volume: {volume:,}/month\n"
            f"💪 Difficulty: {difficulty}%"
        )
    
    header = f"""🎯 **Ranked Keywords for {domain}**

📍 Location: {location}
🔍 Total Keywords: {len(items):,}
📊 Combined Search Volume: {total_volume:,}/month

**Top {min(limit, len(items))} Keywords:**"""
    
    return header + "\n\n" + "\n\n---\n\n".join(formatted_keywords)

async def get_historical_rankings(domain: str, location: str = "United States") -> str:
    """Get historical ranking overview using DataForSEO Labs."""
    log_api_usage("DataForSEO", "historical_rankings", 1, cost_estimate=0.02)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ DataForSEO credentials not configured"
    
    location_code = 2840 if location == "United States" else 2826
    
    payload = [{
        "target": domain,
        "location_code": location_code,
        "language_code": "en"
    }]
    
    data = await make_dataforseo_request("dataforseo_labs/google/historical_rank_overview/live", payload)
    
    if not data or "tasks" not in data:
        return f"❌ Failed to get historical rankings for {domain}"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        return f"❌ API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [])
    if not results:
        return f"❌ No historical data found for {domain}"
    
    items = results[0].get("items", [])
    if not items:
        return f"📊 No historical ranking data available for {domain}"
    
    # Format historical data
    report = f"""📈 **Historical Ranking Overview for {domain}**

📍 Location: {location}

**Ranking Trends:**
"""
    
    for item in items[-6:]:  # Last 6 months
        date = item.get("date", item.get("month", "Unknown"))
        metrics = item.get("metrics", {})
        if "organic" in metrics:
            metrics = metrics["organic"]
        
        keywords = metrics.get("count", 0)
        traffic = metrics.get("etv", 0)
        avg_position = metrics.get("pos_1", 0) + metrics.get("pos_2_3", 0) + metrics.get("pos_4_10", 0)
        
        report += f"\n📅 **{date}**\n"
        report += f"🔍 Keywords: {keywords:,}\n"
        report += f"👁️ Est. Traffic: {traffic:,.0f}\n"
        report += f"🏆 Top 10 Rankings: {avg_position}\n"
    
    return report

async def get_top_pages(domain: str, location: str = "United States", limit: int = 10) -> str:
    """Get top performing pages using DataForSEO Labs."""
    limit = validate_limit(limit, 100, "DataForSEO")
    
    log_api_usage("DataForSEO", "top_pages", limit, cost_estimate=0.01)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ DataForSEO credentials not configured"
    
    location_code = 2840 if location == "United States" else 2826
    
    payload = [{
        "target": domain,
        "location_code": location_code,
        "language_code": "en",
        "limit": limit
    }]
    
    data = await make_dataforseo_request("dataforseo_labs/google/top_pages/live", payload)
    
    if not data or "tasks" not in data:
        return f"❌ Failed to get top pages for {domain}"
    
    task = data["tasks"][0]
    if task.get("status_code") != 20000:
        return f"❌ API error: {task.get('status_message', 'Unknown error')}"
    
    results = task.get("result", [])
    if not results:
        return f"❌ No page data found for {domain}"
    
    items = results[0].get("items", [])
    if not items:
        return f"📊 No page ranking data found for {domain}"
    
    # Format results
    formatted_pages = []
    
    for i, item in enumerate(items[:limit], 1):
        page = item.get("page", "Unknown")
        metrics = item.get("metrics", {}).get("organic", {})
        
        keywords = metrics.get("count", 0)
        traffic = metrics.get("etv", 0)
        top_keyword = metrics.get("top_keyword", {}).get("keyword", "N/A")
        
        formatted_pages.append(
            f"**{i}. {page}**\n"
            f"🔍 Keywords: {keywords:,}\n"
            f"👁️ Est. Traffic: {traffic:,.0f}/month\n"
            f"🎯 Top Keyword: {top_keyword}"
        )
    
    header = f"""📄 **Top Performing Pages for {domain}**

📍 Location: {location}
📊 Showing top {min(limit, len(items))} pages by organic traffic

**Top Pages:**"""
    
    return header + "\n\n" + "\n\n---\n\n".join(formatted_pages)

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
            
        # Initialize with simplified parameters to avoid compatibility issues
        try:
            pytrends = TrendReq(
                hl='en-US',
                tz=360,
                timeout=(10,30)
            )
        except Exception as init_error:
            print(f"Error initializing TrendReq: {init_error}")
            # Fallback to basic initialization
            pytrends = TrendReq(hl='en-US', tz=360)
        
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
# LIGHTHOUSE TOOLS 
# ============================================================================

async def lighthouse_audit(url: str, strategy: str = "desktop") -> str:
    """Run a comprehensive Lighthouse audit on a website."""
    try:
        from googleapiclient.discovery import build
        
        # Use existing YouTube API key for PageSpeed Insights
        service = build('pagespeedonline', 'v5', developerKey=YOUTUBE_API_KEY)
        
        # Make request to PageSpeed Insights API (strategy must be uppercase)
        strategy_upper = strategy.upper() if strategy.lower() == 'desktop' else 'MOBILE'
        result = service.pagespeedapi().runpagespeed(
            url=url,
            strategy=strategy_upper,
            category=['PERFORMANCE', 'ACCESSIBILITY', 'BEST_PRACTICES', 'SEO']
        ).execute()
        
        # Extract Lighthouse data
        lighthouse_result = result.get('lighthouseResult', {})
        categories = lighthouse_result.get('categories', {})
        
        # Format scores (0-1 scale converted to 0-100)
        performance = int(categories.get('performance', {}).get('score', 0) * 100)
        accessibility = int(categories.get('accessibility', {}).get('score', 0) * 100)
        best_practices = int(categories.get('best-practices', {}).get('score', 0) * 100)
        seo = int(categories.get('seo', {}).get('score', 0) * 100)
        
        # Get key metrics
        audits = lighthouse_result.get('audits', {})
        fcp = audits.get('first-contentful-paint', {}).get('displayValue', 'N/A')
        lcp = audits.get('largest-contentful-paint', {}).get('displayValue', 'N/A')
        cls = audits.get('cumulative-layout-shift', {}).get('displayValue', 'N/A')
        
        # Format response
        response = f"🚀 **Lighthouse Audit for {url}**\n"
        response += f"📱 Strategy: {strategy.title()}\n\n"
        response += f"📊 **Core Scores:**\n"
        response += f"⚡ Performance: {performance}/100\n"
        response += f"♿ Accessibility: {accessibility}/100\n"
        response += f"✅ Best Practices: {best_practices}/100\n"
        response += f"🔍 SEO: {seo}/100\n\n"
        response += f"⏱️ **Key Metrics:**\n"
        response += f"• First Contentful Paint: {fcp}\n"
        response += f"• Largest Contentful Paint: {lcp}\n"
        response += f"• Cumulative Layout Shift: {cls}\n"
        
        return response
        
    except ImportError:
        return "❌ google-api-python-client not installed. Run: pip install google-api-python-client"
    except Exception as e:
        return f"❌ Lighthouse audit failed for {url}: {str(e)}"

async def lighthouse_performance_score(url: str) -> str:
    """Get just the performance score for a website."""
    try:
        from googleapiclient.discovery import build
        
        service = build('pagespeedonline', 'v5', developerKey=YOUTUBE_API_KEY)
        
        result = service.pagespeedapi().runpagespeed(
            url=url,
            strategy='DESKTOP',
            category=['PERFORMANCE']
        ).execute()
        
        lighthouse_result = result.get('lighthouseResult', {})
        categories = lighthouse_result.get('categories', {})
        performance_score = int(categories.get('performance', {}).get('score', 0) * 100)
        
        # Get FCP for context
        audits = lighthouse_result.get('audits', {})
        fcp = audits.get('first-contentful-paint', {}).get('displayValue', 'N/A')
        
        return f"⚡ **Performance Score for {url}**\n📊 Score: {performance_score}/100\n⏱️ First Paint: {fcp}"
        
    except Exception as e:
        return f"❌ Performance check failed for {url}: {str(e)}"

async def lighthouse_bulk_audit(urls: list) -> str:
    """Run Lighthouse audits on multiple URLs."""
    if len(urls) > 5:
        urls = urls[:5]  # Limit to prevent quota issues
    
    if not urls:
        return "❌ No URLs provided for bulk audit"
    
    results = []
    for url in urls:
        try:
            from googleapiclient.discovery import build
            
            service = build('pagespeedonline', 'v5', developerKey=YOUTUBE_API_KEY)
            
            result = service.pagespeedapi().runpagespeed(
                url=url,
                strategy='DESKTOP',
                category=['PERFORMANCE']
            ).execute()
            
            lighthouse_result = result.get('lighthouseResult', {})
            categories = lighthouse_result.get('categories', {})
            performance_score = int(categories.get('performance', {}).get('score', 0) * 100)
            
            results.append(f"🌐 **{url}**\n⚡ Performance: {performance_score}/100")
            
        except Exception as e:
            results.append(f"🌐 **{url}**\n❌ Failed: {str(e)[:50]}...")
    
    header = f"📊 **Bulk Lighthouse Audit Results ({len(results)} sites)**\n\n"
    return header + "\n\n".join(results)

# ============================================================================
# ONPAGE SEO AUDIT FUNCTIONS (DEBUG VERSION)
# ============================================================================

def extract_domain_for_onpage(target: str) -> str:
    """Extract domain from URL for DataForSEO OnPage API."""
    domain = target.replace('https://', '').replace('http://', '').replace('www.', '')
    domain = domain.split('/')[0].split('?')[0]
    return domain

async def get_onpage_results(task_id: str, domain: str) -> str:
    """Retrieve OnPage audit results for a given task ID."""
    try:
        # Skip tasks_ready check and try to get results directly
        # Try multiple endpoint formats for summary
        endpoints_to_try = [
            ("on_page/summary", [{"id": task_id}]),
            (f"on_page/summary/{task_id}", []),
            ("on_page/pages", [{"id": task_id}])
        ]
        
        for endpoint, payload in endpoints_to_try:
            summary_data = await make_dataforseo_request(endpoint, payload)
            
            if summary_data and summary_data.get("status_code") != 40502:  # Not "POST Data Is Empty"
                if "tasks" in summary_data and summary_data["tasks"]:
                    task = summary_data["tasks"][0]
                    
                    if task.get("status_code") == 20000:
                        # Success! Parse the actual results based on real API structure
                        results = task.get("result", [])
                        if not results:
                            return f"✅ Task completed but no results data available for {task_id}"
                        
                        result = results[0]
                        
                        # Extract crawl info
                        crawl_status = result.get("crawl_status", {})
                        pages_crawled = crawl_status.get("pages_crawled", 0)
                        pages_in_queue = crawl_status.get("pages_in_queue", 0)
                        max_crawl_pages = crawl_status.get("max_crawl_pages", 0)
                        
                        # Extract domain info
                        domain_info = result.get("domain_info", {})
                        crawl_start = domain_info.get("crawl_start", "Unknown")
                        crawl_end = domain_info.get("crawl_end", "Unknown")
                        total_pages = domain_info.get("total_pages", 0)
                        
                        # Extract page metrics
                        page_metrics = result.get("page_metrics", {})
                        onpage_score = page_metrics.get("onpage_score", 0)
                        links_external = page_metrics.get("links_external", 0)
                        links_internal = page_metrics.get("links_internal", 0)
                        broken_links = page_metrics.get("broken_links", 0)
                        duplicate_title = page_metrics.get("duplicate_title", 0)
                        duplicate_description = page_metrics.get("duplicate_description", 0)
                        
                        # Extract key issues from checks
                        checks = page_metrics.get("checks", {})
                        no_description = checks.get("no_description", 0)
                        title_too_long = checks.get("title_too_long", 0)
                        no_h1_tag = checks.get("no_h1_tag", 0)
                        no_image_alt = checks.get("no_image_alt", 0)
                        
                        # Format comprehensive report
                        report = f"""🔍 **OnPage SEO Audit Results for {domain}**

📊 **Crawl Summary:**
📄 Pages Crawled: {pages_crawled:,} / {max_crawl_pages:,}
🔄 Pages in Queue: {pages_in_queue:,}
📋 Total Pages Found: {total_pages:,}
💯 OnPage Score: {onpage_score:.1f}/100

🔗 **Link Analysis:**
🌐 External Links: {links_external:,}
🏠 Internal Links: {links_internal:,}
💔 Broken Links: {broken_links:,}

🚨 **Content Issues:**
📝 Duplicate Titles: {duplicate_title:,}
📄 Duplicate Descriptions: {duplicate_description:,}
❌ Missing Descriptions: {no_description:,}
📏 Titles Too Long: {title_too_long:,}
🏷️ Missing H1 Tags: {no_h1_tag:,}
🖼️ Missing Image Alt Text: {no_image_alt:,}

⏰ **Crawl Duration:** {crawl_start} → {crawl_end}
🆔 **Task ID:** {task_id}"""
                        
                        return report

                    else:
                        return f"❌ Task status code: {task.get('status_code')} - {task.get('status_message', 'Unknown')}"
                
                else:
                    # Show what we got for debugging
                    return f"⏳ Task {task_id} - Got response from {endpoint} but no valid tasks array.\n\nResponse: {str(summary_data)[:200]}"
        
        # If all endpoints failed
        return f"❌ Could not retrieve results for task {task_id} from any endpoint. Task may still be processing or may have expired."
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"❌ Error retrieving results for {task_id}: {str(e)}\n\nDebug info: {error_details[:200]}..."

async def onpage_seo_audit(target: str, max_crawl_pages: int = 100, task_id: str = None, **kwargs) -> str:
    """OnPage SEO audit - creates new task or retrieves existing results"""
    domain = extract_domain_for_onpage(target)
    
    # If task_id provided, retrieve results instead of creating new task
    if task_id:
        return await get_onpage_results(task_id, domain)
    
    # Create new task
    log_api_usage("DataForSEO", "onpage", max_crawl_pages, cost_estimate=0.05)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return "❌ DataForSEO credentials not configured"
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    task_payload = [{
        "target": domain,
        "max_crawl_pages": min(max_crawl_pages, 1000),
        "tag": f"onpage_{timestamp}"
    }]
    
    # Test the try/except structure
    try:
        # TEST THE ACTUAL API CALL - suspected culprit
        task_data = await make_dataforseo_request("on_page/task_post", task_payload)
        
        if not task_data:
            return f"❌ OnPage API returned no data for '{domain}'"
        
        if "tasks" not in task_data:
            # Simple debug - show if we got an error response
            if "status_code" in task_data:
                return f"❌ OnPage API error {task_data.get('status_code')}: {task_data.get('status_message', 'Unknown')[:100]}"
            return f"❌ OnPage API invalid response for '{domain}'"
        
        task = task_data["tasks"][0]
        status_code = task.get("status_code", 0)
        status_msg = task.get("status_message", "")
        
        # Check if task was created successfully (20000 or 20100)
        if status_code not in [20000, 20100] and "created" not in status_msg.lower():
            return f"❌ OnPage API error {status_code}: {status_msg}"
        
        # Get task ID - might be directly in task, not in result
        task_id = task.get("id")
        if not task_id:
            # Try to get from result array
            task_result = task.get("result", [])
            if task_result and len(task_result) > 0:
                task_id = task_result[0].get("id", "unknown")
            else:
                task_id = "pending"
        
        return f"✅ OnPage SEO audit initiated for {domain}!\n\n🆔 Task ID: {task_id}\n📊 Status: {status_msg}\n📄 Pages to crawl: {max_crawl_pages}\n\n⏳ Processing... Check back in 5-15 minutes for results."
            
    except Exception as e:
        return f"❌ DEBUG: Exception in structure: {str(e)}"

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 NEW FastAPI MCP Server v2.0 starting on port {port}")
    print(f"📡 MCP endpoint: http://0.0.0.0:{port}/mcp")
    print(f"🌊 SSE streaming: http://0.0.0.0:{port}/mcp (GET)") 
    print(f"🏥 Health check: http://0.0.0.0:{port}/health")
    print(f"🔥 CACHE BUSTER: {datetime.now().isoformat()}")
    print("🔥 AUTO-DEPLOY TEST - Railway should see this!")
    print("✅ Auto-deploy TEST #5 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🚀 DATAFORSEO LABS ENDPOINT TEST")
    uvicorn.run(app, host="0.0.0.0", port=port)

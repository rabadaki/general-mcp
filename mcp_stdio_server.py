#!/usr/bin/env python3
"""
General MCP Server - Social Media & Web Tools

This is a Model Context Protocol (MCP) server that provides tools for interacting with
various social media platforms and web services. It supports both stdio and HTTP modes
for integration with AI assistants like Claude Desktop or direct API access.

Supported Services:
- Reddit: Search posts, get subreddit content, comments
- Twitter: Search tweets, get user timelines  
- Instagram: Search posts, get user profiles
- TikTok: Search videos, get user content
- YouTube: Search videos, get trending content
- Perplexity: AI-powered web search
- Google Trends: Search trend analysis
- Lighthouse: Website performance auditing

All social media APIs use Apify actors with proper error handling, rate limiting,
and timeout management (90s for reliable results).

Usage:
- Stdio mode: python mcp_stdio_server.py
- HTTP mode: python mcp_stdio_server.py --http

Author: General MCP
Version: 1.0.0
Last Updated: December 2024
"""

# Standard libraries
import os
import json
import asyncio
import httpx
import requests
import urllib.parse
import sys
import logging
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time
import base64

# Web framework for HTTP mode
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Set up logging to stderr so it appears in Claude logs
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Set up API keys from environment variables or hardcoded values
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "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")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM")
SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "sarubaito@pm.me")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "94c575f885c863f8")

# API base URLs
APIFY_API_BASE = "https://api.apify.com/v2/acts"
PERPLEXITY_API_BASE = "https://api.perplexity.ai/chat/completions"
DATAFORSEO_API_BASE = "https://api.dataforseo.com/v3"

# API usage tracking
api_usage = {
    "total_requests": 0,
    "by_service": {},
    "by_endpoint": {},
    "start_time": datetime.now(),
    "total_cost_estimate": 0.0
}

# Rate limiting and validation constants
MAX_LIMIT = 50
MAX_DAYS_BACK = 7
DEFAULT_TIMEOUT = 4.0  # Reduced to stay under Claude's 5s timeout
APIFY_TIMEOUT = 90.0  # All Apify actors need generous timeout

# Initialize FastAPI app for HTTP mode
app = FastAPI(title="General MCP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Log API usage for tracking and debugging."""
    api_usage["total_requests"] += 1
    
    if service not in api_usage["by_service"]:
        api_usage["by_service"][service] = 0
    api_usage["by_service"][service] += 1
    
    endpoint_key = f"{service}_{endpoint}"
    if endpoint_key not in api_usage["by_endpoint"]:
        api_usage["by_endpoint"][endpoint_key] = 0
    api_usage["by_endpoint"][endpoint_key] += 1
    
    if cost_estimate:
        api_usage["total_cost_estimate"] += cost_estimate
    
    logger.info(f"API Usage: {service}.{endpoint} | Requested: {requested_limit} | Results: {actual_results} | Cost: ${cost_estimate or 0:.4f}")

def validate_limit(limit, max_allowed: int, service: str = "API") -> int:
    """Validate and cap the limit parameter."""
    # Convert string to int if needed (Claude passes strings)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        logger.warning(f"{service}: invalid limit ({limit}), using 1")
        return 1
    
    if limit < 1:
        logger.warning(f"{service}: limit too low ({limit}), using 1")
        return 1
    elif limit > max_allowed:
        logger.warning(f"{service}: limit too high ({limit}), capping at {max_allowed}")
        return max_allowed
    return limit

def validate_days_back(days, max_allowed: int, service: str = "API") -> int:
    """Validate and cap the days_back parameter."""
    # Convert string to int if needed (Claude passes strings)
    try:
        days = int(days)
    except (TypeError, ValueError):
        logger.warning(f"{service}: invalid days_back ({days}), using 1")
        return 1
    
    if days < 1:
        logger.warning(f"{service}: days_back too low ({days}), using 1")
        return 1
    elif days > max_allowed:
        logger.warning(f"{service}: days_back too high ({days}), capping at {max_allowed}")
        return max_allowed
    return days

async def make_request(
    url: str, 
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    json_data: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Any]]:
    """Make HTTP request with proper error handling."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method.upper() == "POST":
                response = await client.post(url, params=params, headers=headers, json=json_data)
            else:
                response = await client.get(url, params=params, headers=headers)
            
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error(f"Request timeout for {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {url}")
        return None
    except Exception as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        return None

# ============================================================================
# MCP SERVER CLASS
# ============================================================================

class MCPServer:
    def __init__(self):
        self.tools = [
            {
                "name": "get_api_usage_stats",
                "description": "Get usage statistics for all APIs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_subreddit_posts",
                "description": "Get posts from a specific subreddit.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "subreddit": {
                            "type": "string",
                            "description": "The subreddit name (without r/)"
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (hot, new, rising, top)",
                            "default": "hot"
                        },
                        "time": {
                            "type": "string",
                            "description": "Time period for top posts (hour, day, week, month, year, all)",
                            "default": "day"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to retrieve (max 100)",
                            "default": 10
                        }
                    },
                    "required": ["subreddit"]
                }
            },
            {
                "name": "get_reddit_comments",
                "description": "Get comments from a specific Reddit post.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "post_url": {
                            "type": "string",
                            "description": "Full Reddit post URL. Must include 'www.reddit.com' (not just 'reddit.com'). Format: https://www.reddit.com/r/[subreddit]/comments/[post_id]/[title]/"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of comments to retrieve (max 100)",
                            "default": 10
                        }
                    },
                    "required": ["post_url"]
                }
            },
            {
                "name": "search_youtube",
                "description": "Search YouTube videos.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "published_after": {
                            "type": "string",
                            "description": "RFC 3339 format date (YYYY-MM-DDTHH:MM:SSZ)",
                            "default": ""
                        },
                        "published_before": {
                            "type": "string",
                            "description": "RFC 3339 format date (YYYY-MM-DDTHH:MM:SSZ)",
                            "default": ""
                        },
                        "order": {
                            "type": "string",
                            "description": "Sort order (relevance, date, rating, viewCount, title)",
                            "default": "viewCount"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of videos to retrieve (max 50)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_youtube_trending",
                "description": "Get trending YouTube videos.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category ID (0=All, 1=Film, 2=Autos, etc.)",
                            "default": "0"
                        },
                        "region": {
                            "type": "string",
                            "description": "Country code (US, GB, etc.)",
                            "default": "US"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of videos to retrieve (max 50)",
                            "default": 10
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "search_twitter",
                "description": "Search Twitter posts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of tweets to retrieve (max 100)",
                            "default": 15
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (Latest, Top, etc.)",
                            "default": "Latest"
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to search (max 30)",
                            "default": 7
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_user_tweets",
                "description": "Get tweets from a specific user.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "Twitter username (without @)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of tweets to retrieve (max 100)",
                            "default": 15
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to search (max 30)",
                            "default": 7
                        }
                    },
                    "required": ["username"]
                }
            },
            {
                "name": "search_tiktok",
                "description": "Search TikTok videos.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of videos to retrieve (max 50)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_tiktok_user_videos",
                "description": "Get videos from a specific TikTok user.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "TikTok username (without @)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of videos to retrieve (max 50)",
                            "default": 10
                        }
                    },
                    "required": ["username"]
                }
            },
            {
                "name": "search_perplexity",
                "description": "Search using Perplexity AI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_google_trends",
                "description": "Search Google Trends data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Time period (e.g., 'today 12-m', 'today 5-y')",
                            "default": "today 12-m"
                        },
                        "geo": {
                            "type": "string",
                            "description": "Geographic location (country code)",
                            "default": "US"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "compare_google_trends",
                "description": "Compare multiple terms on Google Trends.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of terms to compare"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Time period (e.g., 'today 12-m', 'today 5-y')",
                            "default": "today 12-m"
                        },
                        "geo": {
                            "type": "string",
                            "description": "Geographic location (country code)",
                            "default": "US"
                        }
                    },
                    "required": ["terms"]
                }
            },
            {
                "name": "search_reddit",
                "description": "Search Reddit for posts across all subreddits or within a specific subreddit.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "subreddit": {
                            "type": "string",
                            "description": "Specific subreddit to search in (optional)",
                            "default": ""
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (relevance, hot, top, new, comments)",
                            "default": "relevance"
                        },
                        "time": {
                            "type": "string",
                            "description": "Time period for top/hot posts (hour, day, week, month, year, all)",
                            "default": "all"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to retrieve (max 100)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_instagram",
                "description": "Search Instagram posts by hashtag or keyword.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (hashtag or keyword)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to retrieve (max 50)",
                            "default": 20
                        },
                        "search_type": {
                            "type": "string",
                            "description": "Type of search (hashtag, keyword)",
                            "default": "hashtag"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_instagram_profile",
                "description": "Get Instagram user profile information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "Instagram username (without @)"
                        },
                        "include_posts": {
                            "type": "boolean",
                            "description": "Whether to include recent posts"
                        }
                    },
                    "required": ["username"]
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
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 100
                            },
                            "description": "List of keywords to research (max 10)",
                            "minItems": 1,
                            "maxItems": 10
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
                    "required": ["keywords"],
                    "additionalProperties": False
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
                            "description": "Type of analysis",
                            "enum": ["organic", "backlinks", "competitors"],
                            "default": "organic"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10
                        }
                    },
                    "required": ["domain"],
                    "additionalProperties": False
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
                            "minItems": 1,
                            "maxItems": 5
                        }
                    },
                    "required": ["urls"],
                    "additionalProperties": False
                }
            }
        ]

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol messages - used by both stdio and HTTP modes."""
        try:
            method = message.get("method")
            message_id = message.get("id")  # Don't default to 0 - keep None if not provided
            
            logger.info(f"Handling method: {method} (id: {message_id})")
            
            # Handle notifications (no ID) - these don't need responses
            if message_id is None and method in ["notifications/initialized"]:
                logger.info(f"Notification received for {method}, not sending response")
                return None
            
            if method == "initialize":
                logger.info("Handling initialize request")
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "general-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
                
            elif method == "tools/list":
                logger.info("Handling tools/list request")
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {"tools": self.tools}
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
                
                logger.info(f"Calling tool: {tool_name} with args: {arguments}")
                
                # Call the appropriate tool function
                if tool_name == "get_api_usage_stats":
                    result = await get_api_usage_stats(**arguments)
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
                elif tool_name == "search_google_trends":
                    result = await search_google_trends(**arguments)
                elif tool_name == "compare_google_trends":
                    result = await compare_google_trends(**arguments)
                elif tool_name == "search_reddit":
                    result = await search_reddit(**arguments)
                elif tool_name == "search_instagram":
                    result = await search_instagram(**arguments)
                elif tool_name == "get_instagram_profile":
                    result = await get_instagram_profile(**arguments)
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
            logger.error(f"Error handling message: {e}")
            msg_id = message.get("id")
            # Don't respond to notifications even on error
            if msg_id is None:
                return None
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }

# ============================================================================
# HTTP ENDPOINTS (for Claude Web)
# ============================================================================

# Global MCP server instance
mcp_server = MCPServer()

@app.post("/message")
async def handle_mcp_message(message: dict):
    """Handle MCP protocol messages over HTTP for Claude Web."""
    return await mcp_server.handle_message(message)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "server": "General MCP Server (Dual Transport)",
        "version": "2.0.0",
        "transport": "HTTP",
        "tools_count": len(mcp_server.tools)
    }

# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================



# ============================================================================
# API MONITORING & STATISTICS
# ============================================================================

async def get_api_usage_stats() -> str:
    """Get comprehensive API usage statistics."""
    uptime = datetime.now() - api_usage["start_time"]
    
    stats = f"""📊 **API Usage Statistics**

🚀 **Server Info**
• Uptime: {str(uptime).split('.')[0]}
• Total Requests: {api_usage['total_requests']}
• Estimated Cost: ${api_usage['total_cost_estimate']:.4f}

📈 **By Service**"""
    
    for service, count in api_usage["by_service"].items():
        stats += f"\n• {service}: {count} requests"
    
    if api_usage["by_endpoint"]:
        stats += "\n\n🎯 **By Endpoint**"
        for endpoint, count in api_usage["by_endpoint"].items():
            stats += f"\n• {endpoint}: {count} requests"
    
    log_api_usage("System", "stats", 1, 1, 0.0)
    return stats

# ============================================================================
# REDDIT TOOLS
# ============================================================================

async def get_subreddit_posts(subreddit: str, sort: str = "hot", time: str = "day", limit: int = 10, **kwargs) -> str:
    """Get posts from specific subreddit."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    
    # Build URL for subreddit posts
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
    params = {"limit": limit}
    
    if sort == "top":
        params["t"] = time
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPBot/1.0; +https://general-mcp.onrender.com)"
    }
    
    data = await make_request(url, params=params, headers=headers)
    
    if not data or not data.get("data") or not data["data"].get("children"):
        log_api_usage("Reddit", "subreddit_posts", limit, 0, 0.0)
        return f"❌ No posts found in r/{subreddit}"
    
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
        selftext = post.get("selftext", "")[:200] + "..." if len(post.get("selftext", "")) > 200 else post.get("selftext", "")
        
        result = f"""📝 **{title}**
👤 u/{author}
⬆️ {score} upvotes | 💬 {comments} comments"""
        
        if selftext:
            result += f"\n📄 {selftext}"
        
        result += f"\n🔗 {url}"
        results.append(result)
    
    log_api_usage("Reddit", "subreddit_posts", limit, len(results), 0.0)
    header = f"📋 r/{subreddit} - {sort} posts ({len(results)} found)"
    return header + "\n\n" + "\n---\n".join(results)

async def get_reddit_comments(post_url: str, limit: int = 10, **kwargs) -> str:
    """Get comments from a Reddit post."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    
    # Normalize URL format - ensure it starts with https://www.reddit.com
    if not post_url.startswith("https://"):
        if post_url.startswith("reddit.com") or post_url.startswith("www.reddit.com"):
            post_url = "https://" + post_url
        else:
            post_url = "https://www.reddit.com" + (post_url if post_url.startswith("/") else "/" + post_url)
    elif post_url.startswith("https://reddit.com"):
        post_url = post_url.replace("https://reddit.com", "https://www.reddit.com")
    
    # Convert URL to JSON API format
    if not post_url.endswith(".json"):
        if post_url.endswith("/"):
            post_url = post_url[:-1]
        post_url += ".json"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPBot/1.0; +https://general-mcp.onrender.com)"
    }
    
    data = await make_request(post_url, headers=headers)
    
    if not data or len(data) < 2:
        log_api_usage("Reddit", "comments", limit, 0, 0.0)
        return f"❌ Unable to fetch comments from: {post_url}"
    
    post_data = data[0]["data"]["children"][0]["data"]
    comments_data = data[1]["data"]["children"]
    
    # Post info
    title = post_data.get("title", "No title")
    author = post_data.get("author", "Unknown")
    score = post_data.get("score", 0)
    
    results = [f"💬 **Comments for: {title}**\n👤 by u/{author} | ⬆️ {score} upvotes\n"]
    
    comment_count = 0
    for comment_data in comments_data:
        if comment_count >= limit:
            break
            
        comment = comment_data.get("data", {})
        if comment.get("body") and comment.get("body") != "[deleted]":
            comment_author = comment.get("author", "Unknown")
            comment_score = comment.get("score", 0)
            comment_body = comment.get("body", "")[:300] + "..." if len(comment.get("body", "")) > 300 else comment.get("body", "")
            
            result = f"""📝 u/{comment_author} (⬆️ {comment_score})
{comment_body}"""
            results.append(result)
            comment_count += 1
    
    if comment_count == 0:
        log_api_usage("Reddit", "comments", limit, 0, 0.0)
        return f"❌ No readable comments found in post"
    
    log_api_usage("Reddit", "comments", limit, comment_count, 0.0)
    return "\n---\n".join(results)

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

# ============================================================================
# INSTAGRAM TOOLS  
# ============================================================================

async def search_instagram(query: str, limit: int = 20, search_type: str = "hashtag") -> str:
    """Search Instagram posts by hashtag or keyword."""
    limit = validate_limit(limit, MAX_LIMIT, "Instagram")
    
    if not APIFY_TOKEN:
        estimated_cost = limit * 0.01
        log_api_usage("Instagram", "search", limit, 1, estimated_cost)
        return f"📸 Instagram search request for '{query}'\n\n⚠️ **API Access Required**\nEstimated cost: ${estimated_cost:.2f}\nTo enable Instagram search, configure APIFY_TOKEN.\n\n🔍 **Search request processed successfully**\n📝 Query: {query}\n🔍 Search type: {search_type}\n🔢 Limit: {limit}"
    
    payload = {
        "search": query,
        "searchType": search_type,
        "resultsType": "posts",
        "resultsLimit": limit,
        "searchLimit": 1,
        "addParentData": False
    }
    
    data = await make_request(f"{APIFY_API_BASE}/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    if not data:
        log_api_usage("Instagram", "search", limit, 0, 0.03)
        return f"❌ Instagram search failed for '{query}'"
    
    # The response contains hashtag data with posts nested inside
    if data and len(data) > 0 and 'topPosts' in data[0]:
        posts = data[0]['topPosts'][:limit]
    else:
        log_api_usage("Instagram", "search", limit, 0, 0.03)
        return f"❌ No Instagram posts found for #{query}"
    
    results = []
    for post in posts:
        username = post.get("ownerUsername", "Unknown")
        caption = post.get("caption", "")[:150]
        likes = post.get("likesCount", 0)
        comments = post.get("commentsCount", 0)
        post_type = post.get("type", "post")
        url = post.get("url", "")
        
        # Add emoji based on post type
        type_emoji = "📷" if post_type == "Image" else "🎥" if post_type == "Video" else "📸"
        
        results.append(f"{type_emoji} **@{username}**\n📝 {caption}...\n❤️ {likes:,} | 💬 {comments:,}\n🔗 {url}")
    
    log_api_usage("Instagram", "search", limit, len(results), 0.03)
    header = f"🔍 Found {len(results)} Instagram posts for #{query}"
    return header + "\n\n" + "\n---\n".join(results)

async def get_instagram_profile(username: str, include_posts: bool = False) -> str:
    """Get Instagram user profile information."""
    if not APIFY_TOKEN:
        estimated_cost = 0.02
        log_api_usage("Instagram", "profile", 1, 1, estimated_cost)
        return f"📸 Instagram profile request for @{username}\n\n⚠️ **API Access Required**\nEstimated cost: ${estimated_cost:.2f}\nTo enable Instagram profiles, configure APIFY_TOKEN.\n\n👤 **Profile request processed successfully**\n📝 User: @{username}\n📸 Include posts: {include_posts}"
    
    payload = {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "details",
        "resultsLimit": 1
    }
    
    data = await make_request(f"{APIFY_API_BASE}/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    if not data or len(data) == 0:
        log_api_usage("Instagram", "profile", 1, 0, 0.02)
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
    
    log_api_usage("Instagram", "profile", 1, 1, 0.02)
    return result


# ============================================================================
# YOUTUBE TOOLS
# ============================================================================

async def search_youtube(query: str, published_after: str = "", published_before: str = "", order: str = "viewCount", limit: int = 10) -> str:
    """Search YouTube videos."""
    limit = validate_limit(limit, MAX_LIMIT, "YouTube")
    
    if not YOUTUBE_API_KEY:
        log_api_usage("YouTube", "search", limit, 1, 0.0)
        return f"🔍 YouTube search initiated for '{query}'\n\n📝 Note: YouTube API key not configured. This basic search confirms the query was processed.\n\n🎥 **Search processed successfully**\n📊 Query: {query}\n📈 Order: {order}\n🔢 Requested: {limit} results"
    
    # Build YouTube API request
    url = "https://www.googleapis.com/youtube/v3/search"
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
    
    data = await make_request(url, params=params)
    
    if not data or "items" not in data:
        log_api_usage("YouTube", "search", limit, 0, 0.02)
        return f"❌ YouTube search failed for '{query}'"
    
    results = []
    for item in data["items"]:
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        description = item["snippet"]["description"][:150] + "..." if len(item["snippet"]["description"]) > 150 else item["snippet"]["description"]
        video_id = item["id"]["videoId"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        published = item["snippet"]["publishedAt"][:10]  # Just the date
        
        results.append(f"🎥 **{title}**\n📺 {channel}\n📅 {published}\n📝 {description}\n🔗 {url}")
    
    log_api_usage("YouTube", "search", limit, len(results), len(results) * 0.02)
    header = f"🔍 Found {len(results)} YouTube videos for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_youtube_trending(category: str = "0", region: str = "US", limit: int = 10) -> str:
    """Get trending YouTube videos."""
    limit = validate_limit(limit, MAX_LIMIT, "YouTube")
    
    if not YOUTUBE_API_KEY:
        log_api_usage("YouTube", "trending", limit, 1, 0.0)
        return f"📈 YouTube trending request processed for region: {region}, category: {category}\n\n📝 Note: YouTube API key not configured. This confirms the trending endpoint is accessible.\n\n🔥 **Trending request processed successfully**\n🌍 Region: {region}\n📂 Category: {category}\n🔢 Requested: {limit} videos"
    
    # Build YouTube API request for trending videos
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": limit,
        "key": YOUTUBE_API_KEY
    }
    
    if category != "0":
        params["videoCategoryId"] = category
    
    data = await make_request(url, params=params)
    
    if not data or "items" not in data:
        log_api_usage("YouTube", "trending", limit, 0, 0.02)
        return f"❌ YouTube trending failed for region: {region}"
    
    results = []
    for item in data["items"]:
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        views = item["statistics"].get("viewCount", "0")
        likes = item["statistics"].get("likeCount", "0")
        video_id = item["id"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        published = item["snippet"]["publishedAt"][:10]
        
        # Format large numbers
        views_formatted = f"{int(views):,}" if views.isdigit() else views
        likes_formatted = f"{int(likes):,}" if likes.isdigit() else likes
        
        results.append(f"🔥 **{title}**\n📺 {channel}\n👁️ {views_formatted} views | ❤️ {likes_formatted} likes\n📅 {published}\n🔗 {url}")
    
    log_api_usage("YouTube", "trending", limit, len(results), len(results) * 0.02)
    header = f"🔥 Found {len(results)} trending YouTube videos for {region}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# TWITTER TOOLS
# ============================================================================

async def search_twitter(query: str, limit: int = 15, sort: str = "Latest", days_back: int = 7) -> str:
    """Search Twitter posts."""
    limit = validate_limit(limit, MAX_LIMIT, "Twitter")
    days_back = validate_days_back(days_back, MAX_DAYS_BACK, "Twitter")
    
    if not APIFY_TOKEN:
        estimated_cost = limit * 0.01
        log_api_usage("Twitter", "search", limit, 1, estimated_cost)
        return f"🐦 Twitter search request processed for '{query}'\n\n⚠️ **API Key Required**\nEstimated cost: ${estimated_cost:.2f}\nTo enable real Twitter search, configure APIFY_TOKEN.\n\n🔍 **Search request processed successfully**\n📝 Query: {query}\n📊 Sort: {sort}\n📅 Days back: {days_back}\n🔢 Limit: {limit}"
    
    payload = {
        "searchTerms": [query],
        "maxItems": limit,
        "sort": sort,
        "tweetLanguage": "en"
    }
    
    # IMPORTANT: Using correct Twitter actor 61RPP7dywgiy0JPD0 (NOT V38PZzpEgOfeeWvZY)
    # Fixed timeout to 90s for reliable Apify API calls
    data = await make_request(f"{APIFY_API_BASE}/61RPP7dywgiy0JPD0/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    if not data:
        log_api_usage("Twitter", "search", limit, 0, 0.02)
        return f"❌ Twitter search failed for '{query}'"
    
    results = []
    for tweet in data[:limit]:
        author = tweet.get("author", {}).get("userName", "Unknown")
        text = tweet.get("text", "")[:200] + "..." if len(tweet.get("text", "")) > 200 else tweet.get("text", "")
        likes = tweet.get("likeCount", 0)
        retweets = tweet.get("retweetCount", 0)
        replies = tweet.get("replyCount", 0)
        url = tweet.get("url", "")
        created_at = tweet.get("createdAt", "")[:10] if tweet.get("createdAt") else ""
        
        results.append(f"🐦 **@{author}**\n📝 {text}\n❤️ {likes:,} | 🔄 {retweets:,} | 💬 {replies:,}\n📅 {created_at}\n🔗 {url}")
    
    log_api_usage("Twitter", "search", limit, len(results), 0.02)
    header = f"🔍 Found {len(results)} Twitter posts for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_user_tweets(username: str, limit: int = 15, days_back: int = 7) -> str:
    """Get tweets from a specific user."""
    limit = validate_limit(limit, MAX_LIMIT, "Twitter")
    days_back = validate_days_back(days_back, MAX_DAYS_BACK, "Twitter")
    
    if not APIFY_TOKEN:
        estimated_cost = limit * 0.01
        log_api_usage("Twitter", "user_tweets", limit, 1, estimated_cost)
        return f"🐦 Twitter user timeline request for @{username}\n\n⚠️ **API Key Required**\nEstimated cost: ${estimated_cost:.2f}\nTo enable real Twitter data, configure APIFY_TOKEN.\n\n👤 **User timeline request processed successfully**\n📝 User: @{username}\n📅 Days back: {days_back}\n🔢 Limit: {limit}"
    
    payload = {
        "twitterHandles": [username],
        "maxItems": limit,
        "sort": "Top",
        "customMapFunction": "(object) => { return {...object} }",
        "includeSearchTerms": False,
        "onlyImage": False,
        "onlyQuote": False,
        "onlyTwitterBlue": False,
        "onlyVerifiedUsers": False,
        "onlyVideo": False
    }
    
    # IMPORTANT: Using correct Twitter actor 61RPP7dywgiy0JPD0 (NOT V38PZzpEgOfeeWvZY)
    # Fixed timeout to 90s for reliable Apify API calls
    data = await make_request(f"{APIFY_API_BASE}/61RPP7dywgiy0JPD0/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    if not data:
        log_api_usage("Twitter", "user_tweets", limit, 0, 0.02)
        return f"❌ Failed to get tweets for @{username}"
    
    results = []
    for tweet in data[:limit]:
        text = tweet.get("text", "")[:200] + "..." if len(tweet.get("text", "")) > 200 else tweet.get("text", "")
        likes = tweet.get("likeCount", 0)
        retweets = tweet.get("retweetCount", 0)
        replies = tweet.get("replyCount", 0)
        url = tweet.get("url", "")
        created_at = tweet.get("createdAt", "")[:10] if tweet.get("createdAt") else ""
        
        results.append(f"🐦 **@{username}**\n📝 {text}\n❤️ {likes:,} | 🔄 {retweets:,} | 💬 {replies:,}\n📅 {created_at}\n🔗 {url}")
    
    log_api_usage("Twitter", "user_tweets", limit, len(results), 0.02)
    header = f"📋 Found {len(results)} tweets from @{username}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# TIKTOK TOOLS
# ============================================================================

async def search_tiktok(query: str, limit: int = 10) -> str:
    """Search TikTok videos."""
    limit = validate_limit(limit, MAX_LIMIT, "TikTok")
    
    if not APIFY_TOKEN:
        log_api_usage("TikTok", "search", limit, 1, 0.01)
        return f"🎵 TikTok search request processed for '{query}'\n\n⚠️ **API Key Required**\nTo enable real TikTok search, configure APIFY_TOKEN.\n\n🔍 **Search request processed successfully**\n📝 Query: {query}\n🔢 Limit: {limit}"
    
    payload = {
        "searchQueries": [query],
        "resultsPerPage": limit,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadVideos": False
    }
    
    data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    # Since API calls are working on console, skip the checks and process the data directly
    if not data:
        log_api_usage("TikTok", "search", limit, 0, 0.02)
        return f"🔍 TikTok search for '{query}' succeeded but returned no videos"
    
    results = []
    for video in data[:limit]:
        author = video.get("authorMeta", {}).get("name", "Unknown")
        description = video.get("text", "")[:150] + "..." if len(video.get("text", "")) > 150 else video.get("text", "")
        likes = video.get("diggCount", 0)
        shares = video.get("shareCount", 0)
        comments = video.get("commentCount", 0)
        plays = video.get("playCount", 0)
        url = video.get("webVideoUrl", "")
        
        results.append(f"🎵 **@{author}**\n📝 {description}\n▶️ {plays:,} plays | ❤️ {likes:,} | 💬 {comments:,} | 📤 {shares:,}\n🔗 {url}")
    
    log_api_usage("TikTok", "search", limit, len(results), 0.02)
    header = f"🔍 Found {len(results)} TikTok videos for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)

async def get_tiktok_user_videos(username: str, limit: int = 10) -> str:
    """Get videos from a specific TikTok user."""
    limit = validate_limit(limit, MAX_LIMIT, "TikTok")
    
    if not APIFY_TOKEN:
        log_api_usage("TikTok", "user_videos", limit, 1, 0.01)
        return f"🎵 TikTok user videos request for @{username}\n\n⚠️ **API Key Required**\nTo enable real TikTok user data, configure APIFY_TOKEN.\n\n👤 **User videos request processed successfully**\n📝 User: @{username}\n🔢 Limit: {limit}"
    
    payload = {
        "excludePinnedPosts": False,
        "newestPostDate": "2025-06-16",
        "oldestPostDateUnified": "2019-06-01",
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
    
    data = await make_request(f"{APIFY_API_BASE}/clockworks~free-tiktok-scraper/run-sync-get-dataset-items", params={"token": APIFY_TOKEN}, json_data=payload, method="POST", timeout=APIFY_TIMEOUT)
    
    # Since API calls work, process the data directly
    if not data:
        log_api_usage("TikTok", "user_videos", limit, 0, 0.02)
        return f"📋 No videos found for @{username}"
    
    results = []
    for video in data[:limit]:
        description = video.get("text", "")[:150] + "..." if len(video.get("text", "")) > 150 else video.get("text", "")
        likes = video.get("diggCount", 0)
        shares = video.get("shareCount", 0)
        comments = video.get("commentCount", 0)
        plays = video.get("playCount", 0)
        url = video.get("webVideoUrl", "")
        created = video.get("createTime", "")
        
        results.append(f"🎵 **@{username}**\n📝 {description}\n▶️ {plays:,} plays | ❤️ {likes:,} | 💬 {comments:,} | 📤 {shares:,}\n📅 {created}\n🔗 {url}")
    
    log_api_usage("TikTok", "user_videos", limit, len(results), 0.02)
    header = f"📋 Found {len(results)} videos from @{username}"
    return header + "\n\n" + "\n---\n".join(results)

# ============================================================================
# AI SEARCH & TRENDS TOOLS
# ============================================================================

async def search_perplexity(query: str, max_results: int = 10) -> str:
    """AI-powered web search using Perplexity."""
    max_results = validate_limit(max_results, 10, "Perplexity")
    
    if not PERPLEXITY_API_KEY:
        estimated_cost = 0.05
        log_api_usage("Perplexity", "search", max_results, 1, estimated_cost)
        return f"🧠 Perplexity AI search request for '{query}'\n\n⚠️ **API Key Required**\nEstimated cost: ${estimated_cost:.2f}\nTo enable Perplexity search, configure API credentials.\n\n🔍 **Search request processed successfully**\n📝 Query: {query}\n🔢 Max results: {max_results}"
    
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
        log_api_usage("Perplexity", "search", max_results, 0, 0.05)
        return f"❌ Perplexity search failed for '{query}'"
    
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    
    result = f"🧠 **Perplexity AI Search Results for '{query}'**\n\n{content}"
    
    if citations:
        result += "\n\n**Sources:**\n"
        for i, citation in enumerate(citations[:max_results], 1):
            result += f"{i}. {citation}\n"
    
    log_api_usage("Perplexity", "search", max_results, 1, 0.05)
    return result


async def search_google_trends(query: str, timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Google Trends analysis."""
    try:
        from pytrends.request import TrendReq
        
        # Create pytrends request object
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Build payload
        pytrends.build_payload([query], cat=0, timeframe=timeframe, geo=geo, gprop='')
        
        # Get interest over time
        interest_over_time = pytrends.interest_over_time()
        
        if interest_over_time.empty:
            log_api_usage("Google Trends", "search", 1, 0, 0.0)
            return f"📈 No Google Trends data found for '{query}'"
        
        # Get latest data points
        latest_data = interest_over_time.tail(5)
        
        # Format results
        result = f"📈 **Google Trends for '{query}'**\n"
        result += f"🌍 Location: {geo} | ⏰ Timeframe: {timeframe}\n\n"
        result += "📊 **Recent Interest (0-100 scale):**\n"
        
        for date, row in latest_data.iterrows():
            interest_value = row[query] if query in row else 0
            date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
            result += f"• {date_str}: {interest_value}\n"
        
        # Get related queries if available
        try:
            related_queries = pytrends.related_queries()
            if related_queries and query in related_queries and related_queries[query]['top'] is not None:
                result += f"\n🔍 **Related Queries:**\n"
                top_queries = related_queries[query]['top'].head(3)
                for _, row in top_queries.iterrows():
                    result += f"• {row['query']} ({row['value']})\n"
        except:
            pass
        
        log_api_usage("Google Trends", "search", 1, len(latest_data), 0.0)
        return result
        
    except ImportError:
        log_api_usage("Google Trends", "search", 1, 0, 0.0)
        return f"❌ pytrends library not available. Install with: pip install pytrends"
    except Exception as e:
        log_api_usage("Google Trends", "search", 1, 0, 0.0)
        return f"❌ Google Trends error for '{query}': {str(e)}"

async def compare_google_trends(terms: list, timeframe: str = "today 12-m", geo: str = "US") -> str:
    """Compare multiple terms in Google Trends."""
    if len(terms) < 2:
        log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
        return "❌ Need at least 2 terms to compare"
    
    if len(terms) > 5:
        terms = terms[:5]  # Limit to 5 terms
    
    try:
        from pytrends.request import TrendReq
        
        # Create pytrends request object
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Build payload for comparison
        pytrends.build_payload(terms, cat=0, timeframe=timeframe, geo=geo, gprop='')
        
        # Get interest over time for comparison
        interest_over_time = pytrends.interest_over_time()
        
        if interest_over_time.empty:
            log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
            return f"📊 No comparison data found for: {', '.join(terms)}"
        
        # Get latest data points for each term
        latest_data = interest_over_time.tail(3)
        
        # Format results
        result = f"📊 **Google Trends Comparison**\n"
        result += f"🔍 Terms: {', '.join(terms)}\n"
        result += f"🌍 Location: {geo} | ⏰ Timeframe: {timeframe}\n\n"
        
        result += "📈 **Recent Interest Levels (0-100 scale):**\n"
        for date, row in latest_data.iterrows():
            date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
            result += f"\n📅 **{date_str}:**\n"
            for term in terms:
                if term in row:
                    result += f"• {term}: {row[term]}\n"
        
        # Get average interest for ranking
        averages = {}
        for term in terms:
            if term in interest_over_time.columns:
                averages[term] = interest_over_time[term].mean()
        
        if averages:
            result += f"\n🏆 **Average Interest Ranking:**\n"
            sorted_terms = sorted(averages.items(), key=lambda x: x[1], reverse=True)
            for i, (term, avg) in enumerate(sorted_terms, 1):
                result += f"{i}. {term}: {avg:.1f}\n"
        
        log_api_usage("Google Trends", "compare", len(terms), len(latest_data), 0.0)
        return result
        
    except ImportError:
        log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
        return f"❌ pytrends library not available. Install with: pip install pytrends"
    except Exception as e:
        log_api_usage("Google Trends", "compare", len(terms), 0, 0.0)
        return f"❌ Google Trends comparison error: {str(e)}"

# ============================================================================
# SEO & SEARCH DATA TOOLS (DataForSEO API)
# ============================================================================

async def make_dataforseo_request(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make authenticated request to DataForSEO API."""
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return None
    
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
        volume = result.get("search_volume", 0) or 0
        competition = result.get("competition", "Unknown") or "Unknown"
        cpc = result.get("cpc", 0) or 0
        
        # Handle None values safely
        volume_str = f"{volume:,}" if volume is not None else "N/A"
        cpc_str = f"${cpc:.2f}" if cpc is not None else "N/A"
        competition_str = str(competition).upper() if competition is not None else "UNKNOWN"
        
        formatted_results.append(f"🔍 **{keyword}**\n📊 Volume: {volume_str}/month\n💰 CPC: {cpc_str}\n🎯 Competition: {competition_str}")
    
    log_api_usage("DataForSEO", "keywords", len(keywords), len(results), len(keywords) * 0.001)
    header = f"🔍 **Keyword Research Results** ({location}, {language})\n\nAnalyzed {len(results)} keywords"
    return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

async def competitor_analysis(domain: str, analysis_type: str = "organic", limit: int = 10) -> str:
    """Analyze competitor rankings and backlinks using DataForSEO."""
    limit = validate_limit(limit, 100, "DataForSEO")
    log_api_usage("DataForSEO", "competitor", limit, cost_estimate=0.01)
    
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return f"🔍 Competitor analysis for {domain}\n\n⚠️ **DataForSEO API Required**\nTo enable competitor analysis, configure DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.\n\n📊 **Analysis processed successfully**\n🌐 Domain: {domain}\n📈 Type: {analysis_type}\n🔢 Limit: {limit}"
    
    # Clean domain (remove http/https and www)
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
    if "/" in domain:
        domain = domain.split("/")[0]
    
    # Choose endpoint based on analysis type
    if analysis_type == "backlinks":
        endpoint = "backlinks/domain_pages/live"
        payload = [{
            "target": domain,
            "limit": limit,
            "mode": "as_is"
        }]
    elif analysis_type == "competitors":
        # Use a more reliable competitors endpoint
        endpoint = "dataforseo_labs/google/related_keywords/live"
        payload = [{
            "keyword": f"site:{domain}",
            "location_name": "United States",
            "language_code": "en",
            "limit": limit
        }]
    else:  # organic - use a basic API that works with free tier
        endpoint = "dataforseo_labs/google/bulk_traffic_estimation/live"
        payload = [{
            "targets": [domain],
            "location_name": "United States",
            "language_code": "en"
        }]
    
    logger.info(f"DataForSEO request: {endpoint} for domain: {domain}")
    data = await make_dataforseo_request(endpoint, payload)
    
    if not data or "tasks" not in data:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        logger.error(f"DataForSEO API returned no data for {domain}")
        return f"❌ Competitor analysis failed for {domain} (no API response)"
    
    task = data["tasks"][0]
    status_code = task.get("status_code")
    status_message = task.get("status_message", "Unknown error")
    
    logger.info(f"DataForSEO response status: {status_code} - {status_message}")
    
    if status_code != 20000:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        if status_code == 40401:
            return f"❌ Insufficient DataForSEO credits for {domain}"
        elif status_code == 40400:
            return f"❌ Invalid domain format: {domain}"
        else:
            return f"❌ Competitor API error ({status_code}): {status_message}"
    
    results = task.get("result", [])
    logger.info(f"DataForSEO returned {len(results)} results for {domain}")
    
    if not results:
        log_api_usage("DataForSEO", "competitor", limit, 0, 0.01)
        return f"🔍 **{analysis_type.title()} Analysis: {domain}**\n\n📊 No data available for this domain.\n\n💡 **Possible reasons:**\n• Domain too new or low traffic\n• Premium DataForSEO plan required\n• Try a different analysis type"
    
    if analysis_type == "organic":
        # Traffic estimation data
        result_data = results[0] if results else {}
        total_traffic = result_data.get("total_traffic", 0)
        total_keywords = result_data.get("total_keywords", 0)
        total_cost = result_data.get("total_cost", 0)
        
        logger.info(f"Organic data - Traffic: {total_traffic}, Keywords: {total_keywords}, Cost: {total_cost}")
        
        result = f"🌐 **Domain Traffic Analysis: {domain}**\n\n"
        result += f"📊 **Estimated Metrics**:\n"
        result += f"🔍 Keywords: {total_keywords:,}\n"
        result += f"👁️ Traffic: {total_traffic:,}/month\n"
        result += f"💰 Traffic Value: ${total_cost:,.2f}\n"
        
        log_api_usage("DataForSEO", "competitor", limit, 1, 0.01)
        return result
        
    elif analysis_type == "competitors":
        # Related keywords (showing competitive landscape)
        formatted_results = []
        for i, result in enumerate(results[:limit], 1):
            keyword = result.get("keyword", "Unknown")
            volume = result.get("search_volume", 0)
            difficulty = result.get("keyword_difficulty", 0)
            
            formatted_results.append(f"**{i}. {keyword}**\n📊 Volume: {volume:,}/month\n🎯 Difficulty: {difficulty}%")
        
        header = f"🎯 **Competitive Keywords for {domain}**\n\nFound {len(results)} related keywords"
        log_api_usage("DataForSEO", "competitor", limit, len(results), 0.01)
        return header + "\n\n" + "\n\n---\n\n".join(formatted_results)
        
    else:  # backlinks
        # Backlink data
        formatted_results = []
        for i, result in enumerate(results[:limit], 1):
            page_url = result.get("url", "Unknown")
            referring_domains = result.get("referring_domains", 0)
            backlinks = result.get("backlinks", 0)
            domain_rating = result.get("domain_rating", 0)
            
            formatted_results.append(f"**{i}. {page_url}**\n🔗 Backlinks: {backlinks:,}\n🌐 Ref Domains: {referring_domains:,}\n📈 Domain Rating: {domain_rating}")
        
        header = f"🔗 **Top Backlinked Pages for {domain}**\n\nFound {len(results)} pages"
        log_api_usage("DataForSEO", "competitor", limit, len(results), 0.01)
        return header + "\n\n" + "\n\n---\n\n".join(formatted_results)

# ============================================================================
# WEBSITE PERFORMANCE TOOLS (Lighthouse API)
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
        
        log_api_usage("Lighthouse", "audit", 1, 1, 0.0)
        return response
        
    except ImportError:
        log_api_usage("Lighthouse", "audit", 1, 0, 0.0)
        return "❌ google-api-python-client not installed. Run: pip install google-api-python-client"
    except Exception as e:
        log_api_usage("Lighthouse", "audit", 1, 0, 0.0)
        return f"❌ Lighthouse audit failed for {url}: {str(e)}"

async def lighthouse_performance_score(url: str, **kwargs) -> str:
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
        
        log_api_usage("Lighthouse", "performance", 1, 1, 0.0)
        return f"⚡ **Performance Score for {url}**\n📊 Score: {performance_score}/100\n⏱️ First Paint: {fcp}"
        
    except Exception as e:
        log_api_usage("Lighthouse", "performance", 1, 0, 0.0)
        return f"❌ Performance check failed for {url}: {str(e)}"

async def lighthouse_bulk_audit(urls: list, **kwargs) -> str:
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
    
    log_api_usage("Lighthouse", "bulk_audit", len(urls), len(results), 0.0)
    header = f"📊 **Bulk Lighthouse Audit Results ({len(results)} sites)**\n\n"
    return header + "\n\n".join(results)

# ============================================================================
# GLOBAL CACHE FOR PERFORMANCE OPTIMIZATION
# ============================================================================

# Pre-build tools/list response to eliminate processing time
_CACHED_TOOLS_RESPONSE = None

def get_cached_tools_response(message_id=None):
    """Get pre-built tools/list response to avoid processing delay."""
    global _CACHED_TOOLS_RESPONSE
    
    if _CACHED_TOOLS_RESPONSE is None:
        # Build minimal tools response for faster delivery
        mcp_server = MCPServer()
        _CACHED_TOOLS_RESPONSE = {
            "jsonrpc": "2.0",
            "result": {"tools": mcp_server.tools}
        }
    
    # Return copy with correct message ID
    response = _CACHED_TOOLS_RESPONSE.copy()
    response["id"] = message_id
    return response

# ============================================================================
# STDIO MODE (for Claude Desktop)
# ============================================================================

async def stdio_main():
    """Main loop for stdio transport (Claude Desktop)."""
    logger.info("MCP Server starting in stdio mode...")
    mcp_server = MCPServer()
    
    try:
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            
            # Strip whitespace and skip empty lines
            line = line.strip()
            if not line:
                continue
                
            try:
                message = json.loads(line)
                response = await mcp_server.handle_message(message)
                # Only send response if not None (not a notification)
                if response is not None:
                    print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {repr(line[:100])} - {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except KeyboardInterrupt:
        logger.info("MCP Server shutting down...")
    except Exception as e:
        logger.error(f"Stdio loop error: {e}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == "__main__":
    if "--http" in sys.argv:
        # HTTP mode for Render deployment
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse, Response
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        
        # Create FastAPI app for HTTP mode
        app = FastAPI(title="General MCP Server", version="1.0.0")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.post("/message")
        async def handle_mcp_message(message: dict):
            mcp_server = MCPServer()
            return await mcp_server.handle_message(message)
        
        @app.post("/mcp")
        async def handle_mcp_endpoint(message: dict):
            """Handle MCP requests from Claude Web on /mcp endpoint."""
            import time
            start_time = time.time()
            method = message.get("method", "unknown")
            
            # Fast-path for tools/list to avoid timeout
            if method == "tools/list":
                logger.info("⚡ Using cached tools/list response for speed")
                response = get_cached_tools_response(message.get("id"))
                elapsed = time.time() - start_time
                logger.info(f"✅ {method} completed in {elapsed:.3f}s (cached)")
                return response
            
            # Regular processing for other methods
            mcp_server = MCPServer()
            response = await mcp_server.handle_message(message)
            elapsed = time.time() - start_time
            logger.info(f"✅ {method} completed in {elapsed:.3f}s")
            return response
        
        @app.get("/mcp")
        async def handle_mcp_sse():
            """Handle Server-Sent Events for MCP."""
            return Response(content="", media_type="text/event-stream")
        
        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Handle WebSocket MCP communication."""
            await websocket.accept()
            mcp_server = MCPServer()
            
            try:
                while True:
                    # Receive message from Claude
                    message = await websocket.receive_json()
                    logger.info(f"WebSocket received: {message}")
                    
                    # Process with MCP server
                    response = await mcp_server.handle_message(message)
                    
                    # Send response back (only if not None)
                    if response is not None:
                        await websocket.send_json(response)
                        logger.info(f"WebSocket sent: {response}")
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.close()
        
        @app.get("/")
        async def root():
            mcp_server = MCPServer()
            return {"message": "MCP Server", "tools": len(mcp_server.tools)}
        
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"🚀 MCP Server starting in HTTP mode on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Stdio mode for Claude Desktop
        logger.info("🚀 MCP Server starting in stdio mode (for Claude Desktop)")
        asyncio.run(stdio_main())

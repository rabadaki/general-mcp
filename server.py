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
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
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
                "id": message.get("id"),
                "result": {"tools": TOOLS}
            }
        
        elif method == "tools/call":
            tool_name = message.get("params", {}).get("name")
            arguments = message.get("params", {}).get("arguments", {})
            
            # Call the appropriate tool function
            if tool_name == "search_reddit":
                result = await search_reddit(**arguments)
            elif tool_name == "search_web":
                result = await search_web(**arguments)
            elif tool_name == "get_api_usage_stats":
                result = await get_api_usage_stats(**arguments)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
            
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
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
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
            
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
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
    """Search Reddit for posts matching a query using Apify."""
    limit = validate_limit(limit, MAX_LIMIT, "Reddit")
    
    if not APIFY_TOKEN:
        return "❌ APIFY_TOKEN not configured. Please set the environment variable."
    
    # Use Reddit scraper
    payload = {
        "searches": [query] if not subreddit else [f"subreddit:{subreddit} {query}"],
        "sort": sort,
        "time": time,
        "maxItems": limit,
        "proxy": {"useApifyProxy": True}
    }
    
    data = await make_request(
        f"{APIFY_API_BASE}/trudax~reddit-scraper/run-sync-get-dataset-items",
        params={"token": APIFY_TOKEN},
        json_data=payload,
        method="POST"
    )
    
    log_api_usage("Reddit", "search", limit, len(data) if data else 0, 0.01 * limit)
    
    if not data:
        return f"❌ No results found for Reddit search: '{query}'"
    
    results = []
    for post in data[:limit]:
        title = post.get("title", "No title")
        author = post.get("author", "Unknown")
        score = post.get("score", 0)
        comments = post.get("numberOfComments", 0)
        url = post.get("url", "")
        subreddit_name = post.get("subreddit", "")
        
        result = f"""
📝 **{title}**
👤 u/{author} in r/{subreddit_name}
⬆️ {score} upvotes | 💬 {comments} comments
🔗 {url}
"""
        results.append(result.strip())
    
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

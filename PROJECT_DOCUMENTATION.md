# General MCP Server - Comprehensive Project Documentation

## Table of Contents
1. [Product Requirements Document (PRD)](#product-requirements-document-prd)
2. [Architecture Diagram](#architecture-diagram)
3. [Active Contexts & State](#active-contexts--state)
4. [API Documentation](#api-documentation)
5. [Development Guide](#development-guide)
6. [Troubleshooting](#troubleshooting)

---

## Product Requirements Document (PRD)

### Executive Summary
The General MCP Server is a comprehensive Model Context Protocol (MCP) server that provides unified access to multiple social media platforms and web search services. It serves as a central hub for retrieving real-time social media content, trends, and web information through a standardized API interface.

### Product Vision
**"A unified, cost-controlled, and rate-limited gateway to the world's social media and web information."**

### Key Objectives
1. **Unified Access**: Single API interface for multiple platforms (Reddit, YouTube, Twitter, TikTok, etc.)
2. **Cost Protection**: Comprehensive rate limiting and usage monitoring to prevent unexpected charges
3. **Real-time Data**: Access to current social media content and trending information
4. **Developer Experience**: Clean, well-documented API with consistent response formats
5. **Reliability**: Robust error handling and fallback mechanisms

### Target Users
- **AI Developers**: Building applications that need social media data
- **Research Teams**: Analyzing social media trends and sentiment
- **Content Creators**: Monitoring mentions and trending topics
- **Marketing Teams**: Brand monitoring and competitive intelligence
- **Data Scientists**: Social media research and analytics

### Core Features

#### 1. Social Media Integration
- **Reddit**: Posts, comments, subreddit data
- **YouTube**: Video search, trending content  
- **Twitter**: Tweet search, user timelines (cost-protected)
- **TikTok**: Video search, user content
- **Integration Status**: All platforms operational with rate limiting

#### 2. Web Search Capabilities
- **Perplexity AI**: Intelligent web search with citations
- **DuckDuckGo**: Free web search without API keys
- **Google Trends**: Trend analysis and comparison (via ScrapingBee)

#### 3. Cost Protection & Monitoring
- **Usage Tracking**: Comprehensive API call logging
- **Rate Limiting**: Service-specific limits to prevent overruns
- **Cost Estimation**: Track estimated costs per service
- **Alerts**: Warnings for high-cost operations

#### 4. Data Standardization
- **Consistent Formatting**: Unified response formats across platforms
- **Flexible Parsing**: Handle various API response structures
- **Error Handling**: Graceful degradation and informative error messages

### Technical Requirements

#### Performance Requirements
- **Response Time**: < 30 seconds for typical searches
- **Throughput**: Support for concurrent requests
- **Reliability**: 99% uptime for core functionality
- **Scalability**: Handle increasing request volumes

#### Security Requirements
- **API Key Management**: Secure storage and rotation of API credentials
- **Rate Limiting**: Prevent abuse and protect against cost overruns
- **Input Validation**: Sanitize all user inputs
- **Error Handling**: No sensitive data in error messages

#### Integration Requirements
- **MCP Protocol**: Full compliance with Model Context Protocol v1.0
- **Transport Support**: Both stdio and SSE (Server-Sent Events)
- **Client Compatibility**: Works with Claude Desktop, Cursor, and other MCP clients

### Success Metrics
1. **API Response Success Rate**: > 95%
2. **Cost Control**: Zero unexpected charges > $5
3. **Developer Adoption**: Active usage by AI development teams
4. **Data Quality**: Accurate, real-time social media data
5. **Error Rate**: < 5% failed requests

### Risk Assessment

#### High Risk
- **Twitter API Costs**: Historical issues with cost overruns
  - *Mitigation*: Rate-limited actor, backup limiting, usage monitoring
- **API Rate Limits**: External services may throttle requests
  - *Mitigation*: Exponential backoff, retry logic, fallback services

#### Medium Risk
- **API Key Exposure**: Security risk if credentials are compromised
  - *Mitigation*: Environment variable storage, regular rotation
- **Service Downtime**: External APIs may become unavailable
  - *Mitigation*: Graceful error handling, status monitoring

#### Low Risk
- **Data Format Changes**: External APIs may change response formats
  - *Mitigation*: Flexible parsing, comprehensive error handling

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    General MCP Server v2.0                     │
│                        (FastMCP Core)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Transport    │ │ Monitoring   │ │ Validation   │
│ Layer        │ │ & Analytics  │ │ & Safety     │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ • stdio      │ │ • Usage Log  │ │ • Param Val  │
│ • SSE/HTTP   │ │ • Cost Track │ │ • Rate Limit │
│ • WebSocket  │ │ • Analytics  │ │ • Error Hand │
└──────────────┘ └──────────────┘ └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ HTTP Client  │ │ Data Format  │ │ Service      │
│ Layer        │ │ Layer        │ │ Router       │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ • httpx      │ │ • Reddit     │ │ • Tool       │
│ • Retry      │ │ • YouTube    │ │   Registry   │
│ • Timeout    │ │ • Twitter    │ │ • Endpoint   │
│ • Backoff    │ │ • TikTok     │ │   Mapping    │
└──────────────┘ └──────────────┘ └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
┌─────────────────────────┼─────────────────────────┐
│                         │                         │
▼                         ▼                         ▼
┌──────────────────────────────────────────────────────┐
│                External APIs                         │
├─────────────┬─────────────┬─────────────┬──────────┤
│   Social    │  Search     │   Trends    │   Free   │
│   Media     │  Services   │   Analysis  │  Services│
├─────────────┼─────────────┼─────────────┼──────────┤
│ • Twitter   │ • Perplexity│ • Google    │ • Reddit │
│   (Apify)   │   AI        │   Trends    │   JSON   │
│ • TikTok    │ • ScrapingBee│   (Scraping)│ • DuckGo │
│   (Apify)   │             │             │   API    │
│ • YouTube   │             │             │          │
│   (Google)  │             │             │          │
└─────────────┴─────────────┴─────────────┴──────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Data Flow Pattern                           │
├─────────────────────────────────────────────────────────────────┤
│ 1. Client Request ─► MCP Protocol ─► Tool Router               │
│ 2. Parameter Validation ─► Rate Limit Check ─► Usage Log       │
│ 3. HTTP Request ─► External API ─► Response Parse              │
│ 4. Data Format ─► Safety Limit ─► Result Assembly              │
│ 5. Usage Update ─► Response Format ─► Client Response          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   Cost Protection System                        │
├─────────────────────────────────────────────────────────────────┤
│                         Request                                 │
│                           │                                     │
│   ┌───────────────────────▼───────────────────────┐             │
│   │           Pre-Request Validation               │             │
│   │  • Limit ≤ Service Max • Days ≤ Service Max   │             │
│   └───────────────────────┬───────────────────────┘             │
│                           │                                     │
│   ┌───────────────────────▼───────────────────────┐             │
│   │              API Request                      │             │
│   │  • Rate-Limited Actor • Timeout • Retries    │             │
│   └───────────────────────┬───────────────────────┘             │
│                           │                                     │
│   ┌───────────────────────▼───────────────────────┐             │
│   │           Post-Response Safety                │             │
│   │  • Backup Limiting • Cost Monitoring         │             │
│   └───────────────────────┬───────────────────────┘             │
│                           │                                     │
│                        Response                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Active Contexts & State

### Current System State
```yaml
Version: "2.0.0"
Status: "Production Ready"
Last Updated: "2025-01-06"
Environment: "Development"

API Status:
  Twitter:
    Actor: "61RPP7dywgiy0JPD0" # Rate-limited Tweet Scraper V2
    Status: "Active"
    Cost Protection: "Enabled"
    Max Limit: 50
    Max Days: 7
    
  YouTube:
    API: "Data API v3"
    Status: "Active"
    Daily Quota: 100
    Max Results: 50
    
  TikTok:
    Actor: "clockworks~tiktok-scraper"
    Status: "Active"
    Max Limit: 50
    Max Days: 30
    
  Reddit:
    API: "Public JSON"
    Status: "Active"
    Rate Limit: "None"
    Cost: "Free"
    
  Perplexity:
    Model: "llama-3.1-sonar-small-128k-online"
    Status: "Active"
    Rate Limit: "5/minute (free)"
    
  Web Search:
    Provider: "DuckDuckGo"
    Status: "Active"
    Cost: "Free"
    
  Google Trends:
    Provider: "ScrapingBee Proxy"
    Status: "Limited (Anti-bot protection)"
    Manual Access: "Required for detailed data"

Configuration:
  Transport: ["stdio", "sse"]
  Default Port: 8080
  Timeout: 30s
  Max Retries: 3
  Log Rotation: 200 entries
```

### Resource Monitoring
```yaml
API Keys:
  YouTube: "AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ"
  Apify: "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"  
  Perplexity: "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"
  ScrapingBee: "68AEL9OT9277RWTL7HA6H6OFTCR20HELBSCYXQAPW2SDFEFB3BJ8I1TOJS9WJVCFE4OHWULFRO0AILZU"

Cost Tracking:
  High Risk Services: ["Twitter", "TikTok", "Perplexity"]
  Free Services: ["Reddit", "Web Search", "YouTube (quota)"]
  Alert Threshold: "$0.10 per call"
  Daily Budget: "Monitor usage"

Security:
  API Key Storage: "Source code (TODO: Environment variables)"
  Access Control: "None (TODO: Authentication)"
  Rate Limiting: "Per-service basis"
  Input Validation: "Enabled"
```

### Tool Registry
```yaml
Available Tools: 13

Reddit Tools (3):
  - search_reddit: "Search posts across Reddit"
  - get_subreddit_posts: "Get posts from specific subreddit"
  - get_reddit_comments: "Get comments from post"

YouTube Tools (2):
  - search_youtube: "Search videos"
  - get_youtube_trending: "Get trending videos"

Twitter Tools (2):
  - search_twitter: "Search tweets (cost-protected)"
  - get_user_tweets: "Get user timeline (cost-protected)"

TikTok Tools (2):
  - search_tiktok: "Search videos"
  - get_tiktok_user_videos: "Get user videos"

Search Tools (3):
  - search_perplexity: "AI-powered web search"
  - search_web: "DuckDuckGo web search"
  - get_api_usage_stats: "Usage analytics"

Trends Tools (2):
  - search_google_trends: "Google Trends analysis"
  - compare_google_trends: "Compare multiple terms"
```

---

## API Documentation

### Tool Categories

#### Reddit Tools
```python
# Search across all of Reddit
search_reddit(
    query: str,              # Search terms
    subreddit: str = "",     # Specific subreddit (optional)
    sort: str = "relevance", # Sort order
    time: str = "all",       # Time period
    limit: int = 10          # Results count (max 50)
) -> str

# Get posts from specific subreddit
get_subreddit_posts(
    subreddit: str,          # Subreddit name
    sort: str = "hot",       # Sort order
    time: str = "day",       # Time period
    limit: int = 10          # Results count (max 50)
) -> str

# Get comments from a post
get_reddit_comments(
    post_url: str,           # Reddit post URL
    limit: int = 10          # Comments count (max 50)
) -> str
```

#### YouTube Tools
```python
# Search YouTube videos
search_youtube(
    query: str,              # Search terms
    published_after: str = "",   # ISO date (optional)
    published_before: str = "",  # ISO date (optional)
    order: str = "viewCount",    # Sort order
    limit: int = 10          # Results count (max 50)
) -> str

# Get trending videos
get_youtube_trending(
    category: str = "0",     # Category ID
    region: str = "US",      # Country code
    limit: int = 10          # Results count (max 50)
) -> str
```

#### Twitter Tools (Cost Protected)
```python
# Search tweets with comprehensive cost protection
search_twitter(
    query: str,              # Search query (Twitter syntax supported)
    limit: int = 15,         # Results count (max 50)
    sort: str = "Latest",    # Sort order
    days_back: int = 7       # Days to search back (max 7)
) -> str

# Get user timeline with cost protection
get_user_tweets(
    username: str,           # Twitter username (without @)
    limit: int = 15,         # Results count (max 50)
    days_back: int = 7       # Days to search back (max 7)
) -> str
```

#### Web Search Tools
```python
# AI-powered search with Perplexity
search_perplexity(
    query: str,              # Search query
    max_results: int = 10    # Source count (max 10)
) -> str

# Free web search with DuckDuckGo
search_web(
    query: str,              # Search query
    max_results: int = 10,   # Results count (max 50)
    limit: int = None        # Alias for max_results
) -> str
```

#### Analytics Tools
```python
# Get comprehensive usage statistics
get_api_usage_stats() -> str
```

### Response Formats

#### Standard Response Structure
```
🔍 [Service Icon] Found X results for 'query'

[Service Icon] **Title/Author**
📝 Content/Description (truncated to ~200 chars)
📊 Metrics (likes, views, comments, etc.)
📅 Date
🔗 URL

---

[Next Result...]
```

#### Error Response Format
```
❌ [Service] error description
💡 Suggested action or alternative
🔗 Manual access URL (if applicable)
```

---

## Development Guide

### Setup Instructions

#### Prerequisites
```bash
# Python 3.8+
python --version

# Required packages
pip install fastmcp httpx uvicorn starlette beautifulsoup4 requests
```

#### Environment Setup
```bash
# Clone repository
git clone [repository-url]
cd general-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set API keys (recommended: environment variables)
export YOUTUBE_API_KEY="your-key"
export APIFY_TOKEN="your-token"
export PERPLEXITY_API_KEY="your-key"
export SCRAPINGBEE_API_KEY="your-key"
```

#### Running the Server
```bash
# stdio mode (for MCP clients)
python server.py --stdio

# HTTP/SSE mode (for web access)
python server.py --host localhost --port 8080

# Health check
curl http://localhost:8080/health
```

### Code Organization

```
general-mcp/
├── server.py              # Main server implementation
├── PROJECT_DOCUMENTATION.md # This file
├── twitter_demo.py        # Testing demonstration
├── test_new_actor.py      # Comprehensive test suite
├── requirements.txt       # Python dependencies
└── README.md             # Basic setup instructions
```

### Adding New Services

#### Template for New Service
```python
@mcp.tool()
async def search_newservice(
    query: str,
    limit: int = 10,
    **kwargs
) -> str:
    """
    Search [Service Name] for content.
    
    Args:
        query: Search terms
        limit: Number of results (max X)
        **kwargs: Service-specific parameters
    
    Returns:
        Formatted string with results
    """
    # 1. Validate parameters
    limit = validate_limit(limit, SERVICE_MAX_LIMIT, "ServiceName")
    
    # 2. Log API usage
    log_api_usage("ServiceName", "search", limit)
    
    # 3. Make API request
    data = await make_request(url, params, headers, method, json_data)
    
    # 4. Handle errors
    if not data:
        log_api_usage("ServiceName", "search", limit, 0)
        return "❌ Service unavailable"
    
    # 5. Process results
    results = []
    for item in data[:limit]:
        formatted = format_service_item(item)
        results.append(format_result(formatted))
    
    # 6. Update usage log
    log_api_usage("ServiceName", "search", limit, len(results))
    
    # 7. Return formatted response
    header = f"🔍 Found {len(results)} results for '{query}'"
    return header + "\n\n" + "\n---\n".join(results)
```

### Testing

#### Running Tests
```bash
# Run comprehensive test suite
python test_new_actor.py

# Run specific Twitter demonstration
python twitter_demo.py

# Test individual functions
python -c "import asyncio; from server import search_reddit; print(asyncio.run(search_reddit('python')))"
```

#### Test Coverage
- All 13 tools tested automatically
- Cost protection verification
- Error handling validation
- Response format consistency
- Rate limiting behavior

---

## Troubleshooting

### Common Issues

#### 1. Twitter Cost Overruns
**Symptoms**: Unexpected high costs from Twitter searches
**Root Cause**: API Dojo actors may ignore limit parameters
**Solution**: 
- Current actor (61RPP7dywgiy0JPD0) has built-in rate limiting
- Backup safety limiting in code
- Monitor `get_api_usage_stats()` regularly

#### 2. API Key Issues
**Symptoms**: 401/403 errors from services
**Solutions**:
- Verify API keys are current and valid
- Check service-specific quotas and limits
- Rotate keys if compromised

#### 3. Rate Limiting
**Symptoms**: 429 errors, slow responses
**Solutions**:
- Reduce request frequency
- Use exponential backoff (built-in)
- Switch to free alternatives when possible

#### 4. Google Trends Anti-Bot Protection
**Symptoms**: Limited or no Google Trends data
**Solutions**:
- Use manual access URLs provided
- Try different time periods
- Use web search for trend-related news

### Monitoring Commands
```bash
# Check API usage
python -c "import asyncio; from server import get_api_usage_stats; print(asyncio.run(get_api_usage_stats()))"

# Test specific service
python -c "import asyncio; from server import search_web; print(asyncio.run(search_web('test')))"

# Verify server health
curl http://localhost:8080/health
```

### Performance Optimization
1. **Reduce Limits**: Use smaller result counts for exploratory searches
2. **Cache Results**: Implement caching for repeated queries
3. **Batch Requests**: Combine multiple searches when possible
4. **Use Free Services**: Prefer Reddit/Web Search for general queries

### Security Best Practices
1. **Environment Variables**: Move API keys to environment variables
2. **Access Control**: Implement authentication for production use
3. **Input Validation**: All user inputs are validated
4. **Error Sanitization**: No sensitive data in error responses
5. **Regular Key Rotation**: Rotate API keys periodically

---

## Changelog

### v2.0.0 (2025-01-06)
- ✅ Comprehensive code cleanup and documentation
- ✅ Standardized parameter validation across all tools
- ✅ Enhanced cost protection for Twitter searches
- ✅ Fixed TikTok emoji encoding issues
- ✅ Improved error handling and retry logic
- ✅ Added comprehensive usage analytics
- ✅ Created detailed project documentation

### v1.0.0 (Previous)
- ✅ Initial implementation of 13 tools
- ✅ Basic Twitter cost protection
- ✅ Multi-transport support (stdio/SSE)
- ✅ Integration with all major social platforms

---

## Future Roadmap

### Planned Features
1. **Enhanced Security**: Environment variable configuration
2. **Advanced Analytics**: Trend analysis and reporting
3. **Caching Layer**: Redis integration for performance
4. **Authentication**: API key-based access control
5. **Webhooks**: Real-time notifications for monitoring
6. **Batch Operations**: Multi-query optimization
7. **Custom Parsers**: User-defined data extraction rules

### Service Expansions
1. **Instagram**: Posts and stories (via scraping)
2. **LinkedIn**: Professional content and trends
3. **Discord**: Server and channel monitoring
4. **Telegram**: Channel and group content
5. **News APIs**: Real-time news aggregation
6. **Academic Sources**: Research paper search

---

*This documentation is maintained alongside the codebase and reflects the current state of the General MCP Server v2.0.0.* 

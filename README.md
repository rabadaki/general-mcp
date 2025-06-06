# General MCP Server 🚀

A comprehensive Model Context Protocol (MCP) server that provides Reddit, YouTube, and Twitter search capabilities for AI assistants.

## Features

- **🔴 Reddit**: Search across all of Reddit or specific subreddits, browse posts
- **🎥 YouTube**: Search videos, get trending content with view counts and statistics
- **🐦 Twitter**: Search tweets, get user timelines (via Apify integration)
- **Multiple Transport Options**: Supports both stdio and SSE transports

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

**Option A: Stdio transport (for Claude Desktop/local clients)**
```bash
python server.py --stdio
```

**Option B: SSE transport (for web access)**
```bash
python server.py --host localhost --port 8080
```

## Available Tools

### Reddit Tools

#### 1. `search_reddit`
Search Reddit for posts matching a query.

**Parameters:**
- `query` (str): Search terms
- `subreddit` (str, optional): Specific subreddit to search
- `sort` (str): Sort order (relevance, hot, top, new, comments)
- `time` (str): Time period (all, year, month, week, day, hour)
- `limit` (int): Number of results (max 25)

#### 2. `get_subreddit_posts`
Get posts from a specific subreddit.

**Parameters:**
- `subreddit` (str): Name of the subreddit (without r/)
- `sort` (str): Sort order (hot, new, top, rising)
- `time` (str): Time period for top posts
- `limit` (int): Number of posts (max 25)

### YouTube Tools

#### 3. `search_youtube`
Search YouTube for videos matching a query.

**Parameters:**
- `query` (str): Search terms
- `published_after` (str, optional): ISO date string (e.g., "2024-01-01T00:00:00Z")
- `published_before` (str, optional): ISO date string (e.g., "2024-12-31T23:59:59Z")
- `order` (str): Sort order (relevance, date, rating, viewCount, title)
- `limit` (int): Number of results (max 25)

#### 4. `get_youtube_trending`
Get trending YouTube videos.

**Parameters:**
- `category` (str): Category ID (0=All, 10=Music, 15=Pets, 17=Sports, etc.)
- `region` (str): Country code (US, GB, CA, etc.)
- `limit` (int): Number of results (max 25)

### Twitter Tools

#### 5. `search_twitter`
Search Twitter for posts matching a query.

**Parameters:**
- `query` (str): Search terms
- `limit` (int): Number of results (max 25)
- `search_mode` (str): Search mode (live, user, image, video)
- `days_back` (int): How many days back to search (1-30, default 7)

#### 6. `get_twitter_user_tweets`
Get recent tweets from a specific user.

**Parameters:**
- `username` (str): Twitter username (without @)
- `limit` (int): Number of tweets (max 25)
- `days_back` (int): How many days back to search (1-90, default 30)

## Examples

### Search across platforms
```python
# Search Reddit for AI discussions
search_reddit("artificial intelligence", subreddit="MachineLearning", limit=5)

# Find YouTube videos about Python
search_youtube("python tutorial", order="viewCount", limit=10)

# Search Twitter for tech news
search_twitter("OpenAI GPT", limit=5)
```

### Get trending content
```python
# Get hot posts from r/programming
get_subreddit_posts("programming", sort="hot", limit=10)

# Get trending YouTube videos
get_youtube_trending("0", "US", 10)

# Get tweets from a specific user
get_twitter_user_tweets("elonmusk", 5)
```

## Configuration

The server accepts the following command-line arguments:

- `--host`: Host to bind to (default: localhost)
- `--port`: Port to listen on (default: 8080)
- `--stdio`: Use stdio transport instead of SSE

## API Keys

This server uses the following APIs:

- **YouTube**: Requires YouTube Data API v3 key (set `YOUTUBE_API_KEY`)
- **Twitter**: Uses Apify Twitter scraper (set `APIFY_TOKEN`)
- **Reddit**: Uses public JSON API (no key required)

## Installation in Claude Desktop

To use with Claude Desktop, add this to your configuration:

```json
{
  "mcpServers": {
    "general": {
      "command": "/bin/bash",
      "args": ["/Users/Amos/general-mcp/start_server.sh"],
      "cwd": "/Users/Amos/general-mcp"
    }
  }
}
```

## Dependencies

- `fastmcp`: Fast MCP server framework
- `httpx`: HTTP client for API requests
- `uvicorn`: ASGI server for SSE transport
- `starlette`: Web framework for routing

## License

MIT License - feel free to use and modify as needed! # Force redeploy

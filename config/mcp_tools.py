#!/usr/bin/env python3

# Tool definitions in MCP format
TOOLS = [
    {
        "name": "search_perplexity",
        "description": "Search using Perplexity AI for real-time information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_reddit",
        "description": "Search Reddit for posts matching a query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms to look for"
                },
                "subreddit": {
                    "type": "string",
                    "description": "Specific subreddit to search (optional)"
                },
                "sort": {
                    "type": "string",
                    "description": "Sort order (relevance, hot, top, new, comments)"
                },
                "time": {
                    "type": "string",
                    "description": "Time period (all, year, month, week, day, hour)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
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
                "subreddit": {
                    "type": "string",
                    "description": "Subreddit name"
                },
                "sort": {
                    "type": "string",
                    "description": "Sort order (hot, new, rising, top)"
                },
                "time": {
                    "type": "string",
                    "description": "Time period (all, year, month, week, day, hour)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
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
                "post_url": {
                    "type": "string",
                    "description": "Reddit post URL"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of comments to return (max 50)"
                }
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
                "query": {
                    "type": "string",
                    "description": "Search terms"
                },
                "published_after": {
                    "type": "string",
                    "description": "ISO date (optional)"
                },
                "published_before": {
                    "type": "string",
                    "description": "ISO date (optional)"
                },
                "order": {
                    "type": "string",
                    "description": "Sort order (relevance, date, rating, viewCount, title)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
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
                "category": {
                    "type": "string",
                    "description": "Category ID (0=all, 10=music, 15=pets, etc.)"
                },
                "region": {
                    "type": "string",
                    "description": "Country code (US, CA, GB, etc.)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
            }
        }
    },
    {
        "name": "search_twitter",
        "description": "Search tweets (cost-protected)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (Twitter syntax supported)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                },
                "sort": {
                    "type": "string",
                    "description": "Sort order (Latest, Popular, Photos, Videos)"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Days to search back (max 7)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_twitter_profile",
        "description": "Get Twitter profile information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Twitter username (without @)"
                },
                "get_followers": {
                    "type": "boolean",
                    "description": "Whether to fetch followers list"
                },
                "get_following": {
                    "type": "boolean",
                    "description": "Whether to fetch following list"
                }
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
                "query": {
                    "type": "string",
                    "description": "Search terms"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
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
                "username": {
                    "type": "string",
                    "description": "TikTok username (without @)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                }
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
                "query": {
                    "type": "string",
                    "description": "Search term (hashtag without #)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (max 50)"
                },
                "search_type": {
                    "type": "string",
                    "description": "Search type: 'hashtag' or 'keyword' (default: hashtag)"
                }
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
                "username": {
                    "type": "string",
                    "description": "Instagram username (without @)"
                },
                "include_posts": {
                    "type": "boolean",
                    "description": "Include recent posts (default: false)"
                }
            },
            "required": ["username"]
        }
    },
    {
        "name": "search_google_trends",
        "description": "Search Google Trends for a keyword",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Time period (default: 'today 12-m')"
                },
                "geo": {
                    "type": "string",
                    "description": "Country code (default: 'US')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "compare_google_trends",
        "description": "Compare multiple keywords on Google Trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "terms": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of terms to compare"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Time period (default: 'today 12-m')"
                },
                "geo": {
                    "type": "string",
                    "description": "Country code (default: 'US')"
                }
            },
            "required": ["terms"]
        }
    },
    {
        "name": "get_api_usage_stats",
        "description": "Get API usage statistics",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
] 
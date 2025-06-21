# General MCP Server

A comprehensive Model Context Protocol (MCP) server that provides AI assistants with access to social media platforms, web services, and SEO tools.

## 🚀 Features

### Social Media & Web Tools
- **Reddit**: Search posts, get subreddit content, comments
- **Twitter**: Search tweets, get user timelines  
- **Instagram**: Search posts, get user profiles
- **TikTok**: Search videos, get user content
- **YouTube**: Search videos, get trending content
- **Perplexity**: AI-powered web search
- **Google Trends**: Search trend analysis and comparisons

### SEO & Analytics Tools (DataForSEO)
- **SERP Analysis**: Get Google search results data
- **Keyword Research**: Search volume, CPC, competition analysis
- **Competitor Analysis**: Domain traffic, backlinks, competitive keywords
- **Website Performance**: Lighthouse audits, performance scores

## 📁 Project Structure

```
general-mcp/
├── src/                    # Main source code
│   └── mcp_stdio_server.py # Primary MCP server
├── config/                 # Configuration files
│   ├── requirements.txt    # Python dependencies
│   ├── mcp_requirements.txt # MCP-specific dependencies
│   ├── *.json             # Configuration files
│   └── *.js               # Bridge files
├── scripts/                # Utility scripts
│   ├── restart_claude.sh   # Restart Claude Desktop
│   ├── cleanup_project.py  # Project organization script
│   └── *.py               # Various utility scripts
├── tests/                  # All test files
├── docs/                   # Documentation
├── logs/                   # Log files
├── backup/                 # Backup files
├── venv/                   # Virtual environment
└── README.md              # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Claude Desktop (for MCP integration)

### Quick Setup

1. **Clone and setup environment:**
```bash
git clone <repository-url>
cd general-mcp
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r config/requirements.txt
```

2. **Configure API keys:**
Set environment variables or edit the server file:
```bash
export YOUTUBE_API_KEY="your_key_here"
export PERPLEXITY_API_KEY="your_key_here"
export APIFY_TOKEN="your_token_here"
export DATAFORSEO_LOGIN="your_login_here"
export DATAFORSEO_PASSWORD="your_password_here"
```

3. **Configure Claude Desktop:**
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "general-mcp": {
      "command": "python",
      "args": ["/path/to/general-mcp/mcp_stdio_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/general-mcp"
      }
    }
  }
}
```

4. **Start the server:**
```bash
# MCP mode (for Claude Desktop)
python mcp_stdio_server.py

# HTTP mode (for web interface)
python mcp_stdio_server.py --http
```

5. **Restart Claude Desktop:**
```bash
./scripts/restart_claude.sh
```

## 🔧 Usage

### In Claude Desktop
Once configured, you can use natural language to interact with the tools:

```
"Search Reddit for Python tutorials"
"Get trending YouTube videos about AI"
"Analyze the SEO for example.com"
"Research keywords for 'machine learning'"
```

### HTTP Mode
Access the web interface at `http://localhost:8000`:
- Automatic API documentation
- Real-time API usage monitoring
- Server-sent events for live updates

## 📊 API Usage & Cost Tracking

The server includes comprehensive usage tracking:
- Request counts by service and endpoint
- Cost estimates for paid APIs
- Rate limiting protection
- Detailed logging

View usage stats:
```bash
python scripts/count_tools.py
```

## 🔍 Available Tools

### Social Media Tools
- `get_subreddit_posts` - Get posts from a specific subreddit
- `get_reddit_comments` - Get comments from a Reddit post
- `search_reddit` - Search across Reddit
- `search_twitter` - Search Twitter posts
- `get_user_tweets` - Get tweets from a specific user
- `search_instagram` - Search Instagram posts
- `get_instagram_profile` - Get Instagram user profile
- `search_tiktok` - Search TikTok videos
- `get_tiktok_user_videos` - Get videos from TikTok user
- `search_youtube` - Search YouTube videos
- `get_youtube_trending` - Get trending YouTube videos

### Web & Analysis Tools
- `search_perplexity` - AI-powered web search
- `search_google_trends` - Search Google Trends data
- `compare_google_trends` - Compare multiple terms on Google Trends
- `search_serp` - Get Google search results (DataForSEO)
- `keyword_research` - Keyword analysis and search volume
- `competitor_analysis` - Domain and competitor analysis
- `lighthouse_audit` - Website performance audit
- `lighthouse_performance_score` - Quick performance score
- `lighthouse_bulk_audit` - Audit multiple URLs

## 🚨 Troubleshooting

### Common Issues

1. **"Tool not found" errors:**
   - Restart Claude Desktop: `./scripts/restart_claude.sh`
   - Check configuration path in claude_desktop_config.json

2. **API timeout errors:**
   - Some tools (especially social media) take 60-90 seconds
   - This is normal for comprehensive data gathering

3. **Permission errors:**
   - Ensure Python path is correct in configuration
   - Check file permissions: `chmod +x scripts/*.sh`

4. **DataForSEO errors:**
   - Verify API credentials
   - Check account plan limits
   - Some tools require premium subscription

### Debug Mode
Enable detailed logging:
```bash
tail -f logs/mcp_debug.log
```

## 📝 Development

### Adding New Tools
1. Add function to `mcp_stdio_server.py`
2. Add tool definition to `MCPServer.tools`
3. Add handler in `handle_message` method
4. Test with provided test scripts

### Running Tests
```bash
cd tests/
python test_*.py
```

### Code Organization
- Keep all tests in `/tests`
- Put utilities in `/scripts`
- Configuration in `/config`
- Documentation in `/docs`

## 📄 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- Check `/docs` for detailed documentation
- Review `/logs` for debugging information
- Use `/scripts/verify_live_apis.py` to test API connectivity

---

**Version**: 1.0.0  
**Last Updated**: December 2024  
**Author**: General MCP Team

# Vercel Deployment Guide for MCP Server

This guide will help you deploy your MCP (Model Context Protocol) server to Vercel.

## 🚀 Quick Start

### 1. Prerequisites
- [Vercel account](https://vercel.com/) (free tier available)
- [Vercel CLI](https://vercel.com/docs/cli) installed: `npm i -g vercel`
- API keys for the services you want to use

### 2. Deploy to Vercel

#### Option A: Deploy via CLI
```bash
# Install Vercel CLI if not already installed
npm i -g vercel

# Login to Vercel
vercel login

# Deploy from this directory
vercel

# Follow the prompts:
# - Set up and deploy? Y
# - Which scope? (your username/team)
# - Link to existing project? N
# - Project name? (or press enter for auto-generated)
# - Directory? ./
# - Settings correct? Y
```

#### Option B: Deploy via Git Integration
1. Push this repository to GitHub/GitLab/Bitbucket
2. Go to [Vercel Dashboard](https://vercel.com/dashboard)
3. Click "New Project"
4. Import your repository
5. Vercel will auto-detect and deploy

### 3. Configure Environment Variables

In your Vercel dashboard, go to your project → Settings → Environment Variables and add:

```
YOUTUBE_API_KEY=AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ
APIFY_TOKEN=apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM
PERPLEXITY_API_KEY=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
SCRAPINGBEE_API_KEY=68AEL9OT9277RWTL7HA6H6OFTCR20HELBSCYXQAPW2SDFEFB3BJ8I1TOJS9WJVCFE4OHWULFRO0AILZU
```

### 4. Test Your Deployment

Once deployed, your MCP server will be available at:
- `https://your-project-name.vercel.app/`
- Health check: `https://your-project-name.vercel.app/health`
- MCP endpoint: `https://your-project-name.vercel.app/message`

## 📋 Available Endpoints

### Core MCP Endpoints
- `POST /message` - Main MCP protocol endpoint
- `GET /sse` - Server-Sent Events for real-time updates
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with server info

### Tools Available (11/14 working)
✅ **Working Tools:**
- `get_api_usage_stats` - API usage statistics
- `search_web` - DuckDuckGo web search
- `search_youtube` - YouTube video search
- `get_youtube_trending` - Trending YouTube videos
- `search_twitter` - Twitter search
- `get_user_tweets` - User tweet timelines
- `search_tiktok` - TikTok video search
- `get_tiktok_user_videos` - User TikTok videos
- `search_perplexity` - AI-powered web search
- `search_google_trends` - Google Trends analysis
- `compare_google_trends` - Compare multiple trends

❌ **Known Issues:**
- Reddit tools (403 errors due to Reddit's anti-bot measures)

## 🔧 Configuration Files

### `vercel.json`
Configures Vercel deployment settings, routing, and environment variables.

### `api/index.py`
Vercel serverless function entry point that imports and serves the FastAPI app.

### `requirements.txt`
Python dependencies that Vercel will install automatically.

## 🚨 Important Notes

### Serverless Limitations
- **Cold starts**: First request may be slower
- **Timeout**: 60-second maximum execution time
- **Memory**: Limited memory compared to dedicated servers
- **State**: Stateless - no persistent storage between requests

### API Rate Limits
- YouTube API: 10,000 requests/day (free tier)
- Perplexity: Based on your plan
- Apify: Based on your plan
- Google Trends: Rate limited by Google

## 🛠️ Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are in `requirements.txt`
   - Check that `api/index.py` can import from `server.py`

2. **Environment Variables Not Found**
   - Verify environment variables are set in Vercel dashboard
   - Check variable names match exactly

3. **API Timeouts**
   - Some tools may timeout on cold starts
   - Consider implementing retry logic for production use

4. **CORS Issues**
   - The server includes CORS middleware for all origins
   - Adjust in `server.py` if needed for production

### Debugging

1. **Check Function Logs**
   ```bash
   vercel logs your-project-name
   ```

2. **Local Testing**
   ```bash
   # Test locally with Vercel CLI
   vercel dev
   ```

3. **Manual Testing**
   ```bash
   # Test endpoints directly
   curl https://your-project-name.vercel.app/health
   ```

## 📈 Performance Tips

1. **Optimize Cold Starts**
   - Keep imports minimal in `api/index.py`
   - Consider implementing caching for frequently used data

2. **Monitor Usage**
   - Use the `get_api_usage_stats` tool to monitor API consumption
   - Set up alerts for API rate limits

3. **Error Handling**
   - All tools include comprehensive error handling
   - Monitor Vercel function logs for issues

## 🔒 Security Considerations

1. **API Keys**
   - Never commit API keys to version control
   - Use Vercel environment variables
   - Rotate keys regularly

2. **Access Control**
   - Consider implementing authentication for production use
   - Monitor API usage for abuse

3. **Rate Limiting**
   - Built-in rate limiting for expensive API calls
   - Consider implementing additional rate limiting for production

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Vercel function logs
3. Test tools individually using the test script: `python3 test_mcp_tools.py`
4. Check API service status pages for outages

## 🔄 Updates

To update your deployment:
1. Make changes to your code
2. Push to git (if using git integration) or run `vercel` command
3. Vercel will automatically redeploy

---

**Happy deploying!** 🚀
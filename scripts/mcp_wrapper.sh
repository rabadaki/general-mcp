#!/bin/bash

# Set environment variables
export APIFY_TOKEN="apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"
export PERPLEXITY_API_KEY="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"
export YOUTUBE_API_KEY="AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ"
export APIFY_API_TOKEN="apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"

# Change to the script directory
cd "$(dirname "$0")"

# Run the MCP server with unbuffered output
exec /Users/Amos/general-mcp/venv/bin/python -u mcp_stdio_server.py 
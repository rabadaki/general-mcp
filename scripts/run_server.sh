#!/bin/bash

# Change to the script directory
cd "$(dirname "$0")"

# Set environment variables
export APIFY_TOKEN=apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM
export PERPLEXITY_API_KEY=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
export YOUTUBE_API_KEY=AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ

# Run the server using the venv Python
/Users/Amos/general-mcp/venv/bin/python /Users/Amos/general-mcp/mcp_server.py 
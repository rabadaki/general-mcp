#!/usr/bin/env python3
import sys
import os
import subprocess

# Set environment variables
os.environ["APIFY_TOKEN"] = "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"
os.environ["PERPLEXITY_API_KEY"] = "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"
os.environ["YOUTUBE_API_KEY"] = "AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ"
os.environ["APIFY_API_TOKEN"] = "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM"

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run the actual MCP server
subprocess.run([
    sys.executable, 
    "-u",  # Unbuffered output
    "mcp_stdio_server.py"
]) 
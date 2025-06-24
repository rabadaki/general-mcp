#!/usr/bin/env python3
"""
Vercel serverless function entry point for the MCP server.
This file is required for Vercel to properly deploy the FastAPI application.
"""

import sys
import os

# Add the parent directory to the Python path so we can import server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the FastAPI app from server.py
from server import app

# Export the app for Vercel
handler = app
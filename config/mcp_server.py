#!/usr/bin/env python3

import asyncio
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx

# Import all the tool implementations from the main server
from server import (
    search_reddit, get_subreddit_posts, get_reddit_comments,
    search_youtube, get_youtube_trending,
    search_twitter, get_twitter_profile,
    search_tiktok, get_tiktok_user_videos,
    search_instagram, get_instagram_profile,
    search_perplexity, search_google_trends, compare_google_trends,
    get_api_usage_stats
)

# Import MCP tool definitions
from mcp_tools import TOOLS

# MCP protocol implementation for stdio
class MCPServer:
    def __init__(self):
        self.tools = TOOLS
        
    async def handle_message(self, message: dict) -> dict:
        """Handle MCP protocol messages."""
        method = message.get("method")
        message_id = message.get("id")
        
        # If this is a notification (no ID), don't send a response
        if message_id is None:
            return None
            
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "General Search MCP",
                        "version": "1.0.0"
                    }
                }
            }
            
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"tools": self.tools}
            }
            
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"resources": []}
            }
            
        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"prompts": []}
            }
            
        elif method == "tools/call":
            tool_name = message.get("params", {}).get("name")
            arguments = message.get("params", {}).get("arguments", {})
            
            try:
                # Call the appropriate tool function
                if tool_name == "search_reddit":
                    result = await search_reddit(**arguments)
                elif tool_name == "get_subreddit_posts":
                    result = await get_subreddit_posts(**arguments)
                elif tool_name == "get_reddit_comments":
                    result = await get_reddit_comments(**arguments)
                elif tool_name == "search_youtube":
                    result = await search_youtube(**arguments)
                elif tool_name == "get_youtube_trending":
                    result = await get_youtube_trending(**arguments)
                elif tool_name == "search_twitter":
                    result = await search_twitter(**arguments)
                elif tool_name == "get_twitter_profile":
                    result = await get_twitter_profile(**arguments)
                elif tool_name == "search_tiktok":
                    result = await search_tiktok(**arguments)
                elif tool_name == "get_tiktok_user_videos":
                    result = await get_tiktok_user_videos(**arguments)
                elif tool_name == "search_instagram":
                    result = await search_instagram(**arguments)
                elif tool_name == "get_instagram_profile":
                    result = await get_instagram_profile(**arguments)

                elif tool_name == "search_perplexity":
                    result = await search_perplexity(**arguments)
                elif tool_name == "search_google_trends":
                    result = await search_google_trends(**arguments)
                elif tool_name == "compare_google_trends":
                    result = await compare_google_trends(**arguments)
                elif tool_name == "get_api_usage_stats":
                    result = await get_api_usage_stats(**arguments)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                    
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
                
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {
                        "code": -32603,
                        "message": f"Tool execution error: {str(e)}"
                    }
                }
                
        else:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                }
            }
            
    async def run(self):
        """Run the MCP server on stdio."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        
        while True:
            try:
                # Read a line from stdin
                line = await reader.readline()
                if not line:
                    break
                    
                # Parse the JSON message
                message = json.loads(line.decode())
                
                # Handle the message
                response = await self.handle_message(message)
                
                # Send response if not a notification
                if response is not None:
                    print(json.dumps(response), flush=True)
                    
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)
                
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    # Disable any stdout logging from imported modules
    import logging
    logging.basicConfig(level=logging.ERROR)
    
    # Run the server
    server = MCPServer()
    asyncio.run(server.run()) 
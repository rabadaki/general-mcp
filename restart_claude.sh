#!/bin/bash

echo "🔄 Restarting Claude Desktop for MCP server update..."

# Kill any old MCP processes
pkill -f "mcp_stdio_server" 2>/dev/null
pkill -f "mcp-stdio-bridge" 2>/dev/null
pkill -f "server.py" 2>/dev/null

# Force quit Claude Desktop
osascript -e 'quit app "Claude"' 2>/dev/null
sleep 2

# Kill Claude processes if still running
pkill -f "Claude" 2>/dev/null
sleep 1

echo "✅ Old processes cleared"

# Clear any Claude cache/state (optional)
# rm -rf ~/Library/Caches/Claude/* 2>/dev/null

echo "🚀 Starting Claude Desktop..."
open -a "Claude"

echo "✅ Claude Desktop restarted. MCP server should now work correctly."
echo "💡 Test with: 'search reddit for test'" 
# Cursor MCP Setup Guide

## Current Status
✅ MCP Server is configured and running
✅ Configuration files are in place
❌ MCP tools are not showing in Cursor chat interface

## Configuration Locations Checked

1. **Global MCP Config**: `~/.cursor/mcp.json` ✅ (Created)
2. **Project MCP Config**: `.cursor/mcp.json` ✅ (Created)
3. **Old Config Location**: `~/.config/cursor/mcp.json` (Not used by Cursor)

## Current Configuration
```json
{
  "mcpServers": {
    "general-mcp": {
      "command": "/Users/Amos/general-mcp/venv/bin/python",
      "args": ["/Users/Amos/general-mcp/mcp_stdio_server.py"],
      "env": {
        "APIFY_TOKEN": "apify_api_6mzlRzrG8SXTZJembhBd6OWHwyYDNH0OIlgM",
        "PERPLEXITY_API_KEY": "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",
        "YOUTUBE_API_KEY": "AIzaSyA_JGbNe7Tn60dX2AIHudSSMcamcba3szQ"
      }
    }
  }
}
```

## Troubleshooting Steps Taken

1. ✅ Created MCP configuration in the correct location (`~/.cursor/mcp.json`)
2. ✅ Verified MCP server can start and run
3. ✅ Added all required API keys
4. ✅ Used correct Python interpreter from virtual environment
5. ✅ Created project-level configuration as backup

## Why MCP Tools Aren't Showing

Based on the Cursor documentation and testing:

1. **Cursor Version**: Ensure you have Cursor version 0.47.x or above
2. **MCP is a separate feature**: MCP tools appear under "Available Tools" in Cursor's MCP settings page, not in the regular chat tools
3. **Restart Required**: After configuring MCP, Cursor needs a full restart (not just reload)

## Next Steps to Enable MCP

### 1. Check Cursor Version
- Go to Cursor → About Cursor
- Ensure version is 0.47.x or higher

### 2. Access MCP Settings
- Open Cursor Settings (Cmd+,)
- Navigate to: **Cursor Settings → MCP**
- You should see your "general-mcp" server listed there

### 3. Enable MCP Tools
- In the MCP settings page, you should see "Available Tools"
- Toggle on the tools you want to use
- The Cursor Agent will automatically use enabled tools when relevant

### 4. Using MCP Tools
- Tools are used automatically by the Cursor Agent when needed
- You can prompt the agent to use specific tools by name
- Enable "Auto-run" for tools to execute without approval

## Important Notes

1. **MCP tools are NOT the same as built-in chat tools** - They appear in a different section
2. **The AI assistant (me) cannot see or use MCP tools** - They are only available to Cursor's Agent feature
3. **MCP integration is for Cursor's Agent/Composer** - Not for the regular chat interface

## Testing Your MCP Setup

1. Open a new Composer session (not chat)
2. Ask it to use one of your tools, e.g., "Search Reddit for Python tutorials"
3. The Agent should automatically invoke the appropriate MCP tool

## If Still Not Working

1. **Check Cursor Console**: View → Developer → Toggle Developer Tools → Console
2. **Look for MCP errors**: Any errors related to MCP loading
3. **Verify server is accessible**: The MCP server process should be running
4. **Try manual restart**: Quit Cursor completely (Cmd+Q) and reopen

## Alternative Approach

If MCP isn't available in your Cursor version, you can still use the tools by:
1. Running the server in HTTP mode instead of stdio
2. Using the FastAPI endpoints directly
3. Or waiting for Cursor to fully roll out MCP support

The MCP feature is relatively new and may not be available in all Cursor installations yet. 
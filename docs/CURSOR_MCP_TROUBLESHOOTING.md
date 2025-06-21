# Cursor MCP Troubleshooting: 0 Tools Showing

## Current Situation
- ✅ MCP server `general-mcp` appears in Cursor settings
- ❌ Shows "0 tools enabled"
- ✅ Server responds correctly when tested manually

## Solution Steps

### 1. Restart Cursor with Clean State
1. **Completely quit Cursor** (Cmd+Q on Mac)
2. **Kill any lingering MCP processes**:
   ```bash
   pkill -f mcp_stdio_server
   ```
3. **Restart Cursor**

### 2. Check Cursor Developer Console
1. Open Cursor
2. Go to **View → Developer → Toggle Developer Tools**
3. Click on the **Console** tab
4. Look for any MCP-related errors
5. Try refreshing the MCP settings page

### 3. Verify MCP Server Connection
In the Developer Console, you might see messages like:
- "MCP server 'general-mcp' connected"
- "Fetching tools from 'general-mcp'"
- Any error messages about tool fetching

### 4. Manual Tool Toggle
1. Go to **Cursor Settings → MCP**
2. Click on `general-mcp` server
3. Look for a refresh button or toggle to reload tools
4. Sometimes tools appear after a few seconds delay

### 5. Alternative Configuration Format
If tools still don't show, try this alternative configuration in `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "general-mcp": {
      "command": "node",
      "args": [
        "-e",
        "const { spawn } = require('child_process'); const proc = spawn('/Users/Amos/general-mcp/venv/bin/python', ['-u', '/Users/Amos/general-mcp/mcp_stdio_server.py']); proc.stdout.pipe(process.stdout); proc.stderr.pipe(process.stderr); process.stdin.pipe(proc.stdin);"
      ]
    }
  }
}
```

### 6. Check MCP Version Compatibility
Ensure your Cursor version supports MCP:
- Go to **Cursor → About Cursor**
- Version should be **0.47.x or higher**
- If older, update Cursor

### 7. Enable Debug Logging
Add debug logging to see what's happening:
1. Set environment variable: `export MCP_DEBUG=true`
2. Restart Cursor
3. Check logs in Developer Console

## Common Issues & Fixes

### Issue: Tools list times out
**Fix**: The server might be taking too long to respond. Try:
- Reducing the number of tools
- Optimizing the server startup time

### Issue: JSON parsing errors
**Fix**: Ensure the server outputs clean JSON without extra logging to stdout

### Issue: Permission denied
**Fix**: Ensure the wrapper script is executable:
```bash
chmod +x /Users/Amos/general-mcp/mcp_wrapper.sh
```

### Issue: Python path issues
**Fix**: Use absolute paths and ensure virtual environment is activated in wrapper

## If Nothing Works

1. **Try the HTTP mode instead**:
   - Run: `python mcp_stdio_server.py --http`
   - This starts the server in HTTP mode on port 8080
   - Configure Cursor to use the HTTP endpoint

2. **Check Cursor's MCP implementation status**:
   - MCP is relatively new in Cursor
   - Check Cursor forums/Discord for updates
   - Some features might be in beta

3. **Use the Composer directly**:
   - Even if tools don't show in settings, try using them in Composer
   - Example: "Use the search_reddit tool to find Python tutorials"

## Debug Commands

Test the MCP server manually:
```bash
# Test initialization
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}' | /Users/Amos/general-mcp/mcp_wrapper.sh

# Test tools listing
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 2}' | /Users/Amos/general-mcp/mcp_wrapper.sh
```

Both should return valid JSON responses. 
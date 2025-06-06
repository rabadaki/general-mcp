#!/usr/bin/env node

const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio');
const { Server } = require('@modelcontextprotocol/sdk/server');

// Create a proxy server that forwards requests to the Railway MCP server
const server = new Server(
  {
    name: 'general-search-proxy',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

let remoteClient = null;

// Initialize connection to remote server
async function initRemoteConnection() {
  try {
    const response = await fetch('https://general-mcp-production.up.railway.app/sse', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        method: 'initialize',
        params: {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: {
            name: 'claude-proxy',
            version: '1.0.0'
          }
        },
        jsonrpc: '2.0',
        id: 1
      })
    });
    
    console.error('Remote connection initialized');
    return response;
  } catch (error) {
    console.error('Failed to connect to remote server:', error);
    throw error;
  }
}

// Forward tool calls to remote server
server.setRequestHandler('tools/list', async () => {
  try {
    const response = await fetch('https://general-mcp-production.up.railway.app/sse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: 'tools/list',
        params: {},
        jsonrpc: '2.0',
        id: 2
      })
    });
    
    const result = await response.json();
    return result.result || { tools: [] };
  } catch (error) {
    console.error('Failed to list tools:', error);
    return { tools: [] };
  }
});

server.setRequestHandler('tools/call', async (request) => {
  try {
    const response = await fetch('https://general-mcp-production.up.railway.app/sse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: 'tools/call',
        params: request.params,
        jsonrpc: '2.0',
        id: 3
      })
    });
    
    const result = await response.json();
    return result.result || {};
  } catch (error) {
    console.error('Failed to call tool:', error);
    throw error;
  }
});

// Start the proxy server
async function main() {
  try {
    await initRemoteConnection();
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error('MCP proxy server started');
  } catch (error) {
    console.error('Failed to start proxy server:', error);
    process.exit(1);
  }
}

main(); 
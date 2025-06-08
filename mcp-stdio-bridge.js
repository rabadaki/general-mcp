#!/usr/bin/env node

const readline = require('readline');

const MCP_SERVER_URL = 'https://general-mcp.onrender.com/message';

// Use built-in fetch if available (Node 18+), otherwise use https module
let fetchFunction;

if (typeof globalThis.fetch !== 'undefined') {
  fetchFunction = globalThis.fetch;
} else {
  // Fallback to https module for older Node versions
  const https = require('https');
  const { URL } = require('url');
  
  fetchFunction = (url, options = {}) => {
    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const requestOptions = {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port,
        path: parsedUrl.pathname + parsedUrl.search,
        method: options.method || 'GET',
        headers: options.headers || {}
      };

      const req = https.request(requestOptions, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          resolve({
            ok: res.statusCode >= 200 && res.statusCode < 300,
            status: res.statusCode,
            statusText: res.statusMessage,
            json: () => Promise.resolve(JSON.parse(data)),
            text: () => Promise.resolve(data)
          });
        });
      });

      req.on('error', reject);
      
      if (options.body) {
        req.write(options.body);
      }
      
      req.end();
    });
  };
}

// Create interface for stdin/stdout communication
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

// Handle incoming messages from Claude Desktop
rl.on('line', async (line) => {
  let message;
  let messageId = null;
  
  try {
    message = JSON.parse(line.trim());
    messageId = message.id || null;
    
    const response = await fetchFunction(MCP_SERVER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(message)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    
    // Handle notification responses - don't send any response
    if (result && result.__notification__ === true) {
      process.stderr.write(`Debug: Notification handled, no response sent\n`);
      return;
    }
    
    // Comprehensive response validation and repair
    if (result && typeof result === 'object') {
      // Ensure all responses have jsonrpc field
      if (!result.jsonrpc) {
        result.jsonrpc = "2.0";
      }
      
      // Ensure proper ID handling
      if (messageId !== null && messageId !== undefined) {
        result.id = messageId;
      }
      
      // Clean up any malformed error responses
      if (result.error && !result.result) {
        // This is an error response - ensure it's properly formatted
        const cleanResponse = {
          jsonrpc: "2.0",
          id: messageId,
          error: result.error
        };
        console.log(JSON.stringify(cleanResponse));
        return;
      }
      
      // For successful responses, ensure they have result field
      if (!result.error && !result.result) {
        result.result = {};
      }
    }
    
    console.log(JSON.stringify(result));
  } catch (error) {
    // Only send error response for requests that expect a response (have an id)
    if (messageId !== null && messageId !== undefined) {
      const errorResponse = {
        jsonrpc: "2.0",
        id: messageId,
        error: {
          code: -32603,
          message: `Internal error: ${error.message}`
        }
      };
      console.log(JSON.stringify(errorResponse));
    } else {
      // For notifications (no id), add debug info but don't send response
      process.stderr.write(`Debug: Notification error ignored: ${error.message}\n`);
    }
  }
});

process.on('SIGINT', () => {
  process.exit(0);
});

process.on('SIGTERM', () => {
  process.exit(0);
}); 
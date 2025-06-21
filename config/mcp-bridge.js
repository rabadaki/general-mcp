#!/usr/bin/env node

const readline = require('readline');
const https = require('https');

const MCP_SERVER_URL = 'https://general-mcp.onrender.com/message';

// Create interface for stdin/stdout communication
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

// Function to make HTTP request to our MCP server
function makeRequest(data) {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify(data);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = https.request(MCP_SERVER_URL, options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        try {
          const response = JSON.parse(responseData);
          resolve(response);
        } catch (error) {
          reject(error);
        }
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.write(postData);
    req.end();
  });
}

// Handle incoming messages from Claude Desktop
rl.on('line', async (line) => {
  try {
    const message = JSON.parse(line);
    const response = await makeRequest(message);
    console.log(JSON.stringify(response));
  } catch (error) {
    console.error(JSON.stringify({
      jsonrpc: "2.0",
      id: null,
      error: {
        code: -32000,
        message: error.message
      }
    }));
  }
});

process.on('SIGINT', () => {
  process.exit(0);
}); 
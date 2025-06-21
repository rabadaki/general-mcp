#!/usr/bin/env python3
"""
Simple stdio test for MCP protocol
"""

import json
import sys
import asyncio

async def simple_stdio_test():
    """Test basic stdio communication"""
    
    print("Starting simple stdio test...", file=sys.stderr)
    
    try:
        while True:
            # Read line from stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            
            if not line:
                print("No input received, breaking", file=sys.stderr)
                break
                
            print(f"Received: {line.strip()}", file=sys.stderr)
            
            try:
                message = json.loads(line.strip())
                
                # Echo back a simple response
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {"message": "Hello from MCP server", "received": message}
                }
                
                print(json.dumps(response), flush=True)
                print(f"Sent response for message {message.get('id')}", file=sys.stderr)
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(simple_stdio_test()) 
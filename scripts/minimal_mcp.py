#!/usr/bin/env python3
import sys
import json

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
            
        try:
            request = json.loads(line)
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2023-11-05",
                    "capabilities": {
                        "tools": {
                            "enabled": True,
                            "supported": True
                        }
                    },
                    "serverInfo": {
                        "name": "minimal-mcp"
                    }
                }
            }), flush=True)
            
            # Send tools list
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "test_tool",
                            "description": "A test tool",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "test": {
                                        "type": "string",
                                        "description": "Test parameter"
                                    }
                                },
                                "required": ["test"]
                            }
                        }
                    ]
                }
            }), flush=True)
            
        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }), flush=True)

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
import subprocess
import json
import time

def test_server():
    # Start the server
    server = subprocess.Popen(
        ['/Users/Amos/general-mcp/venv/bin/python', '-u', 'mcp_stdio_server.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1
    }
    server.stdin.write(json.dumps(init_request) + '\n')
    server.stdin.flush()
    
    # Read response
    init_response = server.stdout.readline()
    print("Initialize response:", init_response)
    
    # Send tools/list request
    tools_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    }
    server.stdin.write(json.dumps(tools_request) + '\n')
    server.stdin.flush()
    
    # Read response
    tools_response = server.stdout.readline()
    print("Tools response:", tools_response)
    
    # Cleanup
    server.terminate()
    server.wait()

if __name__ == "__main__":
    test_server() 
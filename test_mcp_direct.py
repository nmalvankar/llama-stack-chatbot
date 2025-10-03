#!/usr/bin/env python3
"""Direct test of MCP server connection."""

import asyncio
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_connection():
    """Test direct connection to MCP server."""
    endpoint = "https://ocp-mcp-server-mcp-player1.apps.cluster-2n692.2n692.sandbox557.opentlc.com/sse"
    
    try:
        # Step 1: Get session endpoint from SSE
        logger.info("Step 1: Getting session endpoint...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream('GET', endpoint) as response:
                logger.info(f"SSE Status: {response.status_code}")
                
                session_endpoint = None
                async for line in response.aiter_lines():
                    logger.info(f"SSE Line: '{line}'")
                    if line.startswith('data: ') and '/message?sessionId=' in line:
                        session_endpoint = line[6:]  # Remove 'data: '
                        logger.info(f"Found session: {session_endpoint}")
                        break
                    if len(line.strip()) > 0 and line.strip().startswith('/message?sessionId='):
                        session_endpoint = line.strip()
                        logger.info(f"Found session (direct): {session_endpoint}")
                        break
        
        if not session_endpoint:
            logger.error("No session endpoint found")
            return False
            
        # Step 2: Connect to session and list tools
        base_url = endpoint.rsplit('/', 1)[0]  # Remove /sse
        message_url = f"{base_url}{session_endpoint}"
        logger.info(f"Step 2: Connecting to {message_url}")
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                message_url,
                json=mcp_request,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            logger.info(f"Tools request status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Tools response: {json.dumps(result, indent=2)}")
                
                if 'result' in result and 'tools' in result['result']:
                    tools = result['result']['tools']
                    logger.info(f"Found {len(tools)} tools:")
                    for tool in tools:
                        logger.info(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    return True
                else:
                    logger.error("No tools found in response")
            else:
                logger.error(f"Failed to get tools: {response.text}")
                
        return False
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_connection())
    print(f"✅ Success: {success}" if success else "❌ Failed")

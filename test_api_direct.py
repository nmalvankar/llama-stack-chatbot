#!/usr/bin/env python3
"""Test API directly via HTTP."""

import asyncio
import httpx
import json

async def test_api_chat():
    """Test the chat API directly."""
    url = "http://localhost:8000/api/chat"
    message = "get list of pods in the mission-hq-player1 namespace"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={"message": message})
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response data: {json.dumps(data, indent=2)}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_chat())

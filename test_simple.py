#!/usr/bin/env python3
"""Simple test script for the chatbot."""

import asyncio
import logging
import sys
from pathlib import Path

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from src.simple_agent import SimpleLlamaStackAgent
from src.config import settings


async def test_agent():
    """Test the simple agent."""
    print(f"📡 MCP Endpoint: {settings.mcp_endpoint}")
    
    try:
        # Initialize agent
        print("🔄 Initializing agent...")
        agent = SimpleLlamaStackAgent()
        await agent.initialize()
        
        # Test tools
        print("🔧 Available tools:")
        tools = await agent.get_available_tools()
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # Test chat
        print("\n💬 Testing chat...")
        response = await agent.chat("Hello! What can you help me with?")
        print(f"🤖 Response: {response}")
        
        # Cleanup
        await agent.cleanup()
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True


async def test_api():
    """Test API endpoints."""
    import httpx
    
    print("\n🌐 Testing API endpoints...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            response = await client.get("http://localhost:8000/api/health")
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                
            # Test tools endpoint
            response = await client.get("http://localhost:8000/api/tools")
            if response.status_code == 200:
                tools = response.json()
                print(f"✅ Tools endpoint working ({len(tools)} tools)")
            else:
                print(f"❌ Tools endpoint failed: {response.status_code}")
                
    except Exception as e:
        print(f"❌ API test failed: {e}")
        print("💡 Make sure the server is running: python main.py")


if __name__ == "__main__":
    print("🧪 Simple Chatbot Test Suite")
    print("=" * 40)
    
    # Test agent
    success = asyncio.run(test_agent())
    
    if success:
        # Test API (optional, requires server to be running)
        try:
            asyncio.run(test_api())
        except:
            print("ℹ️  API tests skipped (server not running)")
    
    print("\n🎉 Testing complete!")

#!/usr/bin/env python3
"""Test the specific pods command that's failing."""

import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from src.simple_agent import SimpleLlamaStackAgent
from src.config import settings

async def test_pods_command():
    """Test the specific pods command."""
    print("🧪 Testing specific pods command...")
    print(f"📡 MCP Endpoint: {settings.mcp_endpoint}")
    
    try:
        # Initialize agent
        print("🔄 Initializing agent...")
        agent = SimpleLlamaStackAgent()
        await agent.initialize()
        
        # Test the specific command that's failing
        print("\n💬 Testing: 'get list of pods in the mission-hq-player1 namespace'")
        response = await agent.chat("get list of pods in the mission-hq-player1 namespace")
        print(f"🤖 Response: {response}")
        
        # Cleanup
        await agent.cleanup()
        print("✅ Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_pods_command())
    print(f"Result: {'✅ Success' if success else '❌ Failed'}")

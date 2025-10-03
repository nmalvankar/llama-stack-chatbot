"""Tests for the MCP client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.mcp_client import MCPClient


@pytest.fixture
def mcp_client():
    """Create an MCP client for testing."""
    return MCPClient("ws://test-server:8080/mcp", "test-token")


@pytest.mark.asyncio
async def test_websocket_connection(mcp_client):
    """Test WebSocket connection."""
    with patch('src.mcp_client.ClientSession') as mock_session:
        mock_session.connect_websocket = AsyncMock()
        mock_session_instance = AsyncMock()
        mock_session.connect_websocket.return_value = mock_session_instance
        
        # Mock tools and resources
        mock_tools_result = MagicMock()
        mock_tools_result.tools = []
        mock_session_instance.list_tools.return_value = mock_tools_result
        
        mock_resources_result = MagicMock()
        mock_resources_result.resources = []
        mock_session_instance.list_resources.return_value = mock_resources_result
        
        await mcp_client.connect()
        
        assert mcp_client.session is not None
        mock_session.connect_websocket.assert_called_once()


@pytest.mark.asyncio
async def test_tool_calling(mcp_client):
    """Test tool calling functionality."""
    # Mock session
    mock_session = AsyncMock()
    mcp_client.session = mock_session
    
    # Mock tool
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mcp_client.tools = {"test_tool": mock_tool}
    
    # Mock result
    mock_result = MagicMock()
    mock_session.call_tool.return_value = mock_result
    
    result = await mcp_client.call_tool("test_tool", {"param": "value"})
    
    assert result == mock_result
    mock_session.call_tool.assert_called_once_with("test_tool", {"param": "value"})


@pytest.mark.asyncio
async def test_tool_not_found(mcp_client):
    """Test calling a non-existent tool."""
    mock_session = AsyncMock()
    mcp_client.session = mock_session
    mcp_client.tools = {}
    
    with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
        await mcp_client.call_tool("nonexistent", {})


@pytest.mark.asyncio
async def test_disconnect(mcp_client):
    """Test disconnection."""
    mock_session = AsyncMock()
    mcp_client.session = mock_session
    
    await mcp_client.disconnect()
    
    mock_session.close.assert_called_once()
    assert mcp_client.session is None

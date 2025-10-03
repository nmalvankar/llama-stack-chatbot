"""MCP Client for connecting to remote MCP servers."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import websockets
import httpx
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.client.sse import SseServerParameters
from mcp.client.websocket import WebSocketServerParameters

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to remote MCP servers."""
    
    def __init__(self, endpoint: str, auth_token: Optional[str] = None):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.session: Optional[ClientSession] = None
        self.tools: Dict[str, types.Tool] = {}
        self.resources: Dict[str, types.Resource] = {}
        
    async def connect(self) -> None:
        """Connect to the MCP server via SSE."""
        try:
            # Force SSE connection for Kubernetes deployment
            await self._connect_sse()
                
            await self._initialize_capabilities()
            logger.info(f"Connected to MCP server at {self.endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
            
    async def _connect_websocket(self) -> None:
        """Connect via WebSocket."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            
        server_params = WebSocketServerParameters(
            url=self.endpoint,
            headers=headers
        )
        
        self.session = await ClientSession.connect_websocket(server_params)
        
    async def _connect_sse(self) -> None:
        """Connect via Server-Sent Events."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            
        server_params = SseServerParameters(
            url=self.endpoint,
            headers=headers
        )
        
        self.session = await ClientSession.connect_sse(server_params)
        
    async def _initialize_capabilities(self) -> None:
        """Initialize server capabilities and fetch available tools."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        # List available tools
        try:
            tools_result = await self.session.list_tools()
            self.tools = {tool.name: tool for tool in tools_result.tools}
            logger.info(f"Loaded {len(self.tools)} tools from MCP server")
            
        except Exception as e:
            logger.warning(f"Failed to load tools: {e}")
            
        # List available resources
        try:
            resources_result = await self.session.list_resources()
            self.resources = {resource.uri: resource for resource in resources_result.resources}
            logger.info(f"Loaded {len(self.resources)} resources from MCP server")
            
        except Exception as e:
            logger.warning(f"Failed to load resources: {e}")
            
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        """Call a tool on the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found. Available tools: {list(self.tools.keys())}")
            
        try:
            result = await self.session.call_tool(name, arguments)
            return result
            
        except Exception as e:
            logger.error(f"Failed to call tool '{name}': {e}")
            raise
            
    async def read_resource(self, uri: str) -> types.ReadResourceResult:
        """Read a resource from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        try:
            result = await self.session.read_resource(uri)
            return result
            
        except Exception as e:
            logger.error(f"Failed to read resource '{uri}': {e}")
            raise
            
    def get_available_tools(self) -> List[types.Tool]:
        """Get list of available tools."""
        return list(self.tools.values())
        
    def get_available_resources(self) -> List[types.Resource]:
        """Get list of available resources."""
        return list(self.resources.values())
        
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Disconnected from MCP server")

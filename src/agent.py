"""Simple Llama Stack Agent with Google Gemini and MCP integration."""

import logging
from typing import Any, Dict, List, Optional, AsyncGenerator
import json

from llama_stack_client import LlamaStackClient
import google.generativeai as genai

from .config import settings
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)


class LlamaStackAgent:
    """Simple Llama Stack Agent with Google Gemini LLM and MCP tool integration."""
    
    def __init__(self):
        self.mcp_client: Optional[MCPClient] = None
        self.gemini_model = None
        
    async def initialize(self) -> None:
        """Initialize the agent with MCP client and Google Gemini."""
        try:
            # Configure Google Gemini
            genai.configure(api_key=settings.google_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
            
            # Initialize MCP client for tools
            self.mcp_client = MCPClient(
                endpoint=settings.mcp_endpoint,
                auth_token=settings.mcp_auth_token
            )
            await self.mcp_client.connect()
            
            logger.info("Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
            
    async def chat(self, message: str) -> str:
        """Create the Llama Stack agent with MCP tools."""
        if not self.mcp_client:
            raise RuntimeError("MCP client not initialized")
            
        # Convert MCP tools to Llama Stack tool definitions
        tools = []
        for mcp_tool in self.mcp_client.get_available_tools():
            tool_def = ToolDefinition(
                name=mcp_tool.name,
                description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                parameters=self._convert_mcp_schema_to_llama_params(mcp_tool.inputSchema)
            )
            tools.append(tool_def)
            
        # Create agent configuration
        agent_config = AgentConfig(
            model="gemini-2.5-flash",  # Using Google Gemini
            instructions="""You are a helpful AI assistant with access to kuberetes server through an MCP server.
            You can help users with a wide range of tasks using the available tools.
            Always be helpful, accurate, and explain what you're doing when using tools.""",
            tools=tools,
            tool_choice="auto",
            enable_session_persistence=True
        )
        
        # Create the agent
        agent_response = await self.llama_client.agents.create(config=agent_config)
        self.agent_id = agent_response.agent_id
        
        # Create a session
        session_response = await self.llama_client.agents.sessions.create(
            agent_id=self.agent_id,
            session_name="chatbot_session"
        )
        self.session_id = session_response.session_id
        
        logger.info(f"Created agent {self.agent_id} with session {self.session_id}")
        
    def _convert_mcp_schema_to_llama_params(self, schema: Dict[str, Any]) -> Dict[str, ToolParamDefinition]:
        """Convert MCP tool schema to Llama Stack parameter definitions."""
        params = {}
        
        if "properties" in schema:
            for param_name, param_schema in schema["properties"].items():
                param_def = ToolParamDefinition(
                    param_type=param_schema.get("type", "string"),
                    description=param_schema.get("description", f"Parameter: {param_name}"),
                    required=param_name in schema.get("required", [])
                )
                params[param_name] = param_def
                
        return params
        
    async def chat_stream(self, message: str) -> AsyncGenerator[str, None]:
        """Stream chat response from the agent."""
        if not self.llama_client or not self.agent_id or not self.session_id:
            raise RuntimeError("Agent not initialized")
            
        try:
            # Create user message
            user_msg = UserMessage(content=message, role="user")
            
            # Create agent turn
            turn_params = AgentTurnCreateParams(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=[user_msg],
                stream=True
            )
            
            # Stream the response
            async for chunk in self.llama_client.agents.turns.create(**turn_params):
                if hasattr(chunk, 'delta') and chunk.delta:
                    if hasattr(chunk.delta, 'content'):
                        yield chunk.delta.content
                elif hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    # Handle tool calls
                    for tool_call in chunk.tool_calls:
                        yield await self._handle_tool_call(tool_call)
                        
        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            yield f"Error: {str(e)}"
            
    async def _handle_tool_call(self, tool_call) -> str:
        """Handle tool calls by routing to MCP client."""
        if not self.mcp_client:
            return "Error: MCP client not available"
            
        try:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            # Call the MCP tool
            result = await self.mcp_client.call_tool(tool_name, arguments)
            
            # Format the result
            if result.content:
                if isinstance(result.content, list):
                    return "\n".join([str(item) for item in result.content])
                else:
                    return str(result.content)
            else:
                return f"Tool {tool_name} executed successfully"
                
        except Exception as e:
            logger.error(f"Error handling tool call: {e}")
            return f"Error executing tool: {str(e)}"
            
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        if not self.mcp_client:
            return []
            
        tools = []
        for mcp_tool in self.mcp_client.get_available_tools():
            tools.append({
                "name": mcp_tool.name,
                "description": mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                "schema": mcp_tool.inputSchema
            })
            
        return tools
        
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.mcp_client:
            await self.mcp_client.disconnect()
            
        logger.info("Agent cleanup completed")

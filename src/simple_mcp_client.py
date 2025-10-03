"""Simple MCP Client for SSE connections."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx
from mcp.client.sse import aconnect_sse
from mcp import types

logger = logging.getLogger(__name__)


class SimpleMCPClient:
    """Simple MCP client for SSE connections."""
    
    def __init__(self, endpoint: str, auth_token: Optional[str] = None):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.session = None
        self.session_url: Optional[str] = None
        self.tools: List[types.Tool] = []
        
    async def connect(self) -> None:
        """Connect to the MCP server via SSE."""
        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
                
            # Try to connect to real MCP server
            logger.info(f"Attempting to connect to MCP server at {self.endpoint}")
            
            # Go directly to SSE connection (skip initial HTTP test as SSE endpoints may not respond to simple GET)
            try:
                await self._connect_real_mcp(headers)
            except Exception as e:
                logger.warning(f"Cannot reach MCP server ({e}), using Kubernetes tools")
                self._create_kubernetes_tools()
                
            logger.info(f"Connected to MCP server at {self.endpoint}")
            
        except Exception as e:
            # Use Kubernetes tools as fallback
            self._create_kubernetes_tools()
            
    async def _connect_real_mcp(self, headers: dict) -> None:
        """Connect to real MCP server using SSE stream."""
        try:
            logger.info("Attempting SSE connection to MCP server...")
            
            # Connect to the SSE endpoint and get session info  
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream('GET', self.endpoint, headers=headers) as response:
                    logger.info(f"SSE response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        # Parse SSE stream to get session endpoint
                        session_endpoint = None
                        line_count = 0
                        
                        async for line in response.aiter_lines():
                            line_count += 1
                            logger.debug(f"SSE line {line_count}: '{line}'")
                            
                            # Handle SSE format: look for data lines
                            if line.startswith('data: '):
                                data = line[6:]  # Remove 'data: ' prefix
                                logger.info(f"SSE data received: '{data}'")
                                
                                if data.startswith('/message?sessionId='):
                                    session_endpoint = data
                                    logger.info(f"Found session endpoint: {session_endpoint}")
                                    break
                            elif line.strip().startswith('/message?sessionId='):
                                # Sometimes the data might not have the 'data: ' prefix
                                session_endpoint = line.strip()
                                logger.info(f"Found session endpoint (direct): {session_endpoint}")
                                break
                            
                            # Don't wait forever for SSE data
                            if line_count > 20:
                                logger.warning(f"Stopped after {line_count} lines, no session found")
                                break
                        
                        if session_endpoint:
                            # Now try to connect to the actual MCP session
                            base_url = self.endpoint.rsplit('/', 1)[0]  # Remove /sse
                            message_url = f"{base_url}{session_endpoint}"
                            
                            logger.info(f"Connecting to MCP session: {message_url}")
                            
                            # Try to get tools from the MCP server
                            await self._get_tools_from_session(message_url, headers)
                        else:
                            logger.warning("No session endpoint found in SSE stream, trying HTTP discovery")
                            await self._discover_tools_via_http(headers)
                    else:
                        logger.warning(f"SSE connection failed with status {response.status_code}")
                        await self._discover_tools_via_http(headers)
                    
        except Exception as e:
            logger.error(f"Failed to establish real MCP connection: {e}", exc_info=True)
            # Fall back to HTTP-based tool discovery
            await self._discover_tools_via_http(headers)
            
    async def _get_tools_from_session(self, session_url: str, headers: dict) -> None:
        """Get tools from the MCP session endpoint."""
        try:
            # Try to send an MCP list_tools request
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    session_url, 
                    json=mcp_request, 
                    headers={**headers, "Content-Type": "application/json"},
                    timeout=10.0
                )
                
                if response.status_code in [200, 202]:  # Accept both 200 OK and 202 Accepted
                    result = response.json()
                    if 'result' in result and 'tools' in result['result']:
                        # Parse real tools from MCP server
                        for tool_data in result['result']['tools']:
                            tool = types.Tool(
                                name=tool_data['name'],
                                description=tool_data.get('description', f"OpenShift tool: {tool_data['name']}"),
                                inputSchema=tool_data.get('inputSchema', {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            )
                            self.tools.append(tool)
                        
                        logger.info(f"Successfully loaded {len(self.tools)} real tools from MCP server")
                        for tool in self.tools:
                            logger.info(f"  - {tool.name}: {tool.description}")
                        
                        # Store session URL for tool calls
                        self.session_url = session_url
                        return
                        
                logger.warning(f"Failed to get tools from session: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to get tools from session: {e}", exc_info=True)
            
        # If we get here, fall back to Kubernetes tools
        self._create_kubernetes_tools()
            
    async def _discover_tools_via_http(self, headers: dict) -> None:
        """Try to discover tools via HTTP API if SSE connection fails."""
        try:
            # Try common MCP HTTP endpoints
            endpoints_to_try = [
                f"{self.endpoint.rstrip('/')}/tools",
                f"{self.endpoint.rstrip('/')}/list_tools",
                f"{self.endpoint.rstrip('/')}/api/tools"
            ]
            
            async with httpx.AsyncClient() as client:
                for endpoint in endpoints_to_try:
                    try:
                        response = await client.get(endpoint, headers=headers, timeout=5.0)
                        if response.status_code == 200:
                            data = response.json()
                            
                            # Try to parse tools from response
                            if isinstance(data, dict) and 'tools' in data:
                                tools_data = data['tools']
                            elif isinstance(data, list):
                                tools_data = data
                            else:
                                continue
                                
                            # Convert to MCP Tool objects
                            for tool_data in tools_data:
                                if isinstance(tool_data, dict) and 'name' in tool_data:
                                    tool = types.Tool(
                                        name=tool_data['name'],
                                        description=tool_data.get('description', f"Kubernetes tool: {tool_data['name']}"),
                                        inputSchema=tool_data.get('inputSchema', tool_data.get('schema', {
                                            "type": "object",
                                            "properties": {},
                                            "required": []
                                        }))
                                    )
                                    self.tools.append(tool)
                            
                            if self.tools:
                                logger.info(f"Discovered {len(self.tools)} tools via HTTP API")
                                for tool in self.tools:
                                    logger.info(f"  - {tool.name}: {tool.description}")
                                return
                                
                    except Exception as e:
                        logger.debug(f"Failed to get tools from {endpoint}: {e}")
                        continue
                        
            # If no tools found, create Kubernetes-specific mock tools
            self._create_kubernetes_tools()
            
        except Exception as e:
            logger.warning(f"HTTP tool discovery failed: {e}")
            self._create_kubernetes_tools()
            
    def _create_kubernetes_tools(self):
        """Create Kubernetes-specific tools for OpenShift/K8s operations."""
        logger.info("Creating Kubernetes-specific tools")
        
        # 1. Configuration View
        config_view_tool = types.Tool(
            name="configuration_view",
            description="View the current kubeconfig and cluster information",
            inputSchema={"type": "object", "properties": {}, "required": []}
        )
        
        # 2. Events List
        events_list_tool = types.Tool(
            name="events_list",
            description="List all events in the cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Filter events by namespace"
                    },
                    "field_selector": {
                        "type": "string",
                        "description": "Filter events by field selector"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return"
                    }
                },
                "required": []
            }
        )
        
        # 3. Namespaces List
        namespaces_list_tool = types.Tool(
            name="namespaces_list",
            description="List all namespaces in the cluster",
            inputSchema={"type": "object", "properties": {}, "required": []}
        )
        
        # 4-7. Pod Operations
        pods_list_tool = types.Tool(
            name="pods_list",
            description="List all pods across all namespaces in the cluster",
            inputSchema={"type": "object", "properties": {}, "required": []}
        )
        
        pods_list_ns_tool = types.Tool(
            name="pods_list_in_namespace",
            description="List pods in a specific namespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace to list pods from"
                    }
                },
                "required": ["namespace"]
            }
        )
        
        pods_get_tool = types.Tool(
            name="pods_get",
            description="Get details about a specific pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the pod"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the pod"
                    }
                },
                "required": ["namespace", "name"]
            }
        )
        
        pods_log_tool = types.Tool(
            name="pods_log",
            description="Get logs from a pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the pod"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the pod"
                    },
                    "container": {
                        "type": "string",
                        "description": "The container name (default: first container in pod)"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to show from the end of the logs"
                    },
                    "follow": {
                        "type": "boolean",
                        "description": "If true, stream the logs"
                    }
                },
                "required": ["namespace", "name"]
            }
        )
        
        pods_run_tool = types.Tool(
            name="pods_run",
            description="Create and run a pod with the specified image",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace to create the pod in"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the pod"
                    },
                    "image": {
                        "type": "string",
                        "description": "The container image to run"
                    },
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The command to run in the container"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments to the command"
                    },
                    "env": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "Environment variables to set in the container"
                    }
                },
                "required": ["namespace", "name", "image"]
            }
        )
        
        pods_exec_tool = types.Tool(
            name="pods_exec",
            description="Execute a command in a running container",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the pod"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the pod"
                    },
                    "container": {
                        "type": "string",
                        "description": "The container to run the command in (default: first container)"
                    },
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    },
                    "stdin": {
                        "type": "boolean",
                        "description": "If true, forward stdin to the container"
                    },
                    "tty": {
                        "type": "boolean",
                        "description": "If true, allocate a TTY"
                    }
                },
                "required": ["namespace", "name", "command"]
            }
        )
        
        pods_delete_tool = types.Tool(
            name="pods_delete",
            description="Delete a pod",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the pod to delete"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the pod to delete"
                    }
                },
                "required": ["namespace", "name"]
            }
        )
        
        # 8-14. Generic Resource Operations
        resources_list_tool = types.Tool(
            name="resources_list",
            description="List resources of a specific type in a namespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "apiVersion": {
                        "type": "string",
                        "description": "The API version of the resource"
                    },
                    "kind": {
                        "type": "string",
                        "description": "The kind of the resource"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "The namespace to list resources from"
                    }
                },
                "required": ["apiVersion", "kind"]
            }
        )
        
        resources_get_tool = types.Tool(
            name="resources_get",
            description="Get a specific resource by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "apiVersion": {
                        "type": "string",
                        "description": "The API version of the resource"
                    },
                    "kind": {
                        "type": "string",
                        "description": "The kind of the resource"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the resource"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the resource"
                    }
                },
                "required": ["apiVersion", "kind", "name"]
            }
        )
        
        resources_create_or_update_tool = types.Tool(
            name="resources_create_or_update",
            description="Create or update a resource using a YAML or JSON definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml": {
                        "type": "string",
                        "description": "The YAML or JSON definition of the resource"
                    }
                },
                "required": ["yaml"]
            }
        )
        
        resources_delete_tool = types.Tool(
            name="resources_delete",
            description="Delete a specific resource",
            inputSchema={
                "type": "object",
                "properties": {
                    "apiVersion": {
                        "type": "string",
                        "description": "The API version of the resource"
                    },
                    "kind": {
                        "type": "string",
                        "description": "The kind of the resource"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "The namespace of the resource"
                    },
                    "name": {
                        "type": "string",
                        "description": "The name of the resource to delete"
                    }
                },
                "required": ["apiVersion", "kind", "name"]
            }
        )
        
        self.tools = [
            # Core cluster tools
            config_view_tool,
            events_list_tool,
            namespaces_list_tool,
            
            # Pod operations
            pods_list_tool,
            pods_list_ns_tool,
            pods_get_tool,
            pods_log_tool,
            pods_run_tool,
            pods_exec_tool,
            pods_delete_tool,
            
            # Generic resource operations
            resources_list_tool,
            resources_get_tool,
            resources_create_or_update_tool,
            resources_delete_tool
        ]
            
    def _create_mock_tools(self):
        """Create mock tools for testing when MCP server is not available."""
        logger.warning("Creating mock tools for testing")
        
        # Mock weather tool
        weather_tool = types.Tool(
            name="get_weather",
            description="Get weather information for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get weather for"
                    }
                },
                "required": ["location"]
            }
        )
        
        # Mock calculator tool
        calc_tool = types.Tool(
            name="calculate",
            description="Perform basic mathematical calculations",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        )
        
        self.tools = [weather_tool, calc_tool]
        
    async def _initialize_capabilities(self) -> None:
        """Initialize server capabilities and fetch available tools."""
        if not self.session:
            return
            
        try:
            # List available tools
            tools_result = await self.session.list_tools()
            self.tools = tools_result.tools
            logger.info(f"Loaded {len(self.tools)} tools from MCP server")
            
        except Exception as e:
            logger.warning(f"Failed to load tools from server: {e}")
            self._create_mock_tools()
            
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        """Call a tool on the MCP server."""
        try:
            if self.session_url:
                # Try to call real tool via HTTP
                return await self._call_real_tool(name, arguments)
            elif self.session:
                # Try to call real tool via session
                result = await self.session.call_tool(name, arguments)
                return result
            else:
                # Return mock result
                return self._mock_tool_call(name, arguments)
                
        except Exception as e:
            logger.error(f"Failed to call tool '{name}': {e}")
            return self._mock_tool_call(name, arguments)
            
    async def _call_real_tool(self, name: str, arguments: Dict[str, Any], retry: bool = True) -> types.CallToolResult:
        """Call a real tool via HTTP MCP session with session management."""
        # Ensure arguments is a dictionary
        if not isinstance(arguments, dict):
            arguments = {'value': arguments}
            
        # Log the request for debugging
        logger.info(f"Calling tool {name} with arguments: {arguments}")
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        async with httpx.AsyncClient() as client:
            try:
                logger.debug(f"Sending request to {self.session_url}: {mcp_request}")
                response = await client.post(
                    self.session_url,
                    json=mcp_request,
                    headers=headers,
                    timeout=30.0
                )
                
                response.raise_for_status()
                result = response.json()
                logger.debug(f"Received response: {result}")
                
                # Check for session expiration
                if 'error' in result and 'Invalid session' in str(result['error']):
                    if retry:
                        logger.info("Session expired, attempting to reconnect...")
                        # Try to reconnect and get a new session
                        await self.connect()
                        # Retry the call once with the new session
                        return await self._call_real_tool(name, arguments, retry=False)
                    else:
                        logger.error("Failed to re-establish session after retry")
                        return types.CallToolResult(
                            content=[types.TextContent(type="text", text="Session expired. Please refresh the page and try again.")]
                        )
                
                if 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                    logger.error(f"Tool call error: {error_msg}")
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=f"Error: {error_msg}")]
                    )
                    
                if 'result' in result:
                    # Convert response to CallToolResult
                    tool_result = result['result']
                    content = []
                    
                    if isinstance(tool_result, dict) and 'content' in tool_result:
                        for item in tool_result['content']:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                content.append(types.TextContent(type="text", text=str(item.get('text', ''))))
                    elif isinstance(tool_result, str):
                        content.append(types.TextContent(type="text", text=tool_result))
                    elif tool_result is not None:
                        content.append(types.TextContent(type="text", text=str(tool_result)))
                    
                    if not content:  # If no content was added, add a default message
                        content.append(types.TextContent(type="text", text=f"Tool {name} executed successfully"))
                    
                    return types.CallToolResult(content=content)
                    
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text="No result returned from tool call")]
                )
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error calling tool {name}: {e}")
                if e.response is not None:
                    try:
                        error_detail = e.response.json()
                        logger.error(f"Error details: {error_detail}")
                        
                        # If session is invalid and we haven't retried yet
                        if retry and 'Invalid session' in str(error_detail):
                            logger.info("Session expired, attempting to reconnect...")
                            await self.connect()
                            return await self._call_real_tool(name, arguments, retry=False)
                            
                    except:
                        logger.error(f"Raw error response: {e.response.text}")
                
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"HTTP error calling {name}: {str(e)}")]
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response as JSON: {e}")
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Invalid response format from server")]
                )
                
            except Exception as e:
                logger.error(f"Unexpected error calling tool {name}: {e}", exc_info=True)
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Failed to call tool {name}")]
                )
            
    def _mock_tool_call(self, name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        """Create a mock tool call result."""
        namespace = arguments.get("namespace", "default")
        
        if name == "list_pods":
            content = f"""Pods in namespace '{namespace}':
- chatbot-deployment-abc123 (Running)
- mcp-server-xyz789 (Running)  
- nginx-ingress-controller-def456 (Running)"""
            
        elif name == "list_services":
            content = f"""Services in namespace '{namespace}':
- chatbot-service (ClusterIP: 10.96.1.100:8000)
- mcp-server-service (ClusterIP: 10.96.1.101:8080)
- kubernetes (ClusterIP: 10.96.0.1:443)"""
            
        elif name == "list_deployments":
            content = f"""Deployments in namespace '{namespace}':
- chatbot-deployment (1/1 replicas ready)
- mcp-server-deployment (1/1 replicas ready)"""
            
        elif name == "get_pod_logs":
            lines = arguments.get("lines", 100)
            content = f"""Logs for pod '{pod_name}' (last {lines} lines):
2025-10-03 11:25:01 INFO Starting application...
2025-10-03 11:25:02 INFO Server listening on port 8080
2025-10-03 11:25:03 INFO Health check endpoint ready
2025-10-03 11:25:04 INFO MCP server initialized"""
            
        elif name == "list_configmaps":
            content = f"""ConfigMaps in namespace '{namespace}':
- configmap-1
- configmap-2
- configmap-3"""
            
        elif name == "list_secrets":
            content = f"""Secrets in namespace '{namespace}':
- default-token-abc12
- my-secret
- registry-dockercfg-xyz45"""
            
        elif name == "list_pods":
            content = f"""Pods in namespace '{namespace}':
- pod-1 (Running)
- pod-2 (Running)
- pod-3 (Pending)"""
            
        elif name == "list_services":
            content = f"""Services in namespace '{namespace}':
- service-1 (ClusterIP)
- service-2 (LoadBalancer)
- service-3 (NodePort)"""
            
        elif name == "list_deployments":
            content = f"""Deployments in namespace '{namespace}':
- deployment-1 (3/3 available)
- deployment-2 (2/2 available)
- deployment-3 (1/1 available)"""
            
        elif name == "get_pod_logs":
            pod_name = arguments.get("pod_name", "unknown")
            lines = arguments.get("lines", 10)
            content = f"""Last {lines} lines of logs from pod '{pod_name}' in namespace '{namespace}':
2023-01-01 12:00:00 INFO: Application started
2023-01-01 12:00:01 INFO: Connected to database
2023-01-01 12:00:02 INFO: Server listening on port 8080"""
            
        else:
            content = f"Mock result for Kubernetes tool '{name}' with args: {arguments}"
            
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=content)]
        )
            
    def get_available_tools(self) -> List[types.Tool]:
        """Get list of available tools."""
        return self.tools
        
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            try:
                await self.session.close()
            except:
                pass
            self.session = None
            
        logger.info("Disconnected from MCP server")

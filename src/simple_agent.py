"""Simple Llama Stack Agent with Google Gemini and MCP integration."""

import datetime
import logging
from typing import Any, Dict, List, Optional
import json

import google.generativeai as genai

from .config import settings
from .simple_mcp_client import SimpleMCPClient

logger = logging.getLogger(__name__)


class SimpleLlamaStackAgent:
    """Simple agent that uses Google Gemini directly with MCP tools."""
    
    def __init__(self):
        self.mcp_client: Optional[SimpleMCPClient] = None
        self.gemini_model = None
        self.available_tools = []
        
    async def initialize(self) -> None:
        """Initialize the agent with MCP client and Google Gemini."""
        try:
            # Configure Google Gemini
            genai.configure(api_key=settings.google_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-flash-latest')
            
            # Initialize MCP client for tools
            self.mcp_client = SimpleMCPClient(
                endpoint=settings.mcp_endpoint,
                auth_token=settings.mcp_auth_token
            )
            await self.mcp_client.connect()
            
            # Get available tools
            self.available_tools = self.mcp_client.get_available_tools()
            
            logger.info(f"Agent initialized with {len(self.available_tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
            
    async def chat(self, message: str) -> str:
        """Process a chat message and return enhanced response."""
        if not self.gemini_model:
            raise RuntimeError("Agent not initialized")
            
        try:
            # Create a clean prompt that doesn't trigger function calling
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_prompt = f"""You are a helpful assistant. Respond to the user's query directly. 
            If you need to perform an action, use the call_tool() format exactly as shown below:
            call_tool('tool_name', {{'namespace': 'your-namespace'}})
            
            Available tools:
            - pods_list_in_namespace: List all pods in a specific namespace
            - pods_get: Get details about a specific pod
            - pods_log: Get logs from a specific pod
            - namespaces_list: List all available namespaces
            - events_list: List all events in the cluster
            - configuration_view: View the current kubeconfig
            
            Current time: {current_time_str}
            
            Examples:
            - To list pods in a namespace: call_tool('pods_list_in_namespace', {{'namespace': 'your-namespace'}})
            - To get pod details: call_tool('pods_get', {{'namespace': 'your-namespace', 'name': 'pod-name'}})
            - To get pod logs: call_tool('pods_log', {{'namespace': 'your-namespace', 'name': 'pod-name'}})
            - To list namespaces: call_tool('namespaces_list', {{}})
            - To list events: call_tool('events_list', {{}})
            """
            
            # Format the user's message
            full_prompt = f"{system_prompt}\n\nUser: {message}\nAssistant:"
            
            try:
                # Generate response with function calling explicitly disabled
                response = await self.gemini_model.generate_content_async(
                    full_prompt,
                    generation_config={
                        "temperature": 0.2,
                        "top_p": 0.8,
                        "top_k": 40,
                        "max_output_tokens": 2048,
                    },
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    ]
                )
                
                # Extract text from response safely
                response_text = ""
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'candidates'):
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            parts = [part.text for part in candidate.content.parts if hasattr(part, 'text')]
                            if parts:
                                response_text = ' '.join(parts)
                                break
                
                if not response_text:
                    response_text = "I'm not sure how to respond to that. Could you please rephrase your question?"
                    
            except Exception as e:
                logger.error(f"Error generating response: {e}", exc_info=True)
                response_text = "I encountered an error while processing your request. Please try again."
            
            # Handle tool calls using simple pattern matching
            if "call_tool(" in response_text:
                response_text = await self._handle_tool_calls_in_response(response_text)
                
                # After tool execution, enhance the overall response
                response_text = await self._enhance_final_response(message, response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_details = f"Error type: {type(e).__name__}, Message: {str(e)}"
            logger.error(f"Full error details: {error_details}")
            return f"I apologize, but I encountered an error while processing your request: {error_details}"
            
    async def _enhance_final_response(self, user_message: str, response_with_tools: str) -> str:
        """Enhance the final response after tool execution."""
        try:
            enhancement_prompt = f"""You are an expert Kubernetes/OpenShift assistant. A user asked a question and tools were executed to gather information. Please provide a final, polished response.

User's original question: {user_message}

Response with tool results: {response_with_tools}

Please provide a final response that:
1. Directly answers the user's question
2. Summarizes key findings from the tool results
3. Provides actionable insights or recommendations if appropriate
4. Uses clear, professional language
5. Maintains the technical accuracy while being accessible

Keep it conversational and helpful. Don't repeat "Enhanced with AI analysis" tags.

Final response:"""

            response = await self.gemini_model.generate_content_async(enhancement_prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Failed to enhance final response: {e}")
            return response_with_tools  # Return original if enhancement fails
            
    def _convert_mcp_tools_to_gemini(self) -> list:
        """Convert MCP tools to Gemini function declarations."""
        if not self.available_tools:
            return []
            
        gemini_functions = []
        for mcp_tool in self.available_tools:
            try:
                # Clean and convert the input schema
                schema = mcp_tool.inputSchema or {}
                cleaned_schema = self._clean_schema_for_gemini(schema)
                
                # Convert MCP tool schema to Gemini function declaration
                function_declaration = {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description or f"Execute {mcp_tool.name}",
                    "parameters": cleaned_schema
                }
                gemini_functions.append(function_declaration)
                
            except Exception as e:
                logger.warning(f"Failed to convert tool {mcp_tool.name}: {e}")
                continue
                
        logger.info(f"Converted {len(gemini_functions)} MCP tools to Gemini functions")
        
        # Debug: Log the converted functions
        for i, func in enumerate(gemini_functions):
            logger.debug(f"Function {i}: {func['name']}")
            logger.debug(f"  Parameters: {func['parameters']}")
            
        return gemini_functions
        
    def _clean_schema_for_gemini(self, schema: dict) -> dict:
        """Clean JSON schema to be compatible with Gemini function declarations."""
        if not schema or not isinstance(schema, dict):
            # Return minimal schema without explicit "object" type
            return {
                "properties": {},
                "required": []
            }
        
        # Create a clean copy - avoid "object" type entirely
        cleaned = {
            "properties": {},
            "required": []
        }
        
        # Handle properties
        if "properties" in schema and isinstance(schema["properties"], dict):
            for prop_name, prop_schema in schema["properties"].items():
                cleaned["properties"][prop_name] = self._clean_property_schema(prop_schema)
        
        # Handle required fields
        if "required" in schema and isinstance(schema["required"], list):
            cleaned["required"] = schema["required"]
            
        return cleaned
        
    def _clean_property_schema(self, prop_schema: dict) -> dict:
        """Clean individual property schema."""
        if not isinstance(prop_schema, dict):
            return {"type": "string"}
            
        cleaned = {}
        
        # Handle type - use only the most basic types that Gemini supports
        if "type" in prop_schema:
            prop_type = prop_schema["type"]
            if prop_type == "string":
                cleaned["type"] = "string"
            elif prop_type in ["number", "integer"]:
                cleaned["type"] = "number"  # Gemini uses "number" for both
            elif prop_type == "boolean":
                cleaned["type"] = "string"  # Convert boolean to string to avoid enum issues
            elif prop_type == "array":
                cleaned["type"] = "array"
            elif prop_type == "object":
                # For object types, just omit the type and use properties
                if "properties" in prop_schema:
                    cleaned["properties"] = {}
                    for nested_prop, nested_schema in prop_schema["properties"].items():
                        cleaned["properties"][nested_prop] = self._clean_property_schema(nested_schema)
                else:
                    cleaned["type"] = "string"  # Fallback
            else:
                cleaned["type"] = "string"  # Default fallback for unknown types
        else:
            cleaned["type"] = "string"
            
        # Handle description
        if "description" in prop_schema:
            cleaned["description"] = str(prop_schema["description"])
            
        # Handle items for arrays
        if cleaned.get("type") == "array" and "items" in prop_schema:
            cleaned["items"] = self._clean_property_schema(prop_schema["items"])
            
        return cleaned
        
    async def _format_tool_results_fallback(self, user_message: str, function_responses: list) -> str:
        """Fallback method to format tool results when Gemini function response fails."""
        try:
            result_text = f"I executed the following operations in response to: '{user_message}'\n\n"
            
            for fr in function_responses:
                tool_name = fr["name"]
                response_data = fr["response"]
                
                result_text += f"**{tool_name}:**\n"
                
                if "error" in response_data:
                    result_text += f"❌ Error: {response_data['error']}\n\n"
                elif "result" in response_data:
                    result_data = response_data["result"]
                    
                    # Format based on tool type
                    if "pods_list" in tool_name:
                        result_text += f"📦 **Pods Found:**\n```\n{result_data}\n```\n\n"
                    elif "namespaces_list" in tool_name:
                        result_text += f"🏷️ **Namespaces:**\n```\n{result_data}\n```\n\n"
                    elif "events_list" in tool_name:
                        result_text += f"📋 **Cluster Events:**\n```\n{result_data}\n```\n\n"
                    elif "log" in tool_name:
                        result_text += f"📄 **Logs:**\n```\n{result_data}\n```\n\n"
                    else:
                        result_text += f"```\n{result_data}\n```\n\n"
                else:
                    result_text += f"✅ Operation completed successfully\n\n"
            
            return result_text.strip()
            
        except Exception as e:
            logger.error(f"Error in fallback formatting: {e}")
            return f"I executed your request but encountered an issue formatting the response. The operation may have completed successfully."
            
    def _create_system_prompt(self) -> str:
        """Create system prompt with available tools and detailed documentation."""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Detailed tool documentation with examples and usage guidelines
        tools_docs = """## Kubernetes Tools Reference

### 1. Pod Management

#### pods_list
- **Description**: List all pods across all namespaces in the cluster.
- **Parameters**: None
- **Example**: 
  ```python
  call_tool('pods_list', {})
  ```

#### pods_list_in_namespace
- **Description**: List all pods in a specific namespace.
- **Parameters**: 
  - `namespace` (string, required): The namespace to list pods from.
- **Example**: 
  ```python
  call_tool('pods_list_in_namespace', {'namespace': 'kube-system'})
  ```

#### pods_get
- **Description**: Get detailed information about a specific pod.
- **Parameters**:
  - `namespace` (string, required): The namespace of the pod.
  - `name` (string, required): The name of the pod.
- **Example**:
  ```python
  call_tool('pods_get', {'namespace': 'default', 'name': 'my-pod'})
  ```

#### pods_log
- **Description**: Retrieve logs from a container in a pod.
- **Parameters**:
  - `namespace` (string, required): The namespace of the pod.
  - `name` (string, required): The name of the pod.
  - `container` (string, optional): The name of the container. Defaults to the first container if not specified.
  - `lines` (integer, optional): Number of lines to show from the end of the logs.
  - `follow` (boolean, optional): If true, the logs will be streamed. Defaults to false.
- **Example**:
  ```python
  call_tool('pods_log', {
      'namespace': 'default',
      'name': 'my-pod',
      'lines': 100,
      'container': 'main-app'
  })
  ```

#### pods_run
- **Description**: Create and run a pod with the specified image.
- **Parameters**:
  - `namespace` (string, required): The namespace to create the pod in.
  - `name` (string, required): The name of the pod.
  - `image` (string, required): The container image to run.
  - `command` (array, optional): The command to run in the container.
  - `args` (array, optional): Arguments to the command.
  - `env` (object, optional): Environment variables to set in the container.
- **Example**:
  ```python
  call_tool('pods_run', {
      'namespace': 'default',
      'name': 'test-nginx',
      'image': 'nginx:latest',
      'env': {'ENV_VAR': 'value'}
  })
  ```

#### pods_exec
- **Description**: Execute a command in a running container.
- **Parameters**:
  - `namespace` (string, required): The namespace of the pod.
  - `name` (string, required): The name of the pod.
  - `container` (string, optional): The container to run the command in. Defaults to the first container.
  - `command` (string, required): The command to execute.
  - `stdin` (boolean, optional): If true, forward stdin to the container. Defaults to false.
  - `tty` (boolean, optional): If true, allocate a TTY. Defaults to false.
- **Example**:
  ```python
  call_tool('pods_exec', {
      'namespace': 'default',
      'name': 'my-pod',
      'command': 'ls -la /app',
      'container': 'app-container'
  })
  ```

#### pods_delete
- **Description**: Delete a pod.
- **Parameters**:
  - `namespace` (string, required): The namespace of the pod to delete.
  - `name` (string, required): The name of the pod to delete.
- **Example**:
  ```python
  call_tool('pods_delete', {'namespace': 'default', 'name': 'old-pod'})
  ```

### 2. Generic Resource Management

#### resources_list
- **Description**: List resources of a specific type in a namespace.
- **Parameters**:
  - `apiVersion` (string, required): The API version of the resource.
  - `kind` (string, required): The kind of the resource (e.g., 'Pod', 'ConfigMap', 'Secret').
  - `namespace` (string, optional): The namespace to list resources from. Not needed for cluster-scoped resources.
- **Example**:
  ```python
  # List all ConfigMaps in default namespace
  call_tool('resources_list', {
      'apiVersion': 'v1',
      'kind': 'ConfigMap',
      'namespace': 'default'
  })
  ```

#### resources_get
- **Description**: Get a specific resource by name.
- **Parameters**:
  - `apiVersion` (string, required): The API version of the resource.
  - `kind` (string, required): The kind of the resource.
  - `namespace` (string, optional): The namespace of the resource. Not needed for cluster-scoped resources.
  - `name` (string, required): The name of the resource.
- **Example**:
  ```python
  call_tool('resources_get', {
      'apiVersion': 'v1',
      'kind': 'Secret',
      'namespace': 'default',
      'name': 'database-credentials'
  })
  ```

#### resources_create_or_update
- **Description**: Create or update a resource using a YAML or JSON definition.
- **Parameters**:
  - `yaml` (string, required): The YAML or JSON definition of the resource.
- **Example**:
  ```python
  call_tool('resources_create_or_update', {
      'yaml': '''
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: app-config
        namespace: default
      data:
        config.yaml: |
          database:
            host: db-service
            port: 5432
          logging:
            level: debug
      '''
  })
  ```

#### resources_delete
- **Description**: Delete a specific resource.
- **Parameters**:
  - `apiVersion` (string, required): The API version of the resource.
  - `kind` (string, required): The kind of the resource.
  - `namespace` (string, optional): The namespace of the resource.
  - `name` (string, required): The name of the resource to delete.
- **Example**:
  ```python
  call_tool('resources_delete', {
      'apiVersion': 'v1',
      'kind': 'ConfigMap',
      'namespace': 'default',
      'name': 'old-config'
  })
  ```

### 3. Cluster Management

#### namespaces_list
- **Description**: List all namespaces in the cluster.
- **Parameters**: None
- **Example**:
  ```python
  call_tool('namespaces_list', {})
  ```

#### events_list
- **Description**: List events from the cluster.
- **Parameters**:
  - `namespace` (string, optional): Filter events by namespace.
  - `field_selector` (string, optional): Filter events by field selector.
  - `limit` (integer, optional): Maximum number of events to return.
- **Example**:
  ```python
  # Get recent events from default namespace
  call_tool('events_list', {
      'namespace': 'default',
      'limit': 20
  })
  ```

#### configuration_view
- **Description**: View the current kubeconfig and cluster information.
- **Parameters**: None
- **Example**:
  ```python
  call_tool('configuration_view', {})
  ```

## Best Practices

1. **Namespace Awareness**:
   - Always specify the namespace when working with namespaced resources
   - Use `namespaces_list` to verify namespace existence

2. **Resource Management**:
   - Use `resources_list` to explore available resources
   - Check resource existence before creation
   - Use `resources_get` to verify resource details before updates

3. **Error Handling**:
   - Handle missing resources gracefully
   - Check for required parameters before making calls
   - Use field selectors to filter results when possible

4. **Security**:
   - Be cautious with resource deletion
   - Verify resource names before performing destructive operations
   - Use `--dry-run=server` when available to test changes

Current time: {current_time}
"""
        
        return f"""You are a helpful AI assistant with full access to a Kubernetes cluster through the MCP server.

{tools_docs}

When responding to user requests:
1. First determine which tool(s) are needed
2. Use the call_tool() format exactly as shown in the examples
3. If a tool call fails, try to understand why and correct your approach
4. Always be clear about what actions you're taking and why
5. When showing results, format them in a readable way
6. If you're not sure about something, use the appropriate tool to gather more information

Remember to be precise with namespaces and resource names. Always double-check your tool calls before executing them."""

    async def _handle_tool_calls_in_response(self, response_text: str) -> str:
        """Handle tool calls found in the response and enhance with LLM.
        
        Supports multiple tool call formats:
        1. call_tool('tool_name', {'param': 'value'})
        2. call_tool('tool_name', 'namespace')
        3. call_tool('tool_name', namespace='value')
        4. call_tool('tool_name', 'arg1', 'arg2')
        5. call_tool('tool_name')
        """
        if not self.mcp_client:
            return response_text
            
        import re
        import json
        from typing import Dict, Any, Optional
        
        async def execute_tool(tool_name: str, args: Dict[str, Any]) -> str:
            """Execute a tool and return the result as a formatted string."""
            try:
                logger.info(f"Executing tool: {tool_name} with args: {args}")
                
                # Special handling for resources_* tools
                if tool_name.startswith('resources_'):
                    if 'yaml' in args and isinstance(args['yaml'], str):
                        # Handle multi-line YAML in the arguments
                        args['yaml'] = args['yaml'].replace('\\n', '\n')
                
                # Execute the tool
                result = await self.mcp_client.call_tool(tool_name, args)
                
                # Format the result
                if hasattr(result, 'content'):
                    if isinstance(result.content, list):
                        content = '\n'.join([
                            str(item.text) if hasattr(item, 'text') else str(item) 
                            for item in result.content
                        ])
                    else:
                        content = str(result.content)
                else:
                    content = str(result)
                
                # Format the output
                output = f"""
### ✅ Tool Execution: {tool_name}
**Arguments:**
```json
{json.dumps(args, indent=2)}
```
**Result:**
```
{content}
```
"""
                return output
                
            except Exception as e:
                error_msg = f"Error executing {tool_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return f"❌ {error_msg}"
        
        # Pattern to match tool calls with different formats
        tool_patterns = [
            # Format: call_tool('tool_name', {'param': 'value'})
            (r'call_tool\([\'\"]([^\'\"]+)[\'\"]\s*,\s*({[^}]*})\)', 
             lambda m: (m.group(1), json.loads(m.group(2).replace("'", '"')))),
            
            # Format: call_tool('tool_name', 'namespace')
            (r'call_tool\([\'\"]([^\'\"]+)[\'\"]\s*,\s*[\'\"]([^\'\"]*)[\'\"]\)',
             lambda m: (m.group(1), {'namespace': m.group(2)})),
            
            # Format: call_tool('tool_name', namespace='value')
            (r'call_tool\([\'\"]([^\'\"]+)[\'\"]\s*,\s*namespace\s*=\s*[\'\"]([^\'\"]*)[\'\"]\)',
             lambda m: (m.group(1), {'namespace': m.group(2)})),
            
            # Format: call_tool('tool_name', 'arg1', 'arg2')
            (r'call_tool\([\'\"]([^\'\"]+)[\'\"]\s*,\s*[\'\"]([^\'\"]*)[\'\"]\s*,\s*[\'\"]([^\'\"]*)[\'\"]\)',
             lambda m: (m.group(1), {'arg1': m.group(2), 'arg2': m.group(3)})),
            
            # Format: call_tool('tool_name')
            (r'call_tool\([\'\"]([^\'\"]+)[\'\"]\)',
             lambda m: (m.group(1), {}))
        ]
        
        result_text = response_text
        
        # Process each pattern
        for pattern, args_processor in tool_patterns:
            for match in re.finditer(pattern, result_text):
                try:
                    full_match = match.group(0)
                    tool_name, args = args_processor(match)
                    
                    # Execute the tool
                    tool_result = await execute_tool(tool_name, args)
                    
                    # Replace the tool call with the result
                    result_text = result_text.replace(full_match, tool_result)
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON in tool arguments: {e}"
                    logger.error(error_msg)
                    result_text = result_text.replace(match.group(0), f"❌ {error_msg}")
                    
                except Exception as e:
                    error_msg = f"Error processing tool call: {e}"
                    logger.error(error_msg, exc_info=True)
                    result_text = result_text.replace(match.group(0), f"❌ {error_msg}")
                
            # Handle JSON processing for tool arguments
            try:
                # Clean up the JSON string by removing any trailing commas and fixing common issues
                json_str = match.group(2)
                # Remove trailing commas before closing braces/brackets
                json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
                # Fix single quotes to double quotes for JSON
                json_str = re.sub(r"'\s*:\s*'", '":"', json_str)  # keys and values with single quotes
                json_str = re.sub(r"'\s*,\s*'", '","', json_str)  # array values with single quotes
                json_str = re.sub(r"'\s*}", '"}', json_str)  # closing object with single quotes
                json_str = re.sub(r"{\s*'", '{"', json_str)  # opening object with single quotes
                
                arguments = json.loads(json_str)
                if not isinstance(arguments, dict):
                    arguments = {'value': arguments}
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON arguments for {tool_name}: {e}")
                # Try to extract just the namespace if it's a simple case
                namespace_match = re.search(r"namespace\s*[:=]\s*['\"]([^'\"]+)['\"]", match.group(2))
                if namespace_match:
                    arguments = {'namespace': namespace_match.group(1).strip()}
                else:
                    continue
            
            # Handle additional string arguments if present
            if len(match.groups()) >= 3 and match.group(3):
                if not isinstance(arguments, dict):
                    arguments = {}
                arguments['name'] = match.group(3).strip()
            
            # Special handling for specific tools
            if tool_name == 'pods_list_in_namespace' and not arguments.get('namespace'):
                # Default to a namespace if not provided
                arguments['namespace'] = 'default'
            
            logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")
            
            try:
                result = await self.mcp_client.call_tool(tool_name, arguments)
                
                # Extract raw result
                raw_result = ""
                if hasattr(result, 'content'):
                    if isinstance(result.content, list):
                        raw_result = "\n".join([str(item.text) if hasattr(item, 'text') else str(item) for item in result.content])
                    else:
                        raw_result = str(result.content)
                elif result is not None:
                    raw_result = str(result)
                else:
                    raw_result = f"Tool {tool_name} executed successfully"
                
                # Enhance the result with LLM
                enhanced_result = await self._enhance_tool_result(tool_name, arguments, raw_result)
                
                # Replace the tool call with the enhanced result
                result_text = result_text.replace(match.group(0), enhanced_result)
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                error_msg = f"I encountered an error while executing the {tool_name} tool: {str(e)}"
                result_text = result_text.replace(match.group(0), error_msg)
                
            except Exception as e:
                logger.error(f"Unexpected error processing tool call: {e}", exc_info=True)
                continue
        
        return result_text
        
    async def cleanup(self) -> None:
        """Clean up resources used by the agent."""
        try:
            if self.mcp_client:
                await self.mcp_client.disconnect()
                logger.info("Disconnected from MCP server")
            if hasattr(self, 'gemini_model'):
                # Clean up any Gemini model resources if needed
                pass
            logger.info("Agent cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            
    async def _enhance_tool_result(self, tool_name: str, arguments: Dict[str, Any], raw_result: str) -> str:
        """Use LLM to enhance and format tool results."""
        try:
            enhancement_prompt = f"""You are helping to present Kubernetes/OpenShift cluster information in a user-friendly way.

Tool executed: {tool_name}
Arguments: {json.dumps(arguments, indent=2)}
Raw result from MCP server:
{raw_result}

Please format this information in a clear, conversational way that:
1. Explains what the tool did
2. Presents the data in an organized, readable format
3. Adds helpful context or insights about the Kubernetes resources
4. Uses proper formatting (bullet points, tables, etc.)
5. Keeps it concise but informative

Response:"""

            response = await self.gemini_model.generate_content_async(enhancement_prompt)
            enhanced_text = response.text.strip()
            
            # Add a subtle indicator that this was enhanced
            return f"{enhanced_text}\n\n*✨ Enhanced with AI analysis*"
            
        except Exception as e:
            logger.error(f"Failed to enhance tool result: {e}")
            # Fallback to basic formatting
            return self._basic_format_result(tool_name, arguments, raw_result)
            
    def _basic_format_result(self, tool_name: str, arguments: Dict[str, Any], raw_result: str) -> str:
        """Basic formatting fallback when LLM enhancement fails."""
        namespace = arguments.get('namespace', 'default')
        
        if tool_name == "list_pods":
            return f"📦 **Pods in namespace '{namespace}':**\n{raw_result}"
        elif tool_name == "list_services":
            return f"🌐 **Services in namespace '{namespace}':**\n{raw_result}"
        elif tool_name == "list_deployments":
            return f"🚀 **Deployments in namespace '{namespace}':**\n{raw_result}"
        elif tool_name == "get_pod_logs":
            pod_name = arguments.get('pod_name', 'unknown')
            return f"📋 **Logs for pod '{pod_name}':**\n```\n{raw_result}\n```"
        else:
            return f"🔧 **{tool_name} result:**\n{raw_result}"
            
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        if not self.mcp_client:
            return []
            
        tools = []
        for mcp_tool in self.available_tools:
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

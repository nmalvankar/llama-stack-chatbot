"""FastAPI backend for the Llama Stack Chatbot."""

import asyncio
import logging
from typing import Dict, List
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import settings
from .simple_agent import SimpleLlamaStackAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Llama Stack Chatbot",
    description="A chatbot powered by Llama Stack, Google Gemini, and MCP tools",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent: SimpleLlamaStackAgent = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"


class ToolInfo(BaseModel):
    name: str
    description: str
    schema: Dict


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup."""
    global agent
    try:
        agent = SimpleLlamaStackAgent()
        await agent.initialize()
        logger.info("Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global agent
    if agent:
        await agent.cleanup()


@app.get("/")
async def get_index():
    """Serve the main chat interface."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Llama Stack Chatbot</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            
            .chat-container {
                width: 90%;
                max-width: 800px;
                height: 80vh;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            
            .chat-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }
            
            .chat-header h1 {
                font-size: 24px;
                font-weight: 600;
            }
            
            .chat-header p {
                opacity: 0.9;
                margin-top: 5px;
            }
            
            .chat-messages {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                background: #f8f9fa;
            }
            
            .message {
                margin-bottom: 15px;
                display: flex;
                align-items: flex-start;
            }
            
            .message.user {
                justify-content: flex-end;
            }
            
            .message-content {
                max-width: 70%;
                padding: 12px 16px;
                border-radius: 18px;
                word-wrap: break-word;
            }
            
            .message.user .message-content {
                background: #007bff;
                color: white;
            }
            
            .message.bot .message-content {
                background: white;
                color: #333;
                border: 1px solid #e9ecef;
            }
            
            .chat-input {
                padding: 20px;
                background: white;
                border-top: 1px solid #e9ecef;
                display: flex;
                gap: 10px;
            }
            
            .chat-input input {
                flex: 1;
                padding: 12px 16px;
                border: 1px solid #ddd;
                border-radius: 25px;
                outline: none;
                font-size: 16px;
            }
            
            .chat-input input:focus {
                border-color: #007bff;
            }
            
            .chat-input button {
                padding: 12px 24px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 500;
            }
            
            .chat-input button:hover {
                background: #0056b3;
            }
            
            .chat-input button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            
            .typing-indicator {
                display: none;
                padding: 10px 16px;
                background: white;
                border-radius: 18px;
                border: 1px solid #e9ecef;
                max-width: 70%;
            }
            
            .typing-dots {
                display: flex;
                gap: 4px;
            }
            
            .typing-dots span {
                width: 8px;
                height: 8px;
                background: #999;
                border-radius: 50%;
                animation: typing 1.4s infinite ease-in-out;
            }
            
            .typing-dots span:nth-child(2) {
                animation-delay: 0.2s;
            }
            
            .typing-dots span:nth-child(3) {
                animation-delay: 0.4s;
            }
            
            @keyframes typing {
                0%, 60%, 100% {
                    transform: translateY(0);
                }
                30% {
                    transform: translateY(-10px);
                }
            }
            
            .connection-status {
                padding: 10px;
                text-align: center;
                font-size: 14px;
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
            
            .connection-status.connected {
                background: #d4edda;
                color: #155724;
            }
            
            .connection-status.disconnected {
                background: #f8d7da;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="chat-header">
                <h1>🤖 Llama Stack Chatbot</h1>
                <p>Powered by Google Gemini & MCP Tools</p>
            </div>
            
            <div class="connection-status" id="connectionStatus">
                Connecting...
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message bot">
                    <div class="message-content">
                        Hello! I'm your AI assistant powered by Llama Stack and Google Gemini. I have access to various tools through MCP. How can I help you today?
                    </div>
                </div>
            </div>
            
            <div class="typing-indicator" id="typingIndicator">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            
            <div class="chat-input">
                <input type="text" id="messageInput" placeholder="Type your message..." disabled>
                <button id="sendButton" disabled>Send</button>
            </div>
        </div>

        <script>
            class ChatBot {
                constructor() {
                    this.ws = null;
                    this.messageInput = document.getElementById('messageInput');
                    this.sendButton = document.getElementById('sendButton');
                    this.chatMessages = document.getElementById('chatMessages');
                    this.connectionStatus = document.getElementById('connectionStatus');
                    this.typingIndicator = document.getElementById('typingIndicator');
                    
                    this.init();
                }
                
                init() {
                    this.connect();
                    this.setupEventListeners();
                }
                
                connect() {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${protocol}//${window.location.host}/ws`;
                    
                    this.ws = new WebSocket(wsUrl);
                    
                    this.ws.onopen = () => {
                        this.updateConnectionStatus('connected', 'Connected');
                        this.messageInput.disabled = false;
                        this.sendButton.disabled = false;
                    };
                    
                    this.ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    };
                    
                    this.ws.onclose = () => {
                        this.updateConnectionStatus('disconnected', 'Disconnected');
                        this.messageInput.disabled = true;
                        this.sendButton.disabled = true;
                        
                        // Attempt to reconnect after 3 seconds
                        setTimeout(() => this.connect(), 3000);
                    };
                    
                    this.ws.onerror = (error) => {
                        console.error('WebSocket error:', error);
                        this.updateConnectionStatus('disconnected', 'Connection Error');
                    };
                }
                
                setupEventListeners() {
                    this.sendButton.addEventListener('click', () => this.sendMessage());
                    
                    this.messageInput.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            this.sendMessage();
                        }
                    });
                }
                
                sendMessage() {
                    const message = this.messageInput.value.trim();
                    if (!message || this.ws.readyState !== WebSocket.OPEN) return;
                    
                    // Add user message to chat
                    this.addMessage(message, 'user');
                    
                    // Send message to server
                    this.ws.send(JSON.stringify({
                        type: 'message',
                        content: message
                    }));
                    
                    // Clear input and show typing indicator
                    this.messageInput.value = '';
                    this.showTypingIndicator();
                }
                
                handleMessage(data) {
                    switch (data.type) {
                        case 'message_start':
                            this.hideTypingIndicator();
                            this.currentBotMessage = this.addMessage('', 'bot');
                            break;
                            
                        case 'message_chunk':
                            if (this.currentBotMessage) {
                                this.currentBotMessage.textContent += data.content;
                                this.scrollToBottom();
                            }
                            break;
                            
                        case 'message_end':
                            this.currentBotMessage = null;
                            break;
                            
                        case 'error':
                            this.hideTypingIndicator();
                            this.addMessage(`Error: ${data.content}`, 'bot');
                            break;
                    }
                }
                
                addMessage(content, sender) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${sender}`;
                    
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content';
                    contentDiv.textContent = content;
                    
                    messageDiv.appendChild(contentDiv);
                    this.chatMessages.appendChild(messageDiv);
                    
                    this.scrollToBottom();
                    return contentDiv;
                }
                
                showTypingIndicator() {
                    this.typingIndicator.style.display = 'block';
                    this.scrollToBottom();
                }
                
                hideTypingIndicator() {
                    this.typingIndicator.style.display = 'none';
                }
                
                updateConnectionStatus(status, message) {
                    this.connectionStatus.className = `connection-status ${status}`;
                    this.connectionStatus.textContent = message;
                }
                
                scrollToBottom() {
                    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
                }
            }
            
            // Initialize the chatbot when the page loads
            document.addEventListener('DOMContentLoaded', () => {
                new ChatBot();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_message = message_data.get("content", "")
                
                # Send message start indicator
                await manager.send_personal_message(
                    json.dumps({"type": "message_start"}),
                    websocket
                )
                
                # Get response from agent
                try:
                    # Send initial processing message
                    await manager.send_personal_message(
                        json.dumps({"type": "message_chunk", "content": "Please wait while I process your request...\n\n"}),
                        websocket
                    )
                    
                    response = await agent.chat(user_message)
                    
                    # Clear the initial message by sending an empty chunk
                    await manager.send_personal_message(
                        json.dumps({"type": "message_chunk", "content": ""}),
                        websocket
                    )
                    
                    # Send response as chunks for better UX
                    words = response.split()
                    for i in range(0, len(words), 5):  # Send 5 words at a time
                        chunk = " ".join(words[i:i+5]) + " "
                        await manager.send_personal_message(
                            json.dumps({"type": "message_chunk", "content": chunk}),
                            websocket
                        )
                        
                    # Send message end indicator
                    await manager.send_personal_message(
                        json.dumps({"type": "message_end"}),
                        websocket
                    )
                    
                except Exception as e:
                    logger.error(f"Error in chat: {e}", exc_info=True)
                    error_details = f"Error type: {type(e).__name__}, Message: {str(e)}"
                    logger.error(f"Full WebSocket error details: {error_details}")
                    await manager.send_personal_message(
                        json.dumps({"type": "error", "content": error_details}),
                        websocket
                    )
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/api/tools", response_model=List[ToolInfo])
async def get_tools():
    """Get available tools from the MCP server."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
        
    try:
        tools = await agent.get_available_tools()
        return [ToolInfo(**tool) for tool in tools]
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "timestamp": asyncio.get_event_loop().time()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

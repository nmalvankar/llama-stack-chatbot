# Simple Llama Stack Chatbot

A simplified chatbot that integrates **Google Gemini** with **remote Kubernetes MCP server** using **SSE (Server-Sent Events)** for tool calling. Deployable to **OpenShift**.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Google API Key for Gemini
- Remote MCP server running in Kubernetes with SSE endpoint

### 1. Setup
```bash
git clone <repo-url>
cd llama-stack-chatbot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your values:
# GOOGLE_API_KEY=your_google_api_key
# MCP_ENDPOINT=http://your-k8s-mcp-server:8080/sse
```

### 3. Run
```bash
python main.py
```

### 4. Access
Open `http://localhost:8000` in your browser

## 🏗️ Architecture

```
Browser ←→ FastAPI ←→ Google Gemini ←→ MCP Tools (K8s/SSE)
```

## 🐳 Docker

```bash
docker build -t simple-chatbot .
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY="your_key" \
  -e MCP_ENDPOINT="http://your-server:8080/sse" \
  simple-chatbot
```

## ☁️ OpenShift Deployment

1. **Update configuration**:
   ```bash
   # Edit openshift/configmap.yaml with your MCP endpoint
   # Edit openshift/secret.yaml with your Google API key (base64 encoded)
   ```

2. **Deploy**:
   ```bash
   oc new-project simple-chatbot
   oc apply -f openshift/
   ```

## 🔧 Key Features

- **Simple Architecture**: Direct Google Gemini integration
- **SSE Connection**: Uses Server-Sent Events for MCP server communication
- **Tool Calling**: Automatic tool detection and execution
- **Real-time Chat**: WebSocket-based chat interface
- **OpenShift Ready**: Complete deployment manifests

## 📁 Project Structure

```
├── src/
│   ├── simple_agent.py    # Main agent with Gemini + MCP
│   ├── mcp_client.py      # SSE-based MCP client
│   ├── api.py             # FastAPI backend + UI
│   └── config.py          # Configuration
├── openshift/             # OpenShift deployment files
├── main.py                # Entry point
└── requirements.txt       # Dependencies
```

## 🛠️ How It Works

1. **Agent**: Uses Google Gemini directly for chat responses
2. **Tool Detection**: Parses responses for `call_tool()` patterns
3. **MCP Integration**: Connects to remote MCP server via SSE
4. **Tool Execution**: Calls MCP tools and includes results in response

## 🔍 Example Usage

User: "What tools are available?"
Agent: "I have access to the following tools: [lists MCP tools]"

User: "Use the weather tool to get weather for New York"
Agent: "I'll check the weather for you. call_tool(weather, {"location": "New York"})"
→ Executes MCP tool and returns result

## 🚨 Troubleshooting

- **Connection issues**: Verify MCP endpoint is accessible
- **Tool errors**: Check MCP server logs
- **Authentication**: Ensure API keys are correct

This simplified version focuses on core functionality while maintaining deployment capabilities for OpenShift.

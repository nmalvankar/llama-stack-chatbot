# Quick Start Guide

Get your Llama Stack Chatbot running in 5 minutes!

## 🚀 Prerequisites

1. **Python 3.11+** installed
2. **Google API Key** for Gemini ([Get one here](https://ai.google.dev/))
3. **MCP Server** running and accessible

## ⚡ Quick Setup

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd llama-stack-chatbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
GOOGLE_API_KEY=your_google_api_key_here
MCP_ENDPOINT=ws://your-mcp-server:8080/mcp
MCP_AUTH_TOKEN=optional_token
```

### 3. Run the Application
```bash
python main.py
```

### 4. Open Your Browser
Navigate to: `http://localhost:8000`

## 🐳 Docker Quick Start

```bash
# Build
docker build -t llama-stack-chatbot .

# Run
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY="your_api_key" \
  -e MCP_ENDPOINT="ws://your-mcp-server:8080/mcp" \
  llama-stack-chatbot
```

## 🔧 Development Mode

```bash
# Install dev dependencies
pip install -r dev-requirements.txt

# Use the dev script
python scripts/dev.py dev
```

## 🧪 Test Your Setup

1. **Health Check**: `curl http://localhost:8000/api/health`
2. **Available Tools**: `curl http://localhost:8000/api/tools`
3. **Chat Interface**: Open `http://localhost:8000` in your browser

## 🆘 Troubleshooting

### Common Issues:

**"Agent initialization failed"**
- Check your Google API key
- Verify MCP server is running and accessible

**"WebSocket connection failed"**
- Check firewall settings
- Verify the server is running on the correct port

**"No tools available"**
- Verify MCP server endpoint
- Check authentication token if required

### Get Help:
- Check the full [README.md](README.md) for detailed documentation
- Review logs for specific error messages
- Ensure all environment variables are set correctly

## 🎉 You're Ready!

Your chatbot should now be running with:
- ✅ Google Gemini LLM integration
- ✅ MCP tool calling capabilities  
- ✅ Real-time web interface
- ✅ Health monitoring

Start chatting and explore the available tools!

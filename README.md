# Llama Stack Chatbot

A modern, browser-based chatbot powered by **Llama Stack**, **Google Gemini LLM**, and **MCP (Model Context Protocol)** tools. This application provides a real-time chat interface with tool calling capabilities and can be deployed to OpenShift.

## 🚀 Features

- **Llama Stack Integration**: Uses Llama Stack for agent orchestration
- **Google Gemini LLM**: Powered by Google's advanced Gemini model
- **MCP Tool Integration**: Connects to remote MCP servers for tool calling
- **Real-time Chat**: WebSocket-based chat interface
- **Modern UI**: Clean, responsive web interface
- **OpenShift Ready**: Complete deployment configuration for OpenShift
- **Health Monitoring**: Built-in health checks and monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│  FastAPI Server │◄──►│  Llama Stack    │
│   (Chat UI)     │    │   (WebSocket)   │    │    Agent        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                │                        ▼
                                │               ┌─────────────────┐
                                │               │  Google Gemini  │
                                │               │      LLM        │
                                │               └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   MCP Server    │
                       │  (K8s Remote)   │
                       └─────────────────┘
```

## 📋 Prerequisites

- Python 3.11+
- Google API Key (for Gemini)
- Access to a remote MCP server
- Docker (for containerization)
- OpenShift CLI (for deployment)

## 🛠️ Installation

### Local Development

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd llama-stack-chatbot
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up environment variables**:
   ```bash
   # Required
   export GOOGLE_API_KEY="your_google_api_key"
   export MCP_ENDPOINT="ws://your-k8s-mcp-server:8080/mcp"
   
   # Optional
   export MCP_AUTH_TOKEN="your_mcp_auth_token"
   export LLAMA_STACK_ENDPOINT="http://localhost:5001"
   ```

6. **Run the application**:
   ```bash
   python main.py
   ```

7. **Access the chatbot**:
   Open your browser and navigate to `http://localhost:8000`

## 🐳 Docker Deployment

### Build the Docker image:
```bash
docker build -t llama-stack-chatbot .
```

### Run with Docker:
```bash
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY="your_api_key" \
  -e MCP_ENDPOINT="ws://your-mcp-server:8080/mcp" \
  llama-stack-chatbot
```

## ☁️ OpenShift Deployment

### Prerequisites
- OpenShift cluster access
- `oc` CLI tool installed and configured

### Deployment Steps

1. **Create a new project**:
   ```bash
   oc new-project llama-stack-chatbot
   ```

2. **Update configuration**:
   Edit `openshift/configmap.yaml` and `openshift/secret.yaml` with your values:
   
   ```bash
   # Encode your secrets
   echo -n "your-google-api-key" | base64
   echo -n "your-mcp-auth-token" | base64
   ```

3. **Apply the manifests**:
   ```bash
   # Apply in order
   oc apply -f openshift/configmap.yaml
   oc apply -f openshift/secret.yaml
   oc apply -f openshift/imagestream.yaml
   oc apply -f openshift/buildconfig.yaml
   oc apply -f openshift/deployment.yaml
   oc apply -f openshift/service.yaml
   oc apply -f openshift/route.yaml
   ```

4. **Start the build**:
   ```bash
   oc start-build llama-stack-chatbot-build
   ```

5. **Monitor the deployment**:
   ```bash
   oc get pods -w
   oc logs -f deployment/llama-stack-chatbot
   ```

6. **Get the route URL**:
   ```bash
   oc get route llama-stack-chatbot-route
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key | Yes | - |
| `MCP_ENDPOINT` | MCP server WebSocket endpoint | Yes | - |
| `MCP_AUTH_TOKEN` | MCP server authentication token | No | - |
| `LLAMA_STACK_ENDPOINT` | Llama Stack server endpoint | No | `http://localhost:5001` |
| `LLAMA_STACK_API_KEY` | Llama Stack API key | No | - |
| `HOST` | Server host | No | `0.0.0.0` |
| `PORT` | Server port | No | `8000` |
| `DEBUG` | Enable debug mode | No | `false` |
| `CORS_ORIGINS` | Allowed CORS origins | No | `http://localhost:3000,http://localhost:8000` |

### MCP Server Configuration

The application connects to a remote MCP server running in Kubernetes. Ensure your MCP server:

- Exposes a WebSocket endpoint (e.g., `ws://your-server:8080/mcp`)
- Implements the MCP protocol correctly
- Has the necessary tools configured
- Is accessible from your deployment environment

## 🔧 API Endpoints

- `GET /` - Main chat interface
- `WebSocket /ws` - Real-time chat WebSocket
- `GET /api/tools` - List available MCP tools
- `GET /api/health` - Health check endpoint

## 🧪 Testing

### Test the health endpoint:
```bash
curl http://localhost:8000/api/health
```

### Test tool availability:
```bash
curl http://localhost:8000/api/tools
```

### WebSocket testing:
Use a WebSocket client to connect to `ws://localhost:8000/ws` and send:
```json
{
  "type": "message",
  "content": "Hello, how can you help me?"
}
```

## 📊 Monitoring

### Health Checks
The application provides health checks at `/api/health` that return:
- Application status
- Agent initialization status
- Timestamp

### Logs
The application uses structured logging. Key log events include:
- Agent initialization
- MCP server connection status
- Tool execution
- WebSocket connections
- Errors and exceptions

### OpenShift Monitoring
The deployment includes:
- Liveness probes
- Readiness probes
- Resource limits and requests
- Automatic restarts on failure

## 🔒 Security Considerations

1. **API Keys**: Store sensitive keys in OpenShift secrets
2. **CORS**: Configure appropriate CORS origins
3. **Authentication**: Consider adding authentication for production
4. **Network Policies**: Implement network policies in OpenShift
5. **TLS**: Use HTTPS/WSS in production (configured in route)

## 🐛 Troubleshooting

### Common Issues

1. **Agent initialization fails**:
   - Check Google API key validity
   - Verify MCP server accessibility
   - Check network connectivity

2. **WebSocket connection issues**:
   - Verify CORS configuration
   - Check firewall settings
   - Ensure WebSocket support in proxy/load balancer

3. **Tool calling failures**:
   - Verify MCP server is running
   - Check authentication tokens
   - Review MCP server logs

### Debug Mode
Enable debug mode by setting `DEBUG=true` for detailed logging.

### Logs
Check application logs:
```bash
# Local
python main.py

# Docker
docker logs <container-id>

# OpenShift
oc logs -f deployment/llama-stack-chatbot
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Llama Stack](https://github.com/meta-llama/llama-stack) - Agent orchestration
- [Google Gemini](https://ai.google.dev/) - Large Language Model
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift) - Container platform

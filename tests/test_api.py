"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.api import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_agent():
    """Mock agent for testing."""
    agent = AsyncMock()
    agent.get_available_tools.return_value = [
        {
            "name": "test_tool",
            "description": "A test tool",
            "schema": {"type": "object", "properties": {}}
        }
    ]
    return agent


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data


def test_index_page(client):
    """Test the main index page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Llama Stack Chatbot" in response.text


@patch('src.api.agent')
def test_tools_endpoint(mock_agent_instance, client):
    """Test the tools endpoint."""
    mock_agent_instance.get_available_tools.return_value = [
        {
            "name": "test_tool",
            "description": "A test tool",
            "schema": {"type": "object"}
        }
    ]
    
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test_tool"


def test_websocket_connection(client):
    """Test WebSocket connection."""
    with client.websocket_connect("/ws") as websocket:
        # Connection should be established
        assert websocket is not None

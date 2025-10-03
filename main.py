#!/usr/bin/env python3
"""
Llama Stack Chatbot - Main Entry Point

A chatbot powered by Llama Stack, Google Gemini, and MCP tools with a web interface.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the chatbot application."""
    try:
        import uvicorn
        from src.api import app
        
        logger.info("Starting Simple Llama Stack Chatbot...")
        logger.info(f"Server will run on {settings.host}:{settings.port}")
        logger.info(f"MCP Endpoint: {settings.mcp_endpoint}")
        
        # Run the FastAPI application
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level="info" if settings.debug else "warning",
            reload=settings.debug
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

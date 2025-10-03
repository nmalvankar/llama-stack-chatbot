"""Configuration management for the Llama Stack Chatbot."""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Google Gemini Configuration
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    
    # MCP Server Configuration
    mcp_endpoint: str = Field(..., env="MCP_ENDPOINT")
    mcp_auth_token: Optional[str] = Field(None, env="MCP_AUTH_TOKEN")
    
    
    # Application Configuration
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    debug: bool = Field(False, env="DEBUG")
    
    # CORS Configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        env="CORS_ORIGINS"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignore extra fields from .env file
    }
        
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()

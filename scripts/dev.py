#!/usr/bin/env python3
"""
Development script for the Llama Stack Chatbot.
Provides utilities for development, testing, and deployment.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_command(cmd: str, cwd: Path = PROJECT_ROOT) -> int:
    """Run a shell command and return the exit code."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    return result.returncode


def install_deps():
    """Install development dependencies."""
    return run_command("pip install -r dev-requirements.txt")


def format_code():
    """Format code using black and isort."""
    print("Formatting code...")
    run_command("black src/ main.py scripts/")
    run_command("isort src/ main.py scripts/")
    return 0


def lint_code():
    """Lint code using flake8 and mypy."""
    print("Linting code...")
    exit_code = 0
    exit_code |= run_command("flake8 src/ main.py")
    exit_code |= run_command("mypy src/ main.py --ignore-missing-imports")
    return exit_code


def test():
    """Run tests."""
    return run_command("pytest tests/ -v")


def dev_server():
    """Start development server with auto-reload."""
    return run_command("python main.py")


def build_docker():
    """Build Docker image."""
    return run_command("docker build -t llama-stack-chatbot .")


def run_docker():
    """Run Docker container locally."""
    cmd = """docker run -p 8000:8000 \
        -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
        -e MCP_ENDPOINT="${MCP_ENDPOINT}" \
        -e MCP_AUTH_TOKEN="${MCP_AUTH_TOKEN}" \
        llama-stack-chatbot"""
    return run_command(cmd)


def deploy_openshift():
    """Deploy to OpenShift."""
    print("Deploying to OpenShift...")
    commands = [
        "oc apply -f openshift/configmap.yaml",
        "oc apply -f openshift/secret.yaml", 
        "oc apply -f openshift/imagestream.yaml",
        "oc apply -f openshift/buildconfig.yaml",
        "oc apply -f openshift/deployment.yaml",
        "oc apply -f openshift/service.yaml",
        "oc apply -f openshift/route.yaml"
    ]
    
    for cmd in commands:
        if run_command(cmd) != 0:
            print(f"Failed to execute: {cmd}")
            return 1
    
    print("Starting build...")
    return run_command("oc start-build llama-stack-chatbot-build")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Development utilities for Llama Stack Chatbot")
    parser.add_argument("command", choices=[
        "install", "format", "lint", "test", "dev", 
        "build", "run-docker", "deploy"
    ], help="Command to run")
    
    args = parser.parse_args()
    
    commands = {
        "install": install_deps,
        "format": format_code,
        "lint": lint_code,
        "test": test,
        "dev": dev_server,
        "build": build_docker,
        "run-docker": run_docker,
        "deploy": deploy_openshift
    }
    
    exit_code = commands[args.command]()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

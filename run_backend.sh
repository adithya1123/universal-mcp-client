#!/bin/bash

# Universal MCP Client - Backend Startup Script

echo "🚀 Starting Universal MCP Client Backend..."
echo ""

# Set PYTHONPATH to current directory
export PYTHONPATH=.

# Run the FastAPI server
uv run python src/api/server.py

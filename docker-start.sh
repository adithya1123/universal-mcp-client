#!/bin/bash

# Universal MCP Client - Docker Startup Script

set -e

echo "🚀 Starting Universal MCP Client with Docker..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "📝 Please copy .env.example to .env and configure your settings"
    echo ""
    echo "  cp .env.example .env"
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker compose down

# Build images
echo "🔨 Building Docker images..."
docker compose build

# Start services
echo "▶️  Starting services..."
docker compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "✅ Universal MCP Client is running!"
echo ""
echo "📍 Access the application:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "📝 View logs:"
echo "   All services:  docker compose logs -f"
echo "   Backend only:  docker compose logs -f backend"
echo "   Frontend only: docker compose logs -f frontend"
echo ""
echo "🛑 To stop all services:"
echo "   docker compose down"
echo ""

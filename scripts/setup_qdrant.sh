#!/bin/bash

# Setup script for Qdrant vector database
# This script helps you get Qdrant up and running quickly

echo "========================================="
echo "Qdrant Vector Database Setup"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo ""
    echo "Please install Docker first:"
    echo "  - macOS: https://docs.docker.com/desktop/install/mac-install/"
    echo "  - Linux: https://docs.docker.com/engine/install/"
    echo "  - Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    exit 1
fi

echo "✓ Docker is installed"
echo ""

# Check if Qdrant container is already running
if docker ps | grep -q qdrant; then
    echo "⚠️  Qdrant container is already running"
    echo ""
    echo "To stop it:  docker stop qdrant"
    echo "To restart:  docker restart qdrant"
    echo ""
    exit 0
fi

# Check if Qdrant container exists but is stopped
if docker ps -a | grep -q qdrant; then
    echo "⚠️  Qdrant container exists but is stopped"
    echo "Starting existing container..."
    docker start qdrant
    echo ""
    echo "✓ Qdrant started successfully!"
    echo "Access at: http://localhost:6333"
    echo "Dashboard: http://localhost:6333/dashboard"
    echo ""
    exit 0
fi

# Pull and run Qdrant
echo "📦 Pulling Qdrant Docker image..."
docker pull qdrant/qdrant

echo ""
echo "🚀 Starting Qdrant container..."
docker run -d \
    --name qdrant \
    -p 6333:6333 \
    -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    qdrant/qdrant

echo ""
echo "========================================="
echo "✓ Qdrant Setup Complete!"
echo "========================================="
echo ""
echo "Qdrant is now running:"
echo "  - API endpoint: http://localhost:6333"
echo "  - Dashboard: http://localhost:6333/dashboard"
echo "  - Data stored in: ./qdrant_storage"
echo ""
echo "Useful commands:"
echo "  - View logs:     docker logs qdrant"
echo "  - Stop:          docker stop qdrant"
echo "  - Start:         docker start qdrant"
echo "  - Remove:        docker rm -f qdrant"
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies:"
echo "     pip install qdrant-client sentence-transformers"
echo ""
echo "  2. Run the example:"
echo "     python examples/vector_search_example.py"
echo ""

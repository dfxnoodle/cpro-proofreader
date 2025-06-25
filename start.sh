#!/bin/bash
# Quick start script for the styling guide proof-reader application

echo "🚀 Starting Styling Guide Proof-reader with uv..."
echo "📋 Make sure your .env file contains your Azure OpenAI credentials"
echo "🌐 The app will be available at http://localhost:8002"
echo ""

cd "$(dirname "$0")"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies if needed
echo "📦 Installing dependencies..."
uv sync

# Start the server
echo "🎯 Starting server on port 8002..."
uv run uvicorn main:app --host 0.0.0.0 --port 8002 --reload

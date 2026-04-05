#!/bin/bash
# Jarvis AI Assistant - Quick Deploy Script
# Usage: ./deploy.sh [local|ngrok|docker]

set -e

case "${1:-local}" in
    local)
        echo "Starting Jarvis locally..."
        echo "Dashboard: http://localhost:8000"
        echo "API Docs:  http://localhost:8000/docs"
        echo ""
        pip install -r requirements.txt -q
        python run_server.py
        ;;

    ngrok)
        echo "Starting Jarvis with ngrok tunnel..."
        echo "(Accessible from anywhere in the world)"
        echo ""

        # Check ngrok is installed
        if ! command -v ngrok &> /dev/null; then
            echo "ngrok not found. Install it:"
            echo "  brew install ngrok    (Mac)"
            echo "  snap install ngrok    (Linux)"
            echo "  Or download from https://ngrok.com/download"
            exit 1
        fi

        pip install -r requirements.txt -q

        # Start server in background
        python run_server.py &
        SERVER_PID=$!
        sleep 2

        echo "Server running (PID: $SERVER_PID)"
        echo "Starting ngrok tunnel..."
        echo ""
        ngrok http 8000

        # Cleanup
        kill $SERVER_PID 2>/dev/null
        ;;

    docker)
        echo "Starting Jarvis with Docker..."
        echo ""

        if ! command -v docker &> /dev/null; then
            echo "Docker not found. Install from https://docker.com"
            exit 1
        fi

        docker compose up --build
        ;;

    stop)
        echo "Stopping Jarvis..."
        docker compose down 2>/dev/null || true
        pkill -f "uvicorn.*jarvis" 2>/dev/null || true
        pkill -f "gunicorn.*jarvis" 2>/dev/null || true
        echo "Jarvis stopped."
        ;;

    *)
        echo "Usage: ./deploy.sh [local|ngrok|docker|stop]"
        echo ""
        echo "  local  - Run locally on http://localhost:8000 (default)"
        echo "  ngrok  - Run locally + expose via ngrok tunnel"
        echo "  docker - Run in Docker container"
        echo "  stop   - Stop all running instances"
        ;;
esac

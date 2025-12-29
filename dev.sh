#!/bin/bash

# Definition of colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper function for logging
log() {
    echo -e "${GREEN}[DEV]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function to kill background processes
cleanup() {
    log "Stopping services..."
    kill $(jobs -p) 2>/dev/null
    exit
}

# Trap SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

# Check for Docker (needed for sandbox-runner)
if ! command -v docker &> /dev/null || ! docker info &> /dev/null; then
    echo -e "${RED}[WARNING] Docker is not running or not installed.${NC}"
    echo -e "${RED}[WARNING] The 'sandbox-runner' image cannot be built.${NC}"
    echo -e "${RED}[WARNING] Code execution features will NOT work.${NC}"
    echo -e "${BLUE}[INFO] Continuing to start frontend and backend...${NC}"
else
    # Build Sandbox Runner Image
    log "Building sandbox-runner Docker image..."
    docker build -t sandbox-runner ./sandbox
    if [ $? -ne 0 ]; then
        error "Failed to build sandbox-runner image. Proceeding anyway..."
    else
        log "Sandbox image built successfully."
    fi
fi

# Start Backend
log "Starting Backend..."
cd backend
# Check if uv is installed
if ! command -v uv &> /dev/null; then
    error "uv not found. Please install uv (https://docs.astral.sh/uv/)."
    exit 1
fi

uv run uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
log "Starting Frontend..."
cd frontend
# Check if npm is installed
if ! command -v npm &> /dev/null; then
    error "npm not found. Please install Node.js/npm."
    kill $BACKEND_PID
    exit 1
fi

npm run dev &
FRONTEND_PID=$!
cd ..

log "Services are running!"
log "Backend: http://localhost:8000"
log "Frontend: http://localhost:5173"

# Wait for all background processes
wait

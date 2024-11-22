#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a process is running on a port
check_port() {
    lsof -i:$1 > /dev/null 2>&1
}

# Function to kill process on a port
kill_port() {
    if check_port $1; then
        echo -e "${YELLOW}Killing process on port $1...${NC}"
        fuser -k $1/tcp
        sleep 1
    fi
}

# Function to check if server is responding
check_server() {
    local max_attempts=10
    local attempt=1
    
    echo -e "${YELLOW}Waiting for server to start...${NC}"
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8080/health > /dev/null; then
            echo -e "${GREEN}Server started successfully${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    echo -e "\n${RED}Failed to start server after $max_attempts attempts${NC}"
    return 1
}

# Function to cleanup processes on exit
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    
    # Kill server process if running
    if [ ! -z "$SERVER_PID" ]; then
        echo -e "${YELLOW}Stopping HEOS Controller server...${NC}"
        kill $SERVER_PID 2>/dev/null || true
    fi
    
    # Kill any process on port 8080
    kill_port 8080
    
    # Deactivate virtual environment if active
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate || true
    fi
}

# Set up trap to cleanup on script exit
trap cleanup EXIT

echo -e "${GREEN}Starting HEOS Controller Backend...${NC}"

# Setup Python environment if needed
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creating new virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}Installing Python dependencies...${NC}"
    source venv/bin/activate
    pip install -U pip
    pip install -r requirements.txt
else
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Kill any existing process on port 8080
echo -e "${YELLOW}Ensuring port 8080 is free...${NC}"
kill_port 8080
sleep 2  # Give more time for port to be freed

# Start aiohttp server
echo -e "${GREEN}Starting HEOS Controller server...${NC}"
python3 aiohttp_server.py &
SERVER_PID=$!

# Wait for server to start
if ! check_server; then
    echo -e "${RED}Failed to start HEOS Controller server${NC}"
    exit 1
fi

echo -e "${GREEN}HEOS Controller server is running${NC}"

# Keep the script running
wait $SERVER_PID

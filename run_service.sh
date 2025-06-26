#!/bin/bash
# Wrapper script for systemd service

# Set the working directory
cd /media/dinochlai/Data/cpro-proofreader

# Load environment variables
source .env 2>/dev/null || echo "Warning: .env file not found or has issues"

# Export the environment variables for the child process
export AZURE_OPENAI_ENDPOINT
export AZURE_OPENAI_API_KEY

# Log some debug information
echo "$(date): Starting cpro-proofreader service" >> /tmp/cpro-proofreader.log
echo "$(date): Working directory: $(pwd)" >> /tmp/cpro-proofreader.log
echo "$(date): UV path: /home/dinochlai/.local/bin/uv" >> /tmp/cpro-proofreader.log
echo "$(date): Environment loaded" >> /tmp/cpro-proofreader.log

# Run the application
exec /home/dinochlai/.local/bin/uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8005

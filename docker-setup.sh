#!/bin/bash
# Setup script for Docker deployment of Email Filter

set -e

# Create config directory if it doesn't exist
mkdir -p config

# Copy Docker config template if it doesn't exist
if [ ! -f config/config.yaml ]; then
  echo "Creating config/config.yaml from template..."
  cp config/config.yaml.docker config/config.yaml
  echo "Please edit config/config.yaml to add your email accounts and OpenAI API key."
else
  echo "config/config.yaml already exists. Skipping..."
fi

# Build the Docker image
echo "Building Docker image..."
docker-compose build

echo ""
echo "Setup complete!"
echo ""
echo "To start the Email Filter daemon:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop the daemon:"
echo "  docker-compose down"
echo ""
echo "Don't forget to edit config/config.yaml with your email accounts and OpenAI API key!"

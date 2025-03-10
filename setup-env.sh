#!/usr/bin/env bash
# Helper script for setting up and troubleshooting the development environment

set -e # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Email Filter Environment Setup ===${NC}"

# Check if Nix is installed
if ! command -v nix &>/dev/null; then
  echo -e "${RED}Nix is not installed. Please install Nix first:${NC}"
  echo "sh <(curl -L https://nixos.org/nix/install) --daemon"
  exit 1
fi

# Check if direnv is installed
if ! command -v direnv &>/dev/null; then
  echo -e "${YELLOW}direnv is not installed. Installing with Nix...${NC}"
  nix-env -iA nixpkgs.direnv

  # Add direnv hook to shell config if not already present
  if [[ "$SHELL" == *"bash"* ]]; then
    if ! grep -q "direnv hook bash" ~/.bashrc; then
      echo 'eval "$(direnv hook bash)"' >>~/.bashrc
      echo -e "${GREEN}Added direnv hook to ~/.bashrc${NC}"
    fi
  elif [[ "$SHELL" == *"zsh"* ]]; then
    if ! grep -q "direnv hook zsh" ~/.zshrc; then
      echo 'eval "$(direnv hook zsh)"' >>~/.zshrc
      echo -e "${GREEN}Added direnv hook to ~/.zshrc${NC}"
    fi
  elif [[ "$SHELL" == *"fish"* ]]; then
    if ! grep -q "direnv hook fish" ~/.config/fish/config.fish 2>/dev/null; then
      mkdir -p ~/.config/fish
      echo 'direnv hook fish | source' >>~/.config/fish/config.fish
      echo -e "${GREEN}Added direnv hook to ~/.config/fish/config.fish${NC}"
    fi
  else
    echo -e "${YELLOW}Unknown shell: $SHELL. Please add direnv hook manually.${NC}"
  fi
fi

# Check if flakes are enabled
if ! nix flake --help &>/dev/null; then
  echo -e "${YELLOW}Nix flakes not enabled. Enabling...${NC}"
  mkdir -p ~/.config/nix
  echo "experimental-features = nix-command flakes" >>~/.config/nix/nix.conf
  echo -e "${GREEN}Enabled Nix flakes in ~/.config/nix/nix.conf${NC}"
  echo -e "${YELLOW}You may need to restart the Nix daemon for changes to take effect.${NC}"
fi

# Clean up any previous environment
echo -e "${BLUE}Cleaning up previous environment...${NC}"
rm -rf .direnv .venv

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
  echo -e "${YELLOW}Creating .env file...${NC}"
  cp .env.example .env
  echo -e "${GREEN}Created .env file. Please edit it to add your OpenAI API key.${NC}"
fi

# Allow direnv
echo -e "${BLUE}Allowing direnv...${NC}"
direnv allow

# Final instructions
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}If you're still having issues, try the following:${NC}"
echo "1. Restart your shell or terminal"
echo "2. Run 'direnv reload' in this directory"
echo "3. Check the Nix store for corruption: nix-store --verify --check-contents"
echo "4. Update the flake lock file: nix flake update"
echo -e "${BLUE}Happy coding!${NC}"

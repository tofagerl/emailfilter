{
  description = "Email Filter - A Python application for filtering and processing emails";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          # Allow unfree packages (if needed)
          config.allowUnfree = true;
        };

        # Use Python 3.11
        python = pkgs.python311;
        
        # Basic Python packages from nixpkgs
        pythonEnv = python.withPackages (ps: with ps; [
          # Development tools only - actual dependencies will be installed via pip
          pip
          setuptools
          wheel
          # venv is a built-in module in Python 3.3+, not a separate package
          pytest
          black
          isort
          mypy
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            # Add other system dependencies if needed
            pkgs.openssl
          ];

          shellHook = ''
            echo "📧 Email Filter development environment"
            
            # Create a virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              ${python}/bin/python -m venv .venv
            fi
            
            # Activate the virtual environment
            source .venv/bin/activate || {
              echo "Failed to activate virtual environment. Creating a new one..."
              rm -rf .venv
              ${python}/bin/python -m venv .venv
              source .venv/bin/activate
            }
            
            # Install the package in development mode with all dependencies
            if ! pip show mailmind &> /dev/null; then
              echo "Installing package in development mode..."
              pip install -e ".[dev]"
            fi
            
            # Set up environment variables
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
            
            # Show Python and pip versions
            python --version
            pip --version
            
            # Show OpenAI API key status
            if [ -n "$OPENAI_API_KEY" ]; then
              echo "OpenAI API key: Set ✓"
            else
              echo "OpenAI API key: Not set ✗"
            fi
          '';
        };
      }
    );
} 
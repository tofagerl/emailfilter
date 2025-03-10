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
        };

        # Use Python 3.11 instead of 3.10 for better package compatibility
        python = pkgs.python311;
        
        # Define Python packages explicitly to avoid compatibility issues
        pythonPackages = python.pkgs;
        
        # Create a Python environment with our dependencies
        pythonEnv = python.withPackages (ps: with ps; [
          # Core dependencies
          pyyaml
          imapclient
          (
            buildPythonPackage rec {
              pname = "openai";
              version = "1.12.0";  # Use a specific version that's known to work
              src = fetchPypi {
                inherit pname version;
                hash = "sha256-Yd+7ZZfYZpXBfG+Qf3XuLZ6Wt+Xk9BI9Y+ZHt+4Yvhk=";
              };
              doCheck = false;
              propagatedBuildInputs = [
                anyio
                distro
                httpx
                pydantic
                sniffio
                tqdm
                typing-extensions
              ];
            }
          )
          
          # Development dependencies
          pytest
          black
          isort
          mypy
          
          # Type checking
          types-pyyaml
          types-requests
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.uv  # Modern Python package installer
          ];

          shellHook = ''
            echo "Email Filter development environment"
            echo "Python: ${python.interpreter}"
            
            # Create a virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              ${pkgs.python311Packages.venv}/bin/python -m venv .venv
            fi
            
            # Activate the virtual environment
            source .venv/bin/activate || {
              echo "Failed to activate virtual environment. Creating a new one..."
              rm -rf .venv
              ${pkgs.python311Packages.venv}/bin/python -m venv .venv
              source .venv/bin/activate
            }
            
            # Install the package in development mode if not already installed
            if ! pip show emailfilter &> /dev/null; then
              echo "Installing package in development mode..."
              pip install -e . || echo "Warning: Failed to install package in development mode"
            fi
            
            # Set up environment variables
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
            
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
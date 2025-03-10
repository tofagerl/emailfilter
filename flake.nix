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

        pythonEnv = pkgs.python310.withPackages (ps: with ps; [
          # Core dependencies
          pyyaml
          imapclient
          openai
          
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
            echo "Python: ${pythonEnv.interpreter}"
            echo "OpenAI API key: $OPENAI_API_KEY"
            
            # Create a virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              ${pkgs.uv}/bin/uv venv
            fi
            
            # Activate the virtual environment
            source .venv/bin/activate
            
            # Install the package in development mode if not already installed
            if ! pip show emailfilter &> /dev/null; then
              echo "Installing package in development mode..."
              pip install -e ".[dev]"
            fi
            
            # Set up environment variables
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
          '';
        };
      }
    );
} 
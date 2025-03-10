# Nix Development Environment

This project includes a Nix flake for setting up a reproducible development environment. This ensures that all developers work with the same versions of dependencies, regardless of their host system.

## Quick Setup

For a quick and automated setup, you can use the provided setup script:

```bash
./setup-env.sh
```

This script will:

1. Check if Nix and direnv are installed (and install direnv if needed)
2. Enable Nix flakes if not already enabled
3. Clean up any previous environment
4. Create a `.env` file if it doesn't exist
5. Allow direnv to load the environment

## Manual Setup

### Prerequisites

1. Install [Nix](https://nixos.org/download.html) package manager:

   ```bash
   sh <(curl -L https://nixos.org/nix/install) --daemon
   ```

2. Enable [flakes](https://nixos.wiki/wiki/Flakes) by adding the following to your Nix configuration (`~/.config/nix/nix.conf` or `/etc/nix/nix.conf`):

   ```
   experimental-features = nix-command flakes
   ```

3. Install [direnv](https://direnv.net/) for automatically loading the environment:

   ```bash
   # On macOS with Homebrew
   brew install direnv

   # On NixOS or with Nix package manager
   nix-env -iA nixpkgs.direnv
   ```

4. Add direnv hook to your shell (add to `~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`):

   ```bash
   # For bash/zsh
   eval "$(direnv hook bash)"  # or zsh

   # For fish
   direnv hook fish | source
   ```

### First-time Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/emailfilter.git
   cd emailfilter
   ```

2. Allow direnv to load the environment:

   ```bash
   direnv allow
   ```

   This will automatically set up the development environment using Nix. The first time you run this, it may take several minutes as Nix downloads and builds all dependencies.

3. Create a `.env` file with your OpenAI API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

## How It Works

The Nix flake in this project uses a simplified approach:

1. It creates a minimal Python environment with only the essential development tools
2. It sets up a Python virtual environment using `venv`
3. It installs the project and its dependencies using `pip install -e ".[dev]"`

This approach combines the reproducibility of Nix with the flexibility of pip, making it easier to handle Python packages that might be difficult to package with Nix directly.

## Daily Development

Once set up, the environment will automatically load whenever you enter the project directory. The environment includes:

- Python 3.11 with essential development tools
- A Python virtual environment with all project dependencies
- Proper PYTHONPATH configuration

### Manual Usage (without direnv)

If you prefer not to use direnv, you can manually enter the development environment:

```bash
nix develop
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/test_categorizer.py
```

### Code Formatting

```bash
# Format code
black .
isort .

# Check types
mypy src/
```

## Troubleshooting

### Common Issues

- **"shell: command not found" error in .envrc**:
  This is usually caused by direnv not recognizing the shell directive. The file has been updated to use a shebang instead.

- **Python package compatibility issues**:
  The flake now uses a simplified approach that relies on pip for package installation, avoiding Nix packaging issues.

- **"error: propcache-X.X.X not supported for interpreter pythonX.X"**:
  This error should no longer occur with the simplified approach.

- **Virtual environment activation fails**:
  The shell hook now includes error handling to recreate the virtual environment if activation fails.

### General Troubleshooting Steps

1. **Run the setup script**:

   ```bash
   ./setup-env.sh
   ```

2. **Update the flake lock file**:

   ```bash
   nix flake update
   ```

3. **Reload the direnv environment**:

   ```bash
   direnv reload
   ```

4. **Clean up and rebuild manually**:

   ```bash
   rm -rf .direnv .venv
   direnv allow
   ```

5. **Check Nix store for corruption**:

   ```bash
   nix-store --verify --check-contents
   ```

6. **OpenAI API key not found**: Set it in your `.env` file or export it in your shell.

## Benefits of Using Nix

- **Reproducible**: Everyone gets the exact same development environment.
- **Isolated**: Dependencies don't interfere with your system packages.
- **Declarative**: All dependencies are explicitly defined in `flake.nix`.
- **Cross-platform**: Works on Linux, macOS, and WSL (Windows Subsystem for Linux).

## Advanced Configuration

### Customizing Python Packages

If you need to add or modify Python packages, edit the `install_requires` list in `setup.py`. For development-only packages, add them to the `extras_require["dev"]` list.

### Using a Different Python Version

To use a different Python version, change the `python = pkgs.pythonXXX` line in `flake.nix`, where `XXX` is the version (e.g., `311` for Python 3.11).

# Nix Development Environment

This project includes a Nix flake for setting up a reproducible development environment. This ensures that all developers work with the same versions of dependencies, regardless of their host system.

## Prerequisites

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

## Usage

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

   This will automatically set up the development environment using Nix.

3. Create a `.env` file with your OpenAI API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

### Daily Development

Once set up, the environment will automatically load whenever you enter the project directory. The environment includes:

- Python 3.10 with all required dependencies
- Development tools (pytest, black, isort, mypy)
- Virtual environment management with uv
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

- **Nix environment not loading**: Make sure you have allowed direnv with `direnv allow`.
- **Missing dependencies**: If you add new dependencies, update the `flake.nix` file.
- **OpenAI API key not found**: Set it in your `.env` file or export it in your shell.

## Benefits of Using Nix

- **Reproducible**: Everyone gets the exact same development environment.
- **Isolated**: Dependencies don't interfere with your system packages.
- **Declarative**: All dependencies are explicitly defined in `flake.nix`.
- **Cross-platform**: Works on Linux, macOS, and WSL (Windows Subsystem for Linux).

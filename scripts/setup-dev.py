#!/usr/bin/env python3
"""
Development environment setup script.

This script sets up the development environment by installing
pre-commit hooks and development dependencies.
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed:")
        print(f"  Command: {' '.join(command)}")
        print(f"  Error: {e.stderr}")
        return False


def main():
    """Main setup function."""
    print("Setting up OzBargain Deal Filter development environment...")
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("Error: pyproject.toml not found. Please run this script from the project root.")
        sys.exit(1)
    
    success = True
    
    # Install development dependencies
    success &= run_command(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        "Installing development dependencies"
    )
    
    # Install pre-commit hooks
    success &= run_command(
        [sys.executable, "-m", "pre_commit", "install"],
        "Installing pre-commit hooks"
    )
    
    # Run initial pre-commit check
    print("\nRunning initial pre-commit check...")
    run_command(
        [sys.executable, "-m", "pre_commit", "run", "--all-files"],
        "Initial pre-commit check"
    )
    
    if success:
        print("\n✅ Development environment setup completed successfully!")
        print("\nNext steps:")
        print("1. Run 'make test' to run the test suite")
        print("2. Run 'make quality-check' to run code quality checks")
        print("3. Start developing! Pre-commit hooks will run automatically on commit.")
    else:
        print("\n❌ Some setup steps failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
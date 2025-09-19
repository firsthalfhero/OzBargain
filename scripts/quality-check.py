#!/usr/bin/env python3
"""
Code quality check script.

This script runs all code quality checks including formatting,
linting, and type checking.
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print('='*60)
    
    try:
        result = subprocess.run(command, check=True)
        print(f"✓ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        return False


def main():
    """Main quality check function."""
    print("Running OzBargain Deal Filter code quality checks...")
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("Error: pyproject.toml not found. Please run this script from the project root.")
        sys.exit(1)
    
    checks = [
        ([sys.executable, "-m", "black", "--check", "ozb_deal_filter/", "tests/"], 
         "Code formatting check (black)"),
        ([sys.executable, "-m", "isort", "--check-only", "ozb_deal_filter/", "tests/"], 
         "Import sorting check (isort)"),
        ([sys.executable, "-m", "flake8", "ozb_deal_filter/", "tests/"], 
         "Linting check (flake8)"),
        ([sys.executable, "-m", "mypy", "ozb_deal_filter/"], 
         "Type checking (mypy)"),
    ]
    
    results = []
    for command, description in checks:
        success = run_command(command, description)
        results.append((description, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("QUALITY CHECK SUMMARY")
    print('='*60)
    
    all_passed = True
    for description, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{description:<40} {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All quality checks passed!")
        sys.exit(0)
    else:
        print(f"\n❌ Some quality checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
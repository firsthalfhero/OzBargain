#!/usr/bin/env python3
"""
Development environment setup script for OzBargain Deal Filter.

This script sets up the complete development environment including
dependencies, pre-commit hooks, and development tools.
"""

import subprocess
import sys
from pathlib import Path
import argparse
import os
from typing import List, Optional


class DevSetup:
    """Manages development environment setup."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_path = project_root / "venv"

    def run_command(self, command: List[str], description: str, check: bool = True) -> bool:
        """Run a command and return success status."""
        print(f"\n🔧 {description}...")
        print(f"Running: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                check=check
            )
            
            if result.returncode == 0:
                print(f"✅ {description} completed successfully")
                return True
            else:
                print(f"❌ {description} failed with exit code {result.returncode}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ {description} failed: {e}")
            return False
        except FileNotFoundError:
            print(f"❌ {description} failed - command not found")
            return False

    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        print("🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major == 3 and version.minor >= 11:
            print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
            return True
        else:
            print(f"❌ Python {version.major}.{version.minor}.{version.micro} is not compatible")
            print("Please install Python 3.11 or higher")
            return False

    def create_virtual_environment(self) -> bool:
        """Create a virtual environment if it doesn't exist."""
        if self.venv_path.exists():
            print(f"✅ Virtual environment already exists at {self.venv_path}")
            return True
        
        return self.run_command(
            [sys.executable, "-m", "venv", str(self.venv_path)],
            "Creating virtual environment"
        )

    def activate_virtual_environment(self) -> Optional[str]:
        """Get the activation command for the virtual environment."""
        if os.name == 'nt':  # Windows
            activate_script = self.venv_path / "Scripts" / "activate.bat"
            return str(activate_script)
        else:  # Unix-like
            activate_script = self.venv_path / "bin" / "activate"
            return f"source {activate_script}"

    def install_dependencies(self, dev: bool = True) -> bool:
        """Install project dependencies."""
        # Upgrade pip first
        pip_upgrade = self.run_command(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            "Upgrading pip"
        )
        
        if not pip_upgrade:
            return False
        
        # Install project dependencies
        if dev:
            install_cmd = [sys.executable, "-m", "pip", "install", "-e", ".[dev]"]
            description = "Installing development dependencies"
        else:
            install_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
            description = "Installing production dependencies"
        
        return self.run_command(install_cmd, description)

    def setup_pre_commit_hooks(self) -> bool:
        """Install and setup pre-commit hooks."""
        return self.run_command(
            ["pre-commit", "install"],
            "Installing pre-commit hooks"
        )

    def create_directories(self) -> bool:
        """Create necessary project directories."""
        directories = [
            "logs",
            "reports",
            "htmlcov",
            "config",
            "prompts",
        ]
        
        print("📁 Creating project directories...")
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            print(f"  Created: {directory}")
        
        return True

    def setup_git_hooks(self) -> bool:
        """Setup additional git hooks."""
        hooks_dir = self.project_root / ".git" / "hooks"
        if not hooks_dir.exists():
            print("⚠️  Git repository not found, skipping git hooks setup")
            return True
        
        # Create a simple pre-push hook
        pre_push_hook = hooks_dir / "pre-push"
        pre_push_content = """#!/bin/sh
# Pre-push hook to run quality checks

echo "Running quality checks before push..."
python scripts/quality-check.py --fast

if [ $? -ne 0 ]; then
    echo "Quality checks failed. Push aborted."
    exit 1
fi

echo "Quality checks passed. Proceeding with push."
"""
        
        pre_push_hook.write_text(pre_push_content)
        pre_push_hook.chmod(0o755)
        
        print("✅ Git hooks setup completed")
        return True

    def create_config_files(self) -> bool:
        """Create default configuration files if they don't exist."""
        config_dir = self.project_root / "config"
        
        # Create default config if it doesn't exist
        config_file = config_dir / "config.yaml"
        if not config_file.exists():
            print("📝 Creating default configuration file...")
            # The config.example.yaml should already exist, so we'll copy it
            example_config = config_dir / "config.example.yaml"
            if example_config.exists():
                import shutil
                shutil.copy2(example_config, config_file)
                print(f"✅ Created {config_file} from example")
            else:
                print("⚠️  config.example.yaml not found, skipping config creation")
        
        return True

    def run_initial_tests(self) -> bool:
        """Run a quick test to verify setup."""
        print("🧪 Running initial tests to verify setup...")
        return self.run_command(
            ["pytest", "-m", "unit", "--maxfail=5", "-q"],
            "Initial test run",
            check=False
        )

    def display_setup_summary(self) -> None:
        """Display setup summary and next steps."""
        print("\n" + "="*60)
        print("🎉 Development environment setup completed!")
        print("\n📋 Summary:")
        print(f"  - Project root: {self.project_root}")
        print(f"  - Virtual environment: {self.venv_path}")
        print("  - Dependencies installed")
        print("  - Pre-commit hooks configured")
        print("  - Project directories created")
        print("  - Git hooks setup")
        
        print("\n🚀 Next steps:")
        
        # Show activation command
        activate_cmd = self.activate_virtual_environment()
        if activate_cmd:
            print(f"  1. Activate virtual environment: {activate_cmd}")
        
        print("  2. Review and update config/config.yaml")
        print("  3. Run tests: python scripts/run-tests.py")
        print("  4. Run quality checks: python scripts/quality-check.py")
        print("  5. Start development!")
        
        print("\n📚 Available commands:")
        print("  - make help                    # Show all available make commands")
        print("  - python scripts/run-tests.py # Run tests with various options")
        print("  - python scripts/quality-check.py # Run code quality checks")
        print("  - pre-commit run --all-files   # Run pre-commit hooks")

    def setup_development_environment(self, skip_tests: bool = False) -> bool:
        """Setup the complete development environment."""
        print("🚀 Setting up OzBargain Deal Filter development environment...")
        
        steps = [
            ("Python version check", self.check_python_version),
            ("Virtual environment creation", self.create_virtual_environment),
            ("Dependencies installation", lambda: self.install_dependencies(dev=True)),
            ("Project directories creation", self.create_directories),
            ("Configuration files setup", self.create_config_files),
            ("Pre-commit hooks setup", self.setup_pre_commit_hooks),
            ("Git hooks setup", self.setup_git_hooks),
        ]
        
        if not skip_tests:
            steps.append(("Initial tests", self.run_initial_tests))
        
        for step_name, step_func in steps:
            if not step_func():
                print(f"\n💥 Setup failed at step: {step_name}")
                return False
        
        self.display_setup_summary()
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup development environment for OzBargain Deal Filter"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip initial test run"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    setup = DevSetup(args.project_root)
    
    if not setup.setup_development_environment(skip_tests=args.skip_tests):
        sys.exit(1)
    
    print("\n✨ Development environment is ready!")


if __name__ == "__main__":
    main()
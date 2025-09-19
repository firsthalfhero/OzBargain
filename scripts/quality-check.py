#!/usr/bin/env python3
"""
Comprehensive code quality checker for OzBargain Deal Filter.

This script runs all code quality checks including linting, type checking,
formatting verification, security checks, and test coverage.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple
import argparse


class QualityChecker:
    """Runs comprehensive code quality checks."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.source_dirs = ["ozb_deal_filter", "tests"]
        self.failed_checks: List[str] = []

    def run_command(self, command: List[str], description: str) -> bool:
        """Run a command and return success status."""
        print(f"\n🔍 {description}...")
        print(f"Running: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                print(f"✅ {description} passed")
                if result.stdout.strip():
                    print(f"Output: {result.stdout.strip()}")
                return True
            else:
                print(f"❌ {description} failed")
                if result.stdout.strip():
                    print(f"STDOUT: {result.stdout.strip()}")
                if result.stderr.strip():
                    print(f"STDERR: {result.stderr.strip()}")
                self.failed_checks.append(description)
                return False
                
        except FileNotFoundError:
            print(f"❌ {description} failed - command not found")
            self.failed_checks.append(f"{description} (command not found)")
            return False

    def check_black_formatting(self) -> bool:
        """Check code formatting with black."""
        return self.run_command(
            ["black", "--check", "--diff"] + self.source_dirs,
            "Black code formatting"
        )

    def check_isort_imports(self) -> bool:
        """Check import sorting with isort."""
        return self.run_command(
            ["isort", "--check-only", "--diff"] + self.source_dirs,
            "Import sorting (isort)"
        )

    def check_flake8_linting(self) -> bool:
        """Check code linting with flake8."""
        return self.run_command(
            ["flake8"] + self.source_dirs,
            "Flake8 linting"
        )

    def check_mypy_typing(self) -> bool:
        """Check type hints with mypy."""
        return self.run_command(
            ["mypy", "ozb_deal_filter"],
            "MyPy type checking"
        )

    def check_bandit_security(self) -> bool:
        """Check security issues with bandit."""
        return self.run_command(
            ["bandit", "-r", "ozb_deal_filter", "-f", "json"],
            "Bandit security check"
        )

    def run_tests_with_coverage(self) -> bool:
        """Run tests with coverage reporting."""
        return self.run_command(
            [
                "pytest",
                "--cov=ozb_deal_filter",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-fail-under=85",
                "-v"
            ],
            "Test suite with coverage"
        )

    def run_fast_tests(self) -> bool:
        """Run only fast unit tests."""
        return self.run_command(
            ["pytest", "-m", "not slow", "-v"],
            "Fast unit tests"
        )

    def check_dependencies(self) -> bool:
        """Check for dependency issues."""
        return self.run_command(
            ["pip", "check"],
            "Dependency consistency check"
        )

    def run_all_checks(self, skip_slow: bool = False) -> bool:
        """Run all quality checks."""
        print("🚀 Starting comprehensive code quality checks...")
        print(f"Project root: {self.project_root}")
        
        checks = [
            ("Dependencies", self.check_dependencies),
            ("Black formatting", self.check_black_formatting),
            ("Import sorting", self.check_isort_imports),
            ("Flake8 linting", self.check_flake8_linting),
            ("MyPy type checking", self.check_mypy_typing),
            ("Bandit security", self.check_bandit_security),
        ]
        
        if skip_slow:
            checks.append(("Fast tests", self.run_fast_tests))
        else:
            checks.append(("Tests with coverage", self.run_tests_with_coverage))
        
        all_passed = True
        for check_name, check_func in checks:
            if not check_func():
                all_passed = False
        
        print("\n" + "="*60)
        if all_passed:
            print("🎉 All quality checks passed!")
            return True
        else:
            print("💥 Some quality checks failed:")
            for failed_check in self.failed_checks:
                print(f"  - {failed_check}")
            print("\nPlease fix the issues above before committing.")
            return False

    def fix_formatting(self) -> bool:
        """Auto-fix formatting issues."""
        print("🔧 Auto-fixing formatting issues...")
        
        black_success = self.run_command(
            ["black"] + self.source_dirs,
            "Black auto-formatting"
        )
        
        isort_success = self.run_command(
            ["isort"] + self.source_dirs,
            "Import sorting auto-fix"
        )
        
        return black_success and isort_success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive code quality checks"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix formatting issues"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests and checks"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    checker = QualityChecker(args.project_root)
    
    if args.fix:
        if not checker.fix_formatting():
            sys.exit(1)
        print("✅ Formatting fixes applied. Please review changes.")
        return
    
    if not checker.run_all_checks(skip_slow=args.fast):
        sys.exit(1)
    
    print("🎯 Ready to commit!")


if __name__ == "__main__":
    main()
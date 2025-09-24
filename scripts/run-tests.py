#!/usr/bin/env python3
"""
Comprehensive test runner for OzBargain Deal Filter.

This script provides various test execution modes including unit tests,
integration tests, performance benchmarks, and coverage reporting.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class TestRunner:
    """Manages test execution with various configurations."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.reports_dir = project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)

    def run_command(self, command: List[str], description: str) -> bool:
        """Run a command and return success status."""
        print(f"\n🧪 {description}...")
        print(f"Running: {' '.join(command)}")

        try:
            result = subprocess.run(command, cwd=self.project_root, check=False)

            if result.returncode == 0:
                print(f"✅ {description} completed successfully")
                return True
            else:
                print(f"❌ {description} failed with exit code {result.returncode}")
                return False

        except FileNotFoundError:
            print(f"❌ {description} failed - pytest not found")
            return False

    def run_unit_tests(self, verbose: bool = False) -> bool:
        """Run unit tests only."""
        cmd = ["pytest", "-m", "unit"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Unit tests")

    def run_integration_tests(self, verbose: bool = False) -> bool:
        """Run integration tests only."""
        cmd = ["pytest", "-m", "integration"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Integration tests")

    def run_fast_tests(self, verbose: bool = False) -> bool:
        """Run fast tests (excluding slow ones)."""
        cmd = ["pytest", "-m", "not slow"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Fast tests")

    def run_slow_tests(self, verbose: bool = False) -> bool:
        """Run slow tests only."""
        cmd = ["pytest", "-m", "slow"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Slow tests")

    def run_network_tests(self, verbose: bool = False) -> bool:
        """Run tests that require network access."""
        cmd = ["pytest", "-m", "network"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Network tests")

    def run_docker_tests(self, verbose: bool = False) -> bool:
        """Run tests that require Docker."""
        cmd = ["pytest", "-m", "docker"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Docker tests")

    def run_benchmark_tests(self, verbose: bool = False) -> bool:
        """Run performance benchmark tests."""
        cmd = ["pytest", "-m", "benchmark", "--benchmark-only"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Benchmark tests")

    def run_coverage_tests(self, min_coverage: int = 85) -> bool:
        """Run tests with coverage reporting."""
        cmd = [
            "pytest",
            f"--cov-fail-under={min_coverage}",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml",
        ]
        return self.run_command(cmd, f"Coverage tests (min {min_coverage}%)")

    def run_parallel_tests(self, num_workers: Optional[int] = None) -> bool:
        """Run tests in parallel using pytest-xdist."""
        cmd = ["pytest"]
        if num_workers:
            cmd.extend(["-n", str(num_workers)])
        else:
            cmd.extend(["-n", "auto"])
        return self.run_command(cmd, "Parallel tests")

    def run_specific_test(self, test_path: str, verbose: bool = False) -> bool:
        """Run a specific test file or test function."""
        cmd = ["pytest", test_path]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, f"Specific test: {test_path}")

    def run_failed_tests(self, verbose: bool = False) -> bool:
        """Re-run only failed tests from last run."""
        cmd = ["pytest", "--lf"]
        if verbose:
            cmd.append("-v")
        return self.run_command(cmd, "Failed tests from last run")

    def run_all_tests(self, verbose: bool = False, parallel: bool = False) -> bool:
        """Run all tests with comprehensive reporting."""
        cmd = ["pytest"]

        if parallel:
            cmd.extend(["-n", "auto"])

        if verbose:
            cmd.append("-v")

        return self.run_command(cmd, "All tests")

    def generate_test_report(self) -> bool:
        """Generate comprehensive test report."""
        print("\n📊 Generating comprehensive test report...")

        # Run tests with all reporting enabled
        cmd = [
            "pytest",
            "--cov=ozb_deal_filter",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml",
            "--cov-report=term-missing",
            "--html=reports/pytest_report.html",
            "--self-contained-html",
            "--json-report",
            "--json-report-file=reports/pytest_report.json",
            "-v",
        ]

        success = self.run_command(cmd, "Test report generation")

        if success:
            print("\n📋 Test reports generated:")
            print(f"  - HTML coverage: {self.project_root}/htmlcov/index.html")
            print(f"  - XML coverage: {self.project_root}/coverage.xml")
            print(
                f"  - HTML test report: {self.project_root}/reports/pytest_report.html"
            )
            print(
                f"  - JSON test report: {self.project_root}/reports/pytest_report.json"
            )

        return success

    def clean_test_artifacts(self) -> None:
        """Clean up test artifacts and cache files."""
        print("\n🧹 Cleaning test artifacts...")

        artifacts = [
            ".pytest_cache",
            ".coverage",
            "htmlcov",
            "coverage.xml",
            "reports",
            ".mypy_cache",
            "__pycache__",
        ]

        for artifact in artifacts:
            artifact_path = self.project_root / artifact
            if artifact_path.exists():
                if artifact_path.is_dir():
                    import shutil

                    shutil.rmtree(artifact_path)
                    print(f"  Removed directory: {artifact}")
                else:
                    artifact_path.unlink()
                    print(f"  Removed file: {artifact}")

        # Find and remove __pycache__ directories recursively
        for pycache in self.project_root.rglob("__pycache__"):
            if pycache.is_dir():
                import shutil

                shutil.rmtree(pycache)
                print(f"  Removed: {pycache}")

        print("✅ Test artifacts cleaned")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run tests with various configurations"
    )

    # Test selection arguments
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument(
        "--integration", action="store_true", help="Run integration tests only"
    )
    parser.add_argument("--fast", action="store_true", help="Run fast tests only")
    parser.add_argument("--slow", action="store_true", help="Run slow tests only")
    parser.add_argument("--network", action="store_true", help="Run network tests only")
    parser.add_argument("--docker", action="store_true", help="Run Docker tests only")
    parser.add_argument(
        "--benchmark", action="store_true", help="Run benchmark tests only"
    )
    parser.add_argument(
        "--failed", action="store_true", help="Re-run failed tests from last run"
    )

    # Test execution options
    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )
    parser.add_argument(
        "--min-coverage", type=int, default=85, help="Minimum coverage percentage"
    )
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--workers", type=int, help="Number of parallel workers")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Utility options
    parser.add_argument(
        "--report", action="store_true", help="Generate comprehensive test report"
    )
    parser.add_argument("--clean", action="store_true", help="Clean test artifacts")
    parser.add_argument("--test", type=str, help="Run specific test file or function")
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="Project root directory"
    )

    args = parser.parse_args()

    runner = TestRunner(args.project_root)

    # Handle utility commands first
    if args.clean:
        runner.clean_test_artifacts()
        return

    if args.report:
        success = runner.generate_test_report()
        sys.exit(0 if success else 1)

    # Handle specific test
    if args.test:
        success = runner.run_specific_test(args.test, args.verbose)
        sys.exit(0 if success else 1)

    # Handle test selection
    success = True

    if args.unit:
        success = runner.run_unit_tests(args.verbose)
    elif args.integration:
        success = runner.run_integration_tests(args.verbose)
    elif args.fast:
        success = runner.run_fast_tests(args.verbose)
    elif args.slow:
        success = runner.run_slow_tests(args.verbose)
    elif args.network:
        success = runner.run_network_tests(args.verbose)
    elif args.docker:
        success = runner.run_docker_tests(args.verbose)
    elif args.benchmark:
        success = runner.run_benchmark_tests(args.verbose)
    elif args.failed:
        success = runner.run_failed_tests(args.verbose)
    elif args.coverage:
        success = runner.run_coverage_tests(args.min_coverage)
    elif args.parallel:
        success = runner.run_parallel_tests(args.workers)
    else:
        # Default: run all tests
        success = runner.run_all_tests(args.verbose, args.parallel)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

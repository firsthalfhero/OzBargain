#!/usr/bin/env python3
"""
Integration test runner for OzBargain Deal Filter system.

This script runs comprehensive integration tests including end-to-end workflow
tests, performance benchmarks, and system validation checks.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(cmd: List[str], cwd: Path = None) -> Dict[str, Any]:
    """Run a command and return results."""
    print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    result = subprocess.run(
        cmd, cwd=cwd or project_root, capture_output=True, text=True
    )
    duration = time.time() - start_time

    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration": duration,
        "success": result.returncode == 0,
    }


def run_integration_tests(
    test_categories: List[str] = None, verbose: bool = False
) -> bool:
    """Run integration tests with specified categories."""
    print("🧪 Running OzBargain Deal Filter Integration Tests")
    print("=" * 60)

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add verbosity
    if verbose:
        cmd.extend(["-v", "-s"])

    # Add test markers
    if test_categories:
        marker_expr = " or ".join(test_categories)
        cmd.extend(["-m", marker_expr])
    else:
        cmd.extend(["-m", "integration"])

    # Add coverage if requested
    cmd.extend(
        [
            "--cov=ozb_deal_filter",
            "--cov-report=term-missing",
            "--cov-report=html:reports/coverage",
        ]
    )

    # Specify test files
    test_files = [
        "tests/test_integration.py",
        "tests/test_system_validation.py",
    ]
    cmd.extend(test_files)

    # Run tests
    result = run_command(cmd)

    print("\n📊 Test Results:")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Success: {'✅' if result['success'] else '❌'}")

    if not result["success"]:
        print("\n❌ Test Failures:")
        print(result["stderr"])

    return result["success"]


def run_performance_benchmarks(verbose: bool = False) -> bool:
    """Run performance benchmark tests."""
    print("\n🚀 Running Performance Benchmarks")
    print("=" * 40)

    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.extend(["-v", "-s"])

    cmd.extend(
        [
            "-m",
            "integration",
            "--benchmark-only",
            "--benchmark-sort=mean",
            "--benchmark-columns=min,max,mean,stddev",
            "tests/test_integration.py::TestPerformanceBenchmarks",
        ]
    )

    result = run_command(cmd)

    print("\n📈 Benchmark Results:")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Success: {'✅' if result['success'] else '❌'}")

    return result["success"]


def run_system_validation(verbose: bool = False) -> bool:
    """Run system validation tests."""
    print("\n🔍 Running System Validation")
    print("=" * 35)

    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.extend(["-v", "-s"])

    cmd.extend(
        [
            "-m",
            "integration",
            "tests/test_system_validation.py",
        ]
    )

    result = run_command(cmd)

    print("\n✅ Validation Results:")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Success: {'✅' if result['success'] else '❌'}")

    return result["success"]


def check_test_environment() -> bool:
    """Check if test environment is properly set up."""
    print("🔧 Checking Test Environment")
    print("=" * 30)

    checks = []

    # Check Python version
    python_version = sys.version_info
    python_ok = python_version >= (3, 11)
    checks.append(
        ("Python 3.11+", python_ok, f"{python_version.major}.{python_version.minor}")
    )

    # Check required packages
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-mock",
        "pyyaml",
        "psutil",
    ]

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            checks.append((f"Package: {package}", True, "installed"))
        except ImportError:
            checks.append((f"Package: {package}", False, "missing"))

    # Check test files exist
    test_files = [
        "tests/test_integration.py",
        "tests/test_system_validation.py",
        "tests/integration_fixtures.py",
        "tests/conftest.py",
    ]

    for test_file in test_files:
        file_path = project_root / test_file
        file_exists = file_path.exists()
        checks.append(
            (
                f"Test file: {test_file}",
                file_exists,
                "exists" if file_exists else "missing",
            )
        )

    # Check source files exist
    source_files = [
        "ozb_deal_filter/orchestrator.py",
        "ozb_deal_filter/utils/system_monitor.py",
        "ozb_deal_filter/interfaces.py",
    ]

    for source_file in source_files:
        file_path = project_root / source_file
        file_exists = file_path.exists()
        checks.append(
            (
                f"Source file: {source_file}",
                file_exists,
                "exists" if file_exists else "missing",
            )
        )

    # Print results
    all_ok = True
    for check_name, success, details in checks:
        status = "✅" if success else "❌"
        print(f"{status} {check_name}: {details}")
        if not success:
            all_ok = False

    if not all_ok:
        print("\n❌ Environment check failed. Please install missing dependencies.")
        print("Run: pip install -r requirements.txt")

    return all_ok


def generate_test_report(results: Dict[str, bool]) -> None:
    """Generate a comprehensive test report."""
    print("\n📋 Integration Test Report")
    print("=" * 50)

    total_tests = len(results)
    passed_tests = sum(1 for success in results.values() if success)

    print(f"Total Test Categories: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {passed_tests / total_tests * 100:.1f}%")

    print("\nDetailed Results:")
    for category, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {category}")

    # Generate recommendations
    print("\n💡 Recommendations:")
    if all(results.values()):
        print("  🎉 All integration tests passed! System is ready for deployment.")
    else:
        failed_categories = [cat for cat, success in results.items() if not success]
        print(f"  🔧 Fix issues in: {', '.join(failed_categories)}")
        print("  📖 Check test output above for specific failure details.")
        print("  🐛 Run individual test categories with -c flag for focused debugging.")


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run OzBargain Deal Filter integration tests"
    )
    parser.add_argument(
        "-c",
        "--category",
        choices=["workflow", "performance", "validation", "all"],
        default="all",
        help="Test category to run",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--skip-env-check", action="store_true", help="Skip environment check"
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Run performance benchmarks only"
    )

    args = parser.parse_args()

    # Check environment
    if not args.skip_env_check:
        if not check_test_environment():
            sys.exit(1)

    # Create reports directory
    reports_dir = project_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    results = {}

    try:
        if args.benchmark:
            # Run benchmarks only
            success = run_performance_benchmarks(args.verbose)
            results["Performance Benchmarks"] = success

        elif args.category == "workflow":
            # Run workflow tests only
            success = run_integration_tests(["integration"], args.verbose)
            results["End-to-End Workflow"] = success

        elif args.category == "performance":
            # Run performance tests only
            success = run_performance_benchmarks(args.verbose)
            results["Performance Benchmarks"] = success

        elif args.category == "validation":
            # Run validation tests only
            success = run_system_validation(args.verbose)
            results["System Validation"] = success

        else:  # all
            # Run all test categories
            print("🚀 Running Complete Integration Test Suite")
            print("=" * 60)

            # End-to-end workflow tests
            workflow_success = run_integration_tests(["integration"], args.verbose)
            results["End-to-End Workflow"] = workflow_success

            # Performance benchmarks
            perf_success = run_performance_benchmarks(args.verbose)
            results["Performance Benchmarks"] = perf_success

            # System validation
            validation_success = run_system_validation(args.verbose)
            results["System Validation"] = validation_success

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        sys.exit(1)

    # Generate report
    generate_test_report(results)

    # Exit with appropriate code
    if all(results.values()):
        print("\n🎉 All integration tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some integration tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

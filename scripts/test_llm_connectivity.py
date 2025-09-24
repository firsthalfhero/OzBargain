#!/usr/bin/env python3
"""
OzBargain Deal Filter - LLM Connectivity Test Script

This script tests the connectivity and performance of local LLM integration
with the Ollama service running in Docker.
"""

import json
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests


@dataclass
class TestResult:
    """Test result data structure"""

    test_name: str
    success: bool
    duration: float
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None


class OllamaConnectivityTester:
    """Test Ollama service connectivity and performance"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 30

    def test_service_health(self) -> TestResult:
        """Test if Ollama service is running and accessible"""
        start_time = time.time()

        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                return TestResult(
                    test_name="Service Health Check",
                    success=True,
                    duration=duration,
                    response_data=data,
                )
            else:
                return TestResult(
                    test_name="Service Health Check",
                    success=False,
                    duration=duration,
                    error_message=f"HTTP {response.status_code}: {response.text}",
                )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            return TestResult(
                test_name="Service Health Check",
                success=False,
                duration=duration,
                error_message=str(e),
            )

    def test_model_availability(self) -> TestResult:
        """Test if any models are available"""
        start_time = time.time()

        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])

                if models:
                    return TestResult(
                        test_name="Model Availability",
                        success=True,
                        duration=duration,
                        response_data={"model_count": len(models), "models": models},
                    )
                else:
                    return TestResult(
                        test_name="Model Availability",
                        success=False,
                        duration=duration,
                        error_message="No models installed",
                    )
            else:
                return TestResult(
                    test_name="Model Availability",
                    success=False,
                    duration=duration,
                    error_message=f"HTTP {response.status_code}: {response.text}",
                )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            return TestResult(
                test_name="Model Availability",
                success=False,
                duration=duration,
                error_message=str(e),
            )

    def test_model_evaluation(self, model_name: str) -> TestResult:
        """Test model evaluation with a sample deal"""
        start_time = time.time()

        test_prompt = (
            "Analyze this deal for relevance to electronics enthusiasts:\n\n"
            "Title: iPhone 14 Pro 128GB - Special Offer\n"
            "Price: $899 (was $1399, save $500 - 36% off)\n"
            "Description: Latest iPhone with Pro camera system, A16 Bionic chip, "
            "and Dynamic Island. Limited time offer from authorized retailer.\n\n"
            "Respond with YES or NO followed by a brief explanation."
        )

        payload = {
            "model": model_name,
            "prompt": test_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 200},
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60,  # Longer timeout for generation
            )
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                return TestResult(
                    test_name=f"Model Evaluation ({model_name})",
                    success=True,
                    duration=duration,
                    response_data=data,
                )
            else:
                return TestResult(
                    test_name=f"Model Evaluation ({model_name})",
                    success=False,
                    duration=duration,
                    error_message=f"HTTP {response.status_code}: {response.text}",
                )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=f"Model Evaluation ({model_name})",
                success=False,
                duration=duration,
                error_message=str(e),
            )

    def test_performance_benchmark(self, model_name: str) -> TestResult:
        """Benchmark model performance with multiple requests"""
        test_prompts = [
            "Is this a good deal: Gaming laptop RTX 4060 - $1200 (was $1500)?",
            "Evaluate: Wireless headphones 50% off - $75 (was $150)",
            'Deal analysis: Smart TV 65" 4K - $800 (was $1200, 33% off)',
        ]

        start_time = time.time()
        results = []

        try:
            for i, prompt in enumerate(test_prompts):
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.5, "max_tokens": 100},
                }

                request_start = time.time()
                response = self.session.post(
                    f"{self.base_url}/api/generate", json=payload, timeout=45
                )
                request_duration = time.time() - request_start

                if response.status_code == 200:
                    data = response.json()
                    results.append(
                        {
                            "request": i + 1,
                            "duration": request_duration,
                            "success": True,
                            "response_length": len(data.get("response", "")),
                        }
                    )
                else:
                    results.append(
                        {
                            "request": i + 1,
                            "duration": request_duration,
                            "success": False,
                            "error": f"HTTP {response.status_code}",
                        }
                    )

            total_duration = time.time() - start_time
            successful_requests = sum(1 for r in results if r["success"])
            avg_duration = sum(r["duration"] for r in results if r["success"]) / max(
                successful_requests, 1
            )

            return TestResult(
                test_name=f"Performance Benchmark ({model_name})",
                success=successful_requests > 0,
                duration=total_duration,
                response_data={
                    "total_requests": len(test_prompts),
                    "successful_requests": successful_requests,
                    "average_response_time": avg_duration,
                    "results": results,
                },
            )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=f"Performance Benchmark ({model_name})",
                success=False,
                duration=duration,
                error_message=str(e),
            )


def print_colored(text: str, color: str = ""):
    """Print colored text to console"""
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "reset": "\033[0m",
    }

    if color in colors:
        print(f"{colors[color]}{text}{colors['reset']}")
    else:
        print(text)


def format_duration(duration: float) -> str:
    """Format duration in human-readable format"""
    if duration < 1:
        return f"{duration*1000:.0f}ms"
    else:
        return f"{duration:.2f}s"


def print_test_result(result: TestResult):
    """Print formatted test result"""
    status_color = "green" if result.success else "red"
    status_text = "PASS" if result.success else "FAIL"

    print_colored(
        f"  {result.test_name}: {status_text} ({format_duration(result.duration)})",
        status_color,
    )

    if not result.success and result.error_message:
        print_colored(f"    Error: {result.error_message}", "red")

    if result.success and result.response_data:
        if "models" in result.response_data:
            models = result.response_data["models"]
            print_colored(f"    Found {len(models)} models:", "blue")
            for model in models[:3]:  # Show first 3 models
                name = model.get("name", "Unknown")
                size_gb = model.get("size", 0) / (1024**3)
                print_colored(f"      - {name} ({size_gb:.1f}GB)", "blue")
            if len(models) > 3:
                print_colored(f"      ... and {len(models) - 3} more", "blue")

        elif "response" in result.response_data:
            response_text = result.response_data["response"][:200]
            if len(result.response_data["response"]) > 200:
                response_text += "..."
            print_colored(f"    Response: {response_text}", "blue")

        elif "successful_requests" in result.response_data:
            data = result.response_data
            print_colored(
                f"    Successful: {data['successful_requests']}/{data['total_requests']}",
                "blue",
            )
            print_colored(
                f"    Avg Response Time: {format_duration(data['average_response_time'])}",
                "blue",
            )


def main():
    """Main test execution"""
    print_colored("OzBargain Deal Filter - LLM Connectivity Test", "blue")
    print_colored("=" * 50, "blue")

    tester = OllamaConnectivityTester()

    # Test 1: Service Health
    print_colored("\n1. Testing Ollama Service Health...", "yellow")
    health_result = tester.test_service_health()
    print_test_result(health_result)

    if not health_result.success:
        print_colored("\nService is not accessible. Please ensure:", "red")
        print_colored(
            "  1. Docker containers are running: docker-compose up -d", "yellow"
        )
        print_colored("  2. Ollama service is healthy: docker-compose ps", "yellow")
        print_colored("  3. Port 11434 is not blocked by firewall", "yellow")
        sys.exit(1)

    # Test 2: Model Availability
    print_colored("\n2. Testing Model Availability...", "yellow")
    model_result = tester.test_model_availability()
    print_test_result(model_result)

    if not model_result.success:
        print_colored("\nNo models are installed. Please install a model:", "red")
        print_colored("  ./scripts/manage_models.ps1 -Pull -Model llama2:7b", "yellow")
        print_colored("  ./scripts/manage_models.sh pull llama2:7b", "yellow")
        sys.exit(1)

    # Test 3: Model Evaluation
    models = model_result.response_data.get("models", [])
    if models:
        test_model = models[0]["name"]
        print_colored(f"\n3. Testing Model Evaluation with {test_model}...", "yellow")
        eval_result = tester.test_model_evaluation(test_model)
        print_test_result(eval_result)

        # Test 4: Performance Benchmark
        if eval_result.success:
            print_colored(
                f"\n4. Running Performance Benchmark with {test_model}...", "yellow"
            )
            perf_result = tester.test_performance_benchmark(test_model)
            print_test_result(perf_result)

    # Summary
    print_colored("\n" + "=" * 50, "blue")
    print_colored("Test Summary:", "blue")

    all_tests = [health_result, model_result]
    if models:
        all_tests.extend([eval_result, perf_result])

    passed = sum(1 for test in all_tests if test.success)
    total = len(all_tests)

    if passed == total:
        print_colored(
            f"All {total} tests passed! LLM integration is working correctly.", "green"
        )
    else:
        print_colored(
            f"{passed}/{total} tests passed. Please check failed tests above.", "yellow"
        )

    print_colored("\nRecommendations:", "blue")
    print_colored(
        "  - For best performance, use llama2:7b or mistral:7b models", "yellow"
    )
    print_colored(
        "  - Monitor response times and adjust timeout settings if needed", "yellow"
    )
    print_colored("  - Consider model size vs. available system resources", "yellow")


if __name__ == "__main__":
    main()

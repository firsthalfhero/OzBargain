"""Simple benchmark tests for CI."""

import pytest


@pytest.mark.benchmark
def test_simple_benchmark(benchmark):
    """Simple benchmark test to ensure CI benchmark job works."""

    def simple_function():
        return sum(range(100))

    result = benchmark(simple_function)
    assert result == 4950

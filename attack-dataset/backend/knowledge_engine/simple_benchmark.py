#!/usr/bin/env python3
"""
Simple benchmark script for Knowledge Engine API.
Tests basic API performance and response times.
"""
import time
import statistics
import requests
from typing import List, Dict

API_BASE_URL = "http://localhost:8000"

def benchmark_endpoint(endpoint: str, method: str = "GET", payload: Dict = None, iterations: int = 10) -> Dict:
    """Benchmark a single API endpoint."""
    times = []
    errors = 0
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: {method} {endpoint}")
    print(f"Iterations: {iterations}")
    print(f"{'='*60}")
    
    for i in range(iterations):
        try:
            start_time = time.time()
            
            if method == "GET":
                response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10)
            elif method == "POST":
                response = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=10)
            
            end_time = time.time()
            elapsed = (end_time - start_time) * 1000  # Convert to milliseconds
            
            if response.status_code == 200:
                times.append(elapsed)
                print(f"Iteration {i+1}/{iterations}: {elapsed:.2f}ms - Status: {response.status_code}")
            else:
                errors += 1
                print(f"Iteration {i+1}/{iterations}: ERROR - Status: {response.status_code}")
                
        except Exception as e:
            errors += 1
            print(f"Iteration {i+1}/{iterations}: ERROR - {str(e)}")
    
    if times:
        return {
            "endpoint": endpoint,
            "method": method,
            "iterations": iterations,
            "successful": len(times),
            "errors": errors,
            "avg_time_ms": statistics.mean(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "median_time_ms": statistics.median(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0
        }
    else:
        return {
            "endpoint": endpoint,
            "method": method,
            "iterations": iterations,
            "successful": 0,
            "errors": errors,
            "error": "All requests failed"
        }

def main():
    """Run benchmark tests."""
    print("Knowledge Engine API Benchmark")
    print(f"Target: {API_BASE_URL}")
    
    # Check if API is running
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("ERROR: API health check failed")
            return
        print("✓ API is running and healthy")
    except Exception as e:
        print(f"ERROR: Cannot connect to API: {e}")
        return
    
    # Benchmark endpoints
    benchmarks = []
    
    # Test health endpoint
    result = benchmark_endpoint("/health", "GET", iterations=20)
    benchmarks.append(result)
    
    # Test docs endpoint
    result = benchmark_endpoint("/docs", "GET", iterations=10)
    benchmarks.append(result)
    
    # Test OpenAPI JSON
    result = benchmark_endpoint("/openapi.json", "GET", iterations=10)
    benchmarks.append(result)
    
    # Print summary
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    
    for result in benchmarks:
        if "error" not in result:
            print(f"\nEndpoint: {result['method']} {result['endpoint']}")
            print(f"  Success Rate: {result['successful']}/{result['iterations']} ({100*result['successful']/result['iterations']:.1f}%)")
            print(f"  Avg Time: {result['avg_time_ms']:.2f}ms")
            print(f"  Min Time: {result['min_time_ms']:.2f}ms")
            print(f"  Max Time: {result['max_time_ms']:.2f}ms")
            print(f"  Median: {result['median_time_ms']:.2f}ms")
            print(f"  Std Dev: {result['std_dev_ms']:.2f}ms")
        else:
            print(f"\nEndpoint: {result['method']} {result['endpoint']}")
            print(f"  ERROR: {result['error']}")
    
    print(f"\n{'='*60}")
    print("Benchmark complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test runner script with comprehensive reporting
Validates: Requirement 7.1 - Test suite should complete in less than 5 minutes
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class TestRunner:
    """Comprehensive test runner with reporting."""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.total_duration = 0
    
    def run_command(self, name, command, timeout=300):
        """Run a command and capture results."""
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print(f"{'=' * 60}")
        
        start = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration = time.time() - start
            
            self.results[name] = {
                "success": result.returncode == 0,
                "duration": duration,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            status = "✓ PASSED" if result.returncode == 0 else "✗ FAILED"
            print(f"\n{status} - Duration: {duration:.2f}s")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            self.results[name] = {
                "success": False,
                "duration": duration,
                "returncode": -1,
                "error": "Timeout"
            }
            print(f"✗ TIMEOUT after {duration:.2f}s")
            return False
        
        except Exception as e:
            duration = time.time() - start
            self.results[name] = {
                "success": False,
                "duration": duration,
                "returncode": -1,
                "error": str(e)
            }
            print(f"✗ ERROR: {e}")
            return False
    
    def run_unit_tests(self):
        """Run unit tests."""
        return self.run_command(
            "Unit Tests",
            "python -m pytest tests/unit/ -v --tb=short --timeout=60",
            timeout=120
        )
    
    def run_integration_tests(self):
        """Run integration tests."""
        return self.run_command(
            "Integration Tests",
            "python -m pytest tests/integration/ -v --tb=short --timeout=120",
            timeout=180
        )
    
    def run_e2e_tests(self):
        """Run end-to-end tests."""
        return self.run_command(
            "End-to-End Tests",
            "python -m pytest tests/test_end_to_end_workflows.py -v --tb=short --timeout=180",
            timeout=240
        )
    
    def run_performance_tests(self):
        """Run performance tests."""
        return self.run_command(
            "Performance Tests",
            "python -m pytest tests/test_load_performance.py -v --tb=short --timeout=600",
            timeout=720
        )
    
    def run_all_tests_with_coverage(self):
        """Run all tests with coverage."""
        return self.run_command(
            "All Tests with Coverage",
            "python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html --timeout=300",
            timeout=360
        )
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal test suites: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Total duration: {self.total_duration:.2f}s")
        
        # Requirement 7.1: Test suite should complete in less than 5 minutes
        if self.total_duration < 300:
            print(f"✓ Requirement 7.1 met: Tests completed in {self.total_duration:.2f}s (< 300s)")
        else:
            print(f"✗ Requirement 7.1 NOT met: Tests took {self.total_duration:.2f}s (> 300s)")
        
        print("\nDetailed Results:")
        for name, result in self.results.items():
            status = "✓ PASSED" if result["success"] else "✗ FAILED"
            duration = result["duration"]
            print(f"  {status} - {name}: {duration:.2f}s")
            
            if not result["success"] and "error" in result:
                print(f"    Error: {result['error']}")
        
        print("\n" + "=" * 60)
        
        return failed_tests == 0
    
    def run_all(self, quick=False):
        """Run all test suites."""
        self.start_time = time.time()
        
        print("=" * 60)
        print("NORTHBOUND SCRIPT GENERATOR - TEST SUITE")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Run tests in order
        if quick:
            # Quick mode: only essential tests
            self.run_unit_tests()
            self.run_integration_tests()
        else:
            # Full mode: all tests
            self.run_unit_tests()
            self.run_integration_tests()
            self.run_e2e_tests()
            self.run_performance_tests()
            self.run_all_tests_with_coverage()
        
        self.total_duration = time.time() - self.start_time
        
        # Print summary
        success = self.print_summary()
        
        return 0 if success else 1


def main():
    """Main entry point."""
    runner = TestRunner()
    
    # Check for quick mode
    quick = "--quick" in sys.argv or "-q" in sys.argv
    
    if quick:
        print("Running in QUICK mode (unit + integration tests only)")
    
    exit_code = runner.run_all(quick=quick)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

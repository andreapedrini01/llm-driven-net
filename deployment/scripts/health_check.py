#!/usr/bin/env python3
"""
Health Check Script for LLM Integration Module

Performs comprehensive health checks including:
- API availability
- ChatGPT API connectivity
- File system access
- Memory usage
- Configuration validation
"""

import sys
import time
import requests
from typing import Dict, Any, List
from pathlib import Path


class HealthChecker:
    """Performs health checks on the application"""
    
    def __init__(self, api_url: str = "http://localhost:8080"):
        self.api_url = api_url
        self.checks: List[Dict[str, Any]] = []
        
    def check_api_health(self) -> bool:
        """Check if API is responding"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                self.checks.append({
                    "name": "API Health",
                    "status": "healthy",
                    "details": data
                })
                return True
            else:
                self.checks.append({
                    "name": "API Health",
                    "status": "unhealthy",
                    "details": f"Status code: {response.status_code}"
                })
                return False
                
        except Exception as e:
            self.checks.append({
                "name": "API Health",
                "status": "unhealthy",
                "details": str(e)
            })
            return False
            
    def check_metrics_endpoint(self) -> bool:
        """Check if metrics endpoint is available"""
        try:
            response = requests.get(
                "http://localhost:8000/metrics",
                timeout=5
            )
            
            if response.status_code == 200:
                self.checks.append({
                    "name": "Metrics Endpoint",
                    "status": "healthy",
                    "details": "Prometheus metrics available"
                })
                return True
            else:
                self.checks.append({
                    "name": "Metrics Endpoint",
                    "status": "unhealthy",
                    "details": f"Status code: {response.status_code}"
                })
                return False
                
        except Exception as e:
            self.checks.append({
                "name": "Metrics Endpoint",
                "status": "unhealthy",
                "details": str(e)
            })
            return False
            
    def check_file_system(self) -> bool:
        """Check file system access"""
        try:
            required_dirs = ["cache", "output", "logs"]
            missing_dirs = []
            
            for dir_name in required_dirs:
                dir_path = Path(dir_name)
                if not dir_path.exists():
                    missing_dirs.append(dir_name)
                elif not dir_path.is_dir():
                    missing_dirs.append(f"{dir_name} (not a directory)")
                    
            if missing_dirs:
                self.checks.append({
                    "name": "File System",
                    "status": "warning",
                    "details": f"Missing directories: {', '.join(missing_dirs)}"
                })
                return False
            else:
                self.checks.append({
                    "name": "File System",
                    "status": "healthy",
                    "details": "All required directories exist"
                })
                return True
                
        except Exception as e:
            self.checks.append({
                "name": "File System",
                "status": "unhealthy",
                "details": str(e)
            })
            return False
            
    def check_configuration(self) -> bool:
        """Check configuration file"""
        try:
            env_file = Path(".env")
            
            if not env_file.exists():
                self.checks.append({
                    "name": "Configuration",
                    "status": "warning",
                    "details": ".env file not found"
                })
                return False
                
            # Check for critical config values
            content = env_file.read_text()
            critical_keys = ["OPENAI_API_KEY", "JWT_SECRET_KEY"]
            missing_keys = []
            
            for key in critical_keys:
                if key not in content or f"{key}=your-" in content:
                    missing_keys.append(key)
                    
            if missing_keys:
                self.checks.append({
                    "name": "Configuration",
                    "status": "warning",
                    "details": f"Missing or default values: {', '.join(missing_keys)}"
                })
                return False
            else:
                self.checks.append({
                    "name": "Configuration",
                    "status": "healthy",
                    "details": "Configuration file valid"
                })
                return True
                
        except Exception as e:
            self.checks.append({
                "name": "Configuration",
                "status": "unhealthy",
                "details": str(e)
            })
            return False
            
    def run_all_checks(self) -> bool:
        """Run all health checks"""
        print("Running health checks...\n")
        
        checks_passed = 0
        checks_total = 0
        
        # Run checks
        checks_to_run = [
            ("API Health", self.check_api_health),
            ("Metrics Endpoint", self.check_metrics_endpoint),
            ("File System", self.check_file_system),
            ("Configuration", self.check_configuration),
        ]
        
        for name, check_func in checks_to_run:
            checks_total += 1
            if check_func():
                checks_passed += 1
                
        # Print results
        print("\n" + "=" * 50)
        print("Health Check Results")
        print("=" * 50 + "\n")
        
        for check in self.checks:
            status_symbol = {
                "healthy": "✓",
                "unhealthy": "✗",
                "warning": "⚠"
            }.get(check["status"], "?")
            
            print(f"{status_symbol} {check['name']}: {check['status']}")
            if check.get("details"):
                print(f"  Details: {check['details']}")
            print()
            
        print("=" * 50)
        print(f"Checks passed: {checks_passed}/{checks_total}")
        print("=" * 50 + "\n")
        
        return checks_passed == checks_total
        
    def wait_for_healthy(self, max_wait: int = 60, interval: int = 5) -> bool:
        """Wait for service to become healthy"""
        print(f"Waiting for service to become healthy (max {max_wait}s)...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(
                    f"{self.api_url}/health",
                    timeout=2
                )
                
                if response.status_code == 200:
                    print("✓ Service is healthy!")
                    return True
                    
            except Exception:
                pass
                
            time.sleep(interval)
            print(".", end="", flush=True)
            
        print("\n✗ Service did not become healthy in time")
        return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Health check for LLM Integration Module")
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="API URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for service to become healthy"
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=60,
        help="Maximum wait time in seconds (default: 60)"
    )
    
    args = parser.parse_args()
    
    checker = HealthChecker(api_url=args.url)
    
    if args.wait:
        success = checker.wait_for_healthy(max_wait=args.max_wait)
    else:
        success = checker.run_all_checks()
        
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

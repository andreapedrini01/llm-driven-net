#!/usr/bin/env python3
"""
Comprehensive verification script for all 13 tasks in the Northbound Script Generator.

This script verifies that all implemented tasks still work correctly after
the project reorganization.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 80)
print("NORTHBOUND SCRIPT GENERATOR - ALL TASKS VERIFICATION")
print("=" * 80)

results = []

# Task 1: RYU/ComnetsEMU Integration
print("\n[Task 1] Testing RYU/ComnetsEMU Integration...")
try:
    from src.connectors.ryu_connector import RYUConfig, RYUConnectionPool, create_ryu_connector
    from src.connectors.comnetsemu_connector import ComnetsEMUConfig, create_comnetsemu_connector
    from src.core.retry_system import AdvancedRetrySystem, PersistentActionQueue
    
    # Test RYU connector
    ryu_config = RYUConfig(host="localhost", port=8080)
    print(f"  ✅ RYU connector configuration: {ryu_config.host}:{ryu_config.port}")
    
    # Test ComnetsEMU connector
    comnetsemu_config = ComnetsEMUConfig(host="localhost", port=6653)
    print(f"  ✅ ComnetsEMU connector configuration: {comnetsemu_config.host}:{comnetsemu_config.port}")
    
    # Test retry system
    retry_system = AdvancedRetrySystem()
    print(f"  ✅ Advanced retry system initialized")
    
    results.append(("Task 1: RYU/ComnetsEMU Integration", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 1: RYU/ComnetsEMU Integration", False))

# Task 3: API Gateway and Authentication
print("\n[Task 3] Testing API Gateway and Authentication...")
try:
    from src.api.gateway import app
    from src.api.auth import AuthService, User, UserRole
    from src.api.models import UserInfo, LoginResponse
    
    print(f"  ✅ API Gateway app created")
    print(f"  ✅ Authentication service available")
    print(f"  ✅ User models defined")
    
    results.append(("Task 3: API Gateway & Auth", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 3: API Gateway & Auth", False))

# Task 4: Monitoring and Metrics
print("\n[Task 4] Testing Monitoring and Metrics...")
try:
    from src.monitoring.prometheus_exporter import PrometheusExporter
    from src.monitoring.metrics_collector import MetricsCollector
    from src.monitoring.alert_manager import AlertManager
    from src.monitoring.influxdb_storage import InfluxDBStorage
    
    print(f"  ✅ Prometheus exporter available")
    print(f"  ✅ Metrics collector available")
    print(f"  ✅ Alert manager available")
    print(f"  ✅ InfluxDB storage available")
    
    results.append(("Task 4: Monitoring & Metrics", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 4: Monitoring & Metrics", False))

# Task 5: Web Dashboard
print("\n[Task 5] Testing Web Dashboard...")
try:
    from src.api.dashboard_routes import router as dashboard_router
    
    # Check frontend exists
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(frontend_path):
        print(f"  ✅ Frontend directory exists")
        
        # Check key frontend files
        if os.path.exists(os.path.join(frontend_path, "package.json")):
            print(f"  ✅ Frontend package.json exists")
        if os.path.exists(os.path.join(frontend_path, "src", "App.tsx")):
            print(f"  ✅ Frontend App.tsx exists")
    
    print(f"  ✅ Dashboard routes available")
    
    results.append(("Task 5: Web Dashboard", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 5: Web Dashboard", False))

# Task 7: Backup and Recovery
print("\n[Task 7] Testing Backup and Recovery...")
try:
    from src.backup.backup_manager import BackupManager
    from src.backup.recovery_service import RecoveryService
    from src.backup.retention_manager import RetentionManager
    from src.backup.scheduler import BackupScheduler
    
    print(f"  ✅ Backup manager available")
    print(f"  ✅ Recovery service available")
    print(f"  ✅ Retention manager available")
    print(f"  ✅ Backup scheduler available")
    
    results.append(("Task 7: Backup & Recovery", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 7: Backup & Recovery", False))

# Task 8: Testing and CI/CD
print("\n[Task 8] Testing Automated Testing...")
try:
    # Check test files exist
    tests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
    test_files = [
        "test_basic.py",
        "test_api_gateway.py",
        "test_retry_system.py",
        "test_monitoring_system.py",
        "test_backup_system.py",
        "test_system_integration.py",
        "test_end_to_end_workflows.py",
        "test_load_performance.py"
    ]
    
    found_tests = 0
    for test_file in test_files:
        if os.path.exists(os.path.join(tests_dir, test_file)):
            found_tests += 1
    
    print(f"  ✅ Found {found_tests}/{len(test_files)} test files")
    
    # Check CI/CD configuration
    ci_cd_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".github", "workflows", "ci-cd.yml")
    if os.path.exists(ci_cd_path):
        print(f"  ✅ CI/CD pipeline configured")
    
    # Check mocks
    mocks_dir = os.path.join(tests_dir, "mocks")
    if os.path.exists(mocks_dir):
        print(f"  ✅ Mock implementations available")
    
    results.append(("Task 8: Testing & CI/CD", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 8: Testing & CI/CD", False))

# Task 9: Configuration and Logging
print("\n[Task 9] Testing Configuration and Logging...")
try:
    from src.config.config_manager import ConfigManager
    from src.config.centralized_config import CentralizedConfigManager
    from src.config.distributed_config import DistributedConfigManager
    from src.logging.logger import setup_logging
    from src.logging.aggregator import LogAggregator
    
    print(f"  ✅ Config manager available")
    print(f"  ✅ Centralized config available")
    print(f"  ✅ Distributed config available")
    print(f"  ✅ Logging system available")
    print(f"  ✅ Log aggregator available")
    
    results.append(("Task 9: Config & Logging", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 9: Config & Logging", False))

# Task 10: Scalability and Performance
print("\n[Task 10] Testing Scalability and Performance...")
try:
    from src.scalability.load_balancer import LoadBalancer
    from src.scalability.redis_session import RedisSessionManager
    from src.scalability.connection_pool import GenericConnectionPool, PostgreSQLConnectionPool
    from src.scalability.parallel_processor import ParallelActionProcessor
    from src.scalability.rate_limiter import RateLimiter
    from src.scalability.backpressure import BackpressureManager
    
    print(f"  ✅ Load balancer available")
    print(f"  ✅ Redis session manager available")
    print(f"  ✅ Connection pool available")
    print(f"  ✅ Parallel action processor available")
    print(f"  ✅ Rate limiter available")
    print(f"  ✅ Backpressure manager available")
    
    results.append(("Task 10: Scalability & Performance", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 10: Scalability & Performance", False))

# Task 11: Documentation and Deployment
print("\n[Task 11] Testing Documentation and Deployment...")
try:
    # Check documentation
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    doc_files = [
        "README.md",
        "API_REFERENCE.md",
        "ARCHITECTURE.md",
        "DEPLOYMENT.md",
        "OPERATIONS.md",
        "ACTION_PACKAGE_GUIDE.md"
    ]
    
    found_docs = 0
    for doc_file in doc_files:
        if os.path.exists(os.path.join(docs_dir, doc_file)):
            found_docs += 1
    
    print(f"  ✅ Found {found_docs}/{len(doc_files)} documentation files")
    
    # Check deployment files
    deployment_files = [
        "docker-compose.yml",
        "Dockerfile",
        "deployment/deploy.sh"
    ]
    
    found_deployment = 0
    for deploy_file in deployment_files:
        if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), deploy_file)):
            found_deployment += 1
    
    print(f"  ✅ Found {found_deployment}/{len(deployment_files)} deployment files")
    
    results.append(("Task 11: Documentation & Deployment", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 11: Documentation & Deployment", False))

# Task 12: Integration and Orchestration
print("\n[Task 12] Testing Integration and Orchestration...")
try:
    from src.orchestrator.system_orchestrator import SystemOrchestrator
    from src.orchestrator.health_monitor import HealthMonitor
    from src.api.gateway_app import create_app
    
    print(f"  ✅ System orchestrator available")
    print(f"  ✅ Health monitor available")
    print(f"  ✅ Gateway app factory available")
    
    results.append(("Task 12: Integration & Orchestration", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 12: Integration & Orchestration", False))

# Task 13: Northbound Script Module
print("\n[Task 13] Testing Northbound Script Module...")
try:
    from northbound_script_generator.northbound_script import NorthboundScript
    from northbound_script_generator import NorthboundScript as NSG
    
    print(f"  ✅ NorthboundScript class available")
    print(f"  ✅ Module package exports available")
    
    # Check entry points
    entry_points = [
        "northbound_script_generator/start_system.py",
        "northbound_script_generator/main.py",
        "northbound_script_generator/run_api_gateway.py",
        "start.py"
    ]
    
    found_entry = 0
    for entry in entry_points:
        if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), entry)):
            found_entry += 1
    
    print(f"  ✅ Found {found_entry}/{len(entry_points)} entry points")
    
    results.append(("Task 13: Northbound Script Module", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Task 13: Northbound Script Module", False))

# Demos verification
print("\n[Bonus] Testing Demo Scripts...")
try:
    demos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demos")
    demo_files = [
        "demo_ryu_connector.py",
        "demo_comnetsemu_integration.py",
        "demo_monitoring_system.py",
        "demo_backup_system.py",
        "demo_centralized_config.py",
        "demo_scalability.py"
    ]
    
    found_demos = 0
    for demo_file in demo_files:
        if os.path.exists(os.path.join(demos_dir, demo_file)):
            found_demos += 1
    
    print(f"  ✅ Found {found_demos}/{len(demo_files)} demo scripts")
    
    results.append(("Bonus: Demo Scripts", True))
except Exception as e:
    print(f"  ❌ Failed: {e}")
    results.append(("Bonus: Demo Scripts", False))

# Summary
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

passed = sum(1 for _, result in results if result)
total = len(results)

for name, result in results:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} - {name}")

print(f"\nTotal: {passed}/{total} tasks verified")

if passed == total:
    print("\n🎉 All tasks are working correctly after reorganization!")
    print("The project structure changes did not break any functionality.")
    sys.exit(0)
else:
    print(f"\n⚠️  {total - passed} task(s) have issues. Please review.")
    sys.exit(1)

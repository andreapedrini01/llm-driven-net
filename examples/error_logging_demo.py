#!/usr/bin/env python3
"""
Demo per ErrorManager e LoggingManager

Dimostra l'utilizzo integrato dei sistemi di gestione errori e logging
del Network State Collector.
"""

import time
import random
from pathlib import Path

from network_state_collector.error_manager import (
    ErrorManager, ErrorSeverity, ErrorCategory, RetryPolicy
)
from network_state_collector.logging_manager import (
    setup_logging, LogLevel, LogFormat
)


def simulate_network_operation():
    """Simula un'operazione di rete che può fallire"""
    if random.random() < 0.3:  # 30% di probabilità di fallimento
        raise ConnectionError("Network connection failed")
    return {"status": "success", "data": "network_data"}


def simulate_data_processing(data):
    """Simula elaborazione dati che può fallire"""
    if not data or random.random() < 0.2:  # 20% di probabilità di fallimento
        raise ValueError("Invalid data for processing")
    return {"processed": True, "result": f"processed_{data}"}


def simulate_critical_system_error():
    """Simula un errore critico del sistema"""
    raise RuntimeError("Critical system failure - database unavailable")


def critical_error_handler(error_info):
    """Handler per errori critici"""
    print(f"\n🚨 CRITICAL ERROR ALERT 🚨")
    print(f"Component: {error_info.component}")
    print(f"Message: {error_info.message}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error_info.timestamp))}")
    print("Administrator has been notified!")


def main():
    """Funzione principale del demo"""
    print("🔧 Network State Collector - Error Management & Logging Demo")
    print("=" * 60)
    
    # Setup logging con file
    log_file = Path("logs/demo_error_logging.log")
    log_file.parent.mkdir(exist_ok=True)
    
    logging_manager = setup_logging(
        level=LogLevel.DEBUG,
        format_type=LogFormat.JSON,
        file_path=str(log_file),
        console_enabled=True
    )
    
    # Ottieni logger per il demo
    logger = logging_manager.get_logger("demo.error_logging")
    
    # Inizializza ErrorManager
    error_manager = ErrorManager(logger)
    
    # Registra handler per errori critici
    error_manager.add_critical_error_callback(critical_error_handler)
    
    # Configura politiche di retry personalizzate
    error_manager.set_retry_policy(
        ErrorCategory.CONNECTION,
        RetryPolicy(max_attempts=4, base_delay=0.5, max_delay=10.0)
    )
    
    logger.info("Demo started", extra={
        'component': 'demo',
        'context': {'demo_type': 'error_logging'}
    })
    
    print("\n1. Testing successful retry operation...")
    try:
        result = error_manager.retry_with_backoff(
            operation=simulate_network_operation,
            category=ErrorCategory.CONNECTION,
            component="network_client",
            context={"operation": "fetch_topology"}
        )
        logger.info("Network operation succeeded", extra={
            'component': 'network_client',
            'result': result
        })
        print(f"✅ Success: {result}")
    except Exception as e:
        logger.error("Network operation failed completely", extra={
            'component': 'network_client',
            'error': str(e)
        })
        print(f"❌ Failed: {e}")
    
    print("\n2. Testing data processing with error handling...")
    test_data = ["valid_data", None, "more_data"]
    
    for i, data in enumerate(test_data):
        try:
            if data is None:
                # Simula errore di validazione dati
                raise ValueError("Null data received from controller")
            
            result = simulate_data_processing(data)
            logger.info(f"Data processing successful for item {i}", extra={
                'component': 'data_processor',
                'input_data': data,
                'result': result
            })
            print(f"✅ Processed item {i}: {result}")
            
        except Exception as e:
            error_info = error_manager.handle_error(
                exception=e,
                category=ErrorCategory.DATA_VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                component="data_processor",
                context={"item_index": i, "input_data": data}
            )
            print(f"⚠️  Error processing item {i}: {e}")
    
    print("\n3. Testing critical error handling...")
    try:
        simulate_critical_system_error()
    except Exception as e:
        error_manager.handle_error(
            exception=e,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            component="database_manager",
            context={"operation": "connect_to_db"}
        )
    
    print("\n4. Error Statistics:")
    stats = error_manager.get_error_statistics()
    print(f"   Total errors: {stats['total_errors']}")
    print(f"   Critical errors: {stats['critical_errors']}")
    print(f"   Resolved errors: {stats['resolved_errors']}")
    print(f"   Retry attempts: {stats['retry_attempts']}")
    print(f"   Errors by category: {stats['errors_by_category']}")
    print(f"   Errors by severity: {stats['errors_by_severity']}")
    
    print("\n5. Logging Statistics:")
    log_stats = logging_manager.get_log_statistics()
    print(f"   Total log messages: {log_stats['total_messages']}")
    print(f"   Messages by level: {log_stats['by_level']}")
    print(f"   Active loggers: {log_stats['active_loggers']}")
    
    print("\n6. Recent Errors (last hour):")
    recent_errors = error_manager.get_recent_errors(hours=1)
    for error in recent_errors:
        print(f"   - {error.severity.value.upper()}: {error.message} "
              f"({error.component})")
    
    logger.info("Demo completed", extra={
        'component': 'demo',
        'context': {
            'total_errors': stats['total_errors'],
            'total_logs': log_stats['total_messages']
        }
    })
    
    print(f"\n📝 Logs written to: {log_file}")
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
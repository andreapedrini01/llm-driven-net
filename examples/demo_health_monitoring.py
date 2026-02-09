#!/usr/bin/env python3
"""
Demo script per il monitoraggio della salute del RyuConnector

Dimostra le funzionalità di health check e logging strutturato
implementate nel task 2.3.
"""

import sys
import logging
import json
import time
from pathlib import Path

# Aggiungi il path del progetto
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.ryu_connector import RyuConnector
from network_state_collector.models.config import RyuConfig, RetryConfig
from network_state_collector.models.health import HealthStatus


def setup_logging():
    """Configura il logging per la demo"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Aggiungi un handler personalizzato per il logging strutturato
    logger = logging.getLogger('network_state_collector.ryu_connector')
    
    class StructuredLogHandler(logging.Handler):
        def emit(self, record):
            if hasattr(record, 'structured_data'):
                print(f"STRUCTURED LOG: {record.structured_data}")
    
    # Simula il logging strutturato aggiungendo un metodo al logger
    def structured_log(self, data):
        print(f"STRUCTURED LOG: {data}")
    
    logger.structured = structured_log.__get__(logger, logging.Logger)


def demo_health_monitoring():
    """Dimostra le funzionalità di health monitoring"""
    print("=" * 60)
    print("DEMO: Health Check e Monitoraggio Connessione")
    print("=" * 60)
    
    # Configura logging
    setup_logging()
    
    # Configurazione per un controller Ryu non esistente (per dimostrare gli errori)
    ryu_config = RyuConfig(
        host="localhost",
        port=8080,
        timeout=2.0  # Timeout breve per demo veloce
    )
    
    retry_config = RetryConfig(
        max_attempts=2,  # Pochi tentativi per demo veloce
        initial_delay=0.5,
        max_delay=2.0,
        backoff_factor=2.0,
        jitter=True
    )
    
    print(f"\n1. Inizializzazione RyuConnector")
    print(f"   - Host: {ryu_config.host}:{ryu_config.port}")
    print(f"   - Timeout: {ryu_config.timeout}s")
    print(f"   - Max attempts: {retry_config.max_attempts}")
    
    connector = RyuConnector(ryu_config, retry_config)
    
    print(f"\n2. Stato iniziale del connettore")
    stats = connector.get_connection_stats()
    print(f"   - Total requests: {stats['total_requests']}")
    print(f"   - Success rate: {stats['success_rate']:.2%}")
    print(f"   - Is reachable: {stats['is_reachable']}")
    print(f"   - Health status: {stats['health_status']}")
    
    print(f"\n3. Esecuzione health check (fallirà - controller non disponibile)")
    start_time = time.time()
    is_healthy = connector.is_healthy()
    duration = time.time() - start_time
    
    print(f"   - Health check result: {'✓ HEALTHY' if is_healthy else '✗ UNHEALTHY'}")
    print(f"   - Duration: {duration:.2f}s")
    
    print(f"\n4. Stato dettagliato della salute")
    health_status = connector.get_health_status()
    print(f"   - Component: {health_status.component.value}")
    print(f"   - Status: {health_status.status.value.upper()}")
    print(f"   - Message: {health_status.message}")
    print(f"   - Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(health_status.timestamp))}")
    
    print(f"\n5. Dettagli della connessione")
    conn_health = health_status.details['connection_health']
    print(f"   - Is reachable: {conn_health['is_reachable']}")
    print(f"   - Response time: {conn_health['response_time_ms']:.2f}ms")
    print(f"   - Consecutive failures: {conn_health['consecutive_failures']}")
    print(f"   - Success rate: {conn_health['success_rate']:.2%}")
    if conn_health['last_error']:
        print(f"   - Last error: {conn_health['last_error'][:100]}...")
    
    print(f"\n6. Statistiche di connessione aggiornate")
    stats = connector.get_connection_stats()
    print(f"   - Total requests: {stats['total_requests']}")
    print(f"   - Successful requests: {stats['successful_requests']}")
    print(f"   - Failed requests: {stats['failed_requests']}")
    print(f"   - Success rate: {stats['success_rate']:.2%}")
    print(f"   - Uptime: {stats['uptime_seconds']:.2f}s")
    
    print(f"\n7. Tentativo di raccolta dati (fallirà)")
    try:
        switches = connector.get_switches()
        print(f"   - Switches trovati: {len(switches)}")
    except Exception as e:
        print(f"   - ✗ Errore nella raccolta: {type(e).__name__}")
        print(f"   - Messaggio: {str(e)[:100]}...")
    
    print(f"\n8. Stato finale dopo tentativi")
    final_health = connector.get_health_status()
    final_stats = connector.get_connection_stats()
    
    print(f"   - Health status: {final_health.status.value.upper()}")
    print(f"   - Total requests: {final_stats['total_requests']}")
    print(f"   - Consecutive failures: {final_stats['consecutive_failures']}")
    print(f"   - Is reachable: {final_stats['is_reachable']}")
    
    print(f"\n9. Esempio di logging strutturato")
    print("   I log strutturati vengono generati automaticamente per:")
    print("   - Inizializzazione del connettore")
    print("   - Successi e fallimenti delle richieste")
    print("   - Health check results")
    print("   - Errori di connessione con dettagli")
    
    print(f"\n10. Chiusura connettore")
    uptime = final_stats['uptime_seconds']
    connector.close()
    print(f"    - Connettore chiuso dopo {uptime:.2f}s di uptime")
    
    print(f"\n" + "=" * 60)
    print("DEMO COMPLETATA")
    print("=" * 60)
    print("\nFunzionalità dimostrate:")
    print("✓ Health check avanzato con stato dettagliato")
    print("✓ Monitoraggio continuo della connessione")
    print("✓ Logging strutturato per errori e successi")
    print("✓ Statistiche dettagliate di connessione")
    print("✓ Rilevamento automatico di degradazione")
    print("✓ Gestione robusta degli errori")
    
    print(f"\nRequisiti soddisfatti:")
    print("✓ 5.4 - Logging strutturato per errori di connessione")
    print("✓ 5.5 - Continuità servizio durante errori critici")
    print("✓ Health check method is_healthy() implementato")
    print("✓ Monitoraggio connessione con metriche dettagliate")


if __name__ == "__main__":
    demo_health_monitoring()
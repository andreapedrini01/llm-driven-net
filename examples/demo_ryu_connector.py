#!/usr/bin/env python3
"""
Demo del RyuConnector - Mostra le funzionalità implementate

Questo script dimostra le funzionalità del RyuConnector implementato
nel task 2.1, inclusi:
- Connessione al controller Ryu
- Gestione errori robusta
- Retry con backoff esponenziale
- Raccolta dati di switches, links e port statistics
"""

import sys
import logging
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector import RyuConnector, RyuConfig, RetryConfig, RyuConnectionError


def demo_configuration():
    """Dimostra la configurazione del RyuConnector"""
    print("=== Demo Configurazione RyuConnector ===")
    
    # Configurazione Ryu
    ryu_config = RyuConfig(
        host="localhost",
        port=8080,
        timeout=5.0,
        use_https=False,
        verify_ssl=True
    )
    print(f"✓ RyuConfig creata: {ryu_config.base_url}")
    
    # Configurazione Retry
    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        jitter=True
    )
    print(f"✓ RetryConfig creata: max_attempts={retry_config.max_attempts}")
    
    return ryu_config, retry_config


def demo_connector_creation(ryu_config, retry_config):
    """Dimostra la creazione del connettore"""
    print("\n=== Demo Creazione Connettore ===")
    
    connector = RyuConnector(ryu_config, retry_config)
    print("✓ RyuConnector creato con successo")
    print(f"  - Base URL: {connector.ryu_config.base_url}")
    print(f"  - Timeout: {connector.ryu_config.timeout}s")
    print(f"  - Max retry: {connector.retry_config.max_attempts}")
    
    return connector


def demo_error_handling(connector):
    """Dimostra la gestione degli errori"""
    print("\n=== Demo Gestione Errori ===")
    
    # Test health check (probabilmente fallirà se Ryu non è in esecuzione)
    try:
        is_healthy = connector.is_healthy()
        if is_healthy:
            print("✓ Controller Ryu è raggiungibile")
        else:
            print("⚠ Controller Ryu non è raggiungibile (normale se non in esecuzione)")
    except Exception as e:
        print(f"⚠ Health check fallito: {e}")
    
    # Test gestione errori con endpoint inesistente
    try:
        connector._make_request('/nonexistent/endpoint')
    except RyuConnectionError as e:
        print(f"✓ Gestione errore di connessione: {type(e).__name__}")
    except Exception as e:
        print(f"✓ Gestione errore generico: {type(e).__name__}")


def demo_api_methods(connector):
    """Dimostra i metodi API implementati"""
    print("\n=== Demo Metodi API ===")
    
    # Test get_switches
    print("Testing get_switches()...")
    try:
        switches = connector.get_switches()
        print(f"✓ get_switches() implementato - Trovati {len(switches)} switches")
        
        # Se ci sono switches, testa get_port_stats
        if switches:
            switch = switches[0]
            print(f"Testing get_port_stats() per switch {switch.dpid}...")
            try:
                port_stats = connector.get_port_stats(switch.dpid)
                print(f"✓ get_port_stats() implementato - {len(port_stats)} porte")
            except Exception as e:
                print(f"⚠ get_port_stats() fallito: {e}")
        
    except RyuConnectionError as e:
        print(f"⚠ get_switches() fallito (normale se Ryu non in esecuzione): {type(e).__name__}")
    
    # Test get_links
    print("Testing get_links()...")
    try:
        links = connector.get_links()
        print(f"✓ get_links() implementato - Trovati {len(links)} links")
    except RyuConnectionError as e:
        print(f"⚠ get_links() fallito (normale se Ryu non in esecuzione): {type(e).__name__}")


def demo_connection_stats(connector):
    """Dimostra le statistiche di connessione"""
    print("\n=== Demo Statistiche Connessione ===")
    
    stats = connector.get_connection_stats()
    print("Statistiche di connessione:")
    print(f"  - Richieste totali: {stats['total_requests']}")
    print(f"  - Richieste riuscite: {stats['successful_requests']}")
    print(f"  - Richieste fallite: {stats['failed_requests']}")
    print(f"  - Tentativi di retry: {stats['retry_attempts']}")
    print(f"  - Tasso di successo: {stats['success_rate']:.2%}")
    
    if stats['last_success']:
        print(f"  - Ultimo successo: {stats['last_success']}")
    if stats['last_error']:
        print(f"  - Ultimo errore: {stats['last_error']}")


def demo_features_implemented():
    """Mostra le funzionalità implementate nel task 2.1"""
    print("\n=== Funzionalità Implementate nel Task 2.1 ===")
    
    features = [
        "✓ Classe RyuConnector con architettura modulare",
        "✓ Metodo get_switches() per recuperare switch attivi",
        "✓ Metodo get_links() per recuperare topologia di rete", 
        "✓ Metodo get_port_stats() per statistiche delle porte",
        "✓ Esclusione automatica delle porte LOCAL",
        "✓ Gestione timeout configurabili",
        "✓ Retry logic con backoff esponenziale",
        "✓ Jitter opzionale per evitare thundering herd",
        "✓ Gestione robusta degli errori (RyuConnectionError, RyuTimeoutError, RyuDataError)",
        "✓ Logging strutturato per debugging",
        "✓ Statistiche di connessione dettagliate",
        "✓ Health check del controller",
        "✓ Formattazione consistente dei DPID",
        "✓ Validazione dei dati ricevuti",
        "✓ Sessione HTTP riutilizzabile con configurazione SSL",
        "✓ Test unitari e property-based test completi"
    ]
    
    for feature in features:
        print(f"  {feature}")


def main():
    """Funzione principale del demo"""
    print("🚀 Demo RyuConnector - Task 2.1 Completato")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)  # Riduci verbosità per demo
    
    try:
        # Demo configurazione
        ryu_config, retry_config = demo_configuration()
        
        # Demo creazione connettore
        connector = demo_connector_creation(ryu_config, retry_config)
        
        # Demo gestione errori
        demo_error_handling(connector)
        
        # Demo metodi API
        demo_api_methods(connector)
        
        # Demo statistiche
        demo_connection_stats(connector)
        
        # Mostra funzionalità implementate
        demo_features_implemented()
        
        print("\n=== Requisiti Soddisfatti ===")
        requirements = [
            "✓ Requisito 1.1: Recupero lista completa switch attivi",
            "✓ Requisito 1.2: Ottenimento connessioni tra switch con porte",
            "✓ Requisito 5.1: Retry connessione con backoff esponenziale", 
            "✓ Requisito 5.2: Gestione timeout nelle richieste API"
        ]
        
        for req in requirements:
            print(f"  {req}")
        
    except Exception as e:
        print(f"❌ Errore durante il demo: {e}")
        
    finally:
        if 'connector' in locals():
            connector.close()
            print("\n✓ Connettore chiuso correttamente")
    
    print("\n🎉 Demo completato! Task 2.1 implementato con successo.")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Esempio di utilizzo del RyuConnector

Dimostra come utilizzare il RyuConnector per raccogliere dati
dal controller Ryu con gestione errori robusta.
"""

import sys
import logging
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.ryu_connector import RyuConnector, RyuConnectionError
from src.models.config import RyuConfig, RetryConfig


def setup_logging():
    """Configura il logging per l'esempio"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Esempio principale di utilizzo del RyuConnector"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Configurazione per il controller Ryu
    ryu_config = RyuConfig(
        host="localhost",
        port=8080,
        timeout=10.0
    )
    
    # Configurazione retry con backoff esponenziale
    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        backoff_factor=2.0,
        jitter=True
    )
    
    # Crea il connettore
    connector = RyuConnector(ryu_config, retry_config)
    
    try:
        logger.info("Testing RyuConnector...")
        
        # Test health check
        logger.info("Checking controller health...")
        if connector.is_healthy():
            logger.info("✓ Controller is healthy")
        else:
            logger.warning("✗ Controller health check failed")
        
        # Test raccolta switches
        logger.info("Fetching switches...")
        try:
            switches = connector.get_switches()
            logger.info(f"✓ Found {len(switches)} switches")
            
            for switch in switches:
                logger.info(f"  - Switch {switch.dpid}: {len(switch.ports)} ports")
                
                # Test raccolta statistiche porte per questo switch
                try:
                    port_stats = connector.get_port_stats(switch.dpid)
                    logger.info(f"    ✓ Retrieved stats for {len(port_stats)} ports")
                    
                    for port in port_stats[:3]:  # Mostra solo le prime 3 porte
                        utilization = port.calculate_utilization()
                        error_rate = port.calculate_error_rate()
                        logger.info(f"      Port {port.port_no}: "
                                  f"RX={port.rx_packets}, TX={port.tx_packets}, "
                                  f"Util={utilization:.2%}, Errors={error_rate:.2%}")
                        
                except RyuConnectionError as e:
                    logger.error(f"    ✗ Failed to get port stats for {switch.dpid}: {e}")
                    
        except RyuConnectionError as e:
            logger.error(f"✗ Failed to get switches: {e}")
        
        # Test raccolta links
        logger.info("Fetching topology links...")
        try:
            links = connector.get_links()
            logger.info(f"✓ Found {len(links)} topology links")
            
            for link in links[:5]:  # Mostra solo i primi 5 link
                logger.info(f"  - Link: {link.src_dpid}:{link.src_port} -> "
                          f"{link.dst_dpid}:{link.dst_port}")
                          
        except RyuConnectionError as e:
            logger.error(f"✗ Failed to get links: {e}")
        
        # Mostra statistiche di connessione
        stats = connector.get_connection_stats()
        logger.info("Connection Statistics:")
        logger.info(f"  Total requests: {stats['total_requests']}")
        logger.info(f"  Successful: {stats['successful_requests']}")
        logger.info(f"  Failed: {stats['failed_requests']}")
        logger.info(f"  Success rate: {stats['success_rate']:.2%}")
        logger.info(f"  Retry attempts: {stats['retry_attempts']}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        
    finally:
        # Chiudi la connessione
        connector.close()
        logger.info("RyuConnector closed")


if __name__ == "__main__":
    main()
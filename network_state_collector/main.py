"""
Entry point principale per Network State Collector

Fornisce un'interfaccia command-line per utilizzare il collector
in modalità standalone o come servizio.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .models import CollectorConfig
from .collector import NetworkStateCollector


def setup_logging(config: CollectorConfig) -> None:
    """Configura il sistema di logging"""
    log_config = config.logging
    
    # Configura il formato
    formatter = logging.Formatter(log_config.format)
    
    # Configura il logger root
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_config.level.upper()))
    
    # Rimuovi handler esistenti
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler
    if log_config.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_config.file_path:
        log_path = Path(log_config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=log_config.max_file_size,
            backupCount=log_config.backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def create_parser() -> argparse.ArgumentParser:
    """Crea il parser per gli argomenti command-line"""
    parser = argparse.ArgumentParser(
        description="Network State Collector - Raccolta dati di rete per LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:

  # Raccolta singola con configurazione default
  %(prog)s collect

  # Raccolta continua con configurazione personalizzata
  %(prog)s continuous --config config/production.yaml --interval 10

  # Verifica stato di salute
  %(prog)s health --config config/production.yaml

  # Modalità daemon
  %(prog)s daemon --config config/production.yaml
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config/development.yaml",
        help="Path al file di configurazione (default: config/development.yaml)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Abilita output verboso"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandi disponibili")
    
    # Comando collect
    collect_parser = subparsers.add_parser(
        "collect",
        help="Raccoglie un singolo snapshot della rete"
    )
    collect_parser.add_argument(
        "--output", "-o",
        type=str,
        help="File di output per lo snapshot (opzionale)"
    )
    
    # Comando continuous
    continuous_parser = subparsers.add_parser(
        "continuous",
        help="Avvia raccolta continua"
    )
    continuous_parser.add_argument(
        "--interval", "-i",
        type=float,
        help="Intervallo di raccolta in secondi"
    )
    
    # Comando health
    subparsers.add_parser(
        "health",
        help="Verifica lo stato di salute del sistema"
    )
    
    # Comando daemon
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Avvia in modalità daemon"
    )
    daemon_parser.add_argument(
        "--pidfile",
        type=str,
        help="Path al file PID per il daemon"
    )
    
    return parser


def load_config(config_path: str, verbose: bool = False) -> CollectorConfig:
    """Carica la configurazione dal file specificato"""
    try:
        config = CollectorConfig.load_from_file(config_path)
        if verbose:
            print(f"Configurazione caricata da: {config_path}")
        return config
    except FileNotFoundError:
        print(f"Errore: File di configurazione non trovato: {config_path}")
        print("Creazione configurazione di default...")
        
        # Crea configurazione di default
        config = CollectorConfig()
        
        # Crea directory e salva configurazione di esempio
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config.save_to_file(config_path)
        
        print(f"Configurazione di default salvata in: {config_path}")
        return config
    except Exception as e:
        print(f"Errore nel caricamento della configurazione: {e}")
        sys.exit(1)


def cmd_collect(args, config: CollectorConfig) -> int:
    """Esegue raccolta singola"""
    collector = NetworkStateCollector(config)
    
    print("Raccolta snapshot della rete...")
    snapshot = collector.collect_snapshot()
    
    if snapshot is None:
        print("Errore: Impossibile raccogliere snapshot")
        return 1
    
    # Salva snapshot se specificato output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(snapshot.to_json(), encoding='utf-8')
        print(f"Snapshot salvato in: {args.output}")
    else:
        print("Snapshot raccolto con successo")
        print(f"Timestamp: {snapshot.get_timestamp_iso()}")
        print(f"Switch: {len(snapshot.topology.switches)}")
        print(f"Link: {len(snapshot.topology.links)}")
    
    return 0


def cmd_continuous(args, config: CollectorConfig) -> int:
    """Esegue raccolta continua"""
    collector = NetworkStateCollector(config)
    
    interval = args.interval or config.collection.interval
    print(f"Avvio raccolta continua (intervallo: {interval}s)")
    print("Premi Ctrl+C per fermare...")
    
    try:
        collector.start_continuous_collection(interval)
        
        # Loop principale
        while collector.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nFermando raccolta continua...")
        collector.stop_collection()
        print("Raccolta fermata")
    
    return 0


def cmd_health(args, config: CollectorConfig) -> int:
    """Verifica stato di salute"""
    collector = NetworkStateCollector(config)
    
    print("Verifica stato di salute del sistema...")
    health = collector.get_health_status()
    
    print(f"Stato generale: {health.overall_status.value}")
    print(f"Uptime: {health.uptime_seconds:.1f} secondi")
    
    if health.components:
        print("\nComponenti:")
        for name, component in health.components.items():
            status_icon = "✓" if component.status.value == "healthy" else "✗"
            print(f"  {status_icon} {name}: {component.status.value}")
            if component.last_error:
                print(f"    Ultimo errore: {component.last_error}")
    
    unhealthy = health.get_unhealthy_components()
    if unhealthy:
        print(f"\nAttenzione: {len(unhealthy)} componenti non sani")
        return 1
    
    print("\nSistema in salute ✓")
    return 0


def cmd_daemon(args, config: CollectorConfig) -> int:
    """Avvia in modalità daemon"""
    print("Modalità daemon non ancora implementata")
    print("Usa 'continuous' per raccolta continua in foreground")
    return 1


def main() -> int:
    """Entry point principale"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Carica configurazione
    config = load_config(args.config, args.verbose)
    
    # Configura logging
    setup_logging(config)
    
    # Esegui comando
    if args.command == "collect":
        return cmd_collect(args, config)
    elif args.command == "continuous":
        return cmd_continuous(args, config)
    elif args.command == "health":
        return cmd_health(args, config)
    elif args.command == "daemon":
        return cmd_daemon(args, config)
    else:
        print(f"Comando non riconosciuto: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
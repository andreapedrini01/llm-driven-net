#!/usr/bin/env python3
"""
Demo per ConfigurationManager

Dimostra le funzionalità del Configuration Manager:
- Caricamento configurazioni da file
- Validazione configurazioni
- Override da variabili d'ambiente
- Gestione ambienti multipli
- Hot reload delle configurazioni
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.configuration_manager import ConfigurationManager
from src.models.config import CollectorConfig


def demo_basic_usage():
    """Demo utilizzo base del ConfigurationManager"""
    print("=== Demo Utilizzo Base ConfigurationManager ===")
    
    # Crea manager con directory di configurazione esistente
    manager = ConfigurationManager("config")
    
    try:
        # Carica configurazione development
        print("\n1. Caricamento configurazione development...")
        config = manager.load_config(environment="development")
        print(f"   ✓ Configurazione caricata: {config.environment}")
        print(f"   ✓ Ryu endpoint: {manager.get_ryu_endpoint()}")
        print(f"   ✓ Output directory: {manager.get_output_directory()}")
        print(f"   ✓ Collection interval: {manager.get_collection_interval()}s")
        
        # Mostra configurazione corrente
        print(f"\n2. Configurazione corrente:")
        current = manager.get_current_config()
        print(f"   - Environment: {current.environment}")
        print(f"   - Ryu host: {current.ryu.host}:{current.ryu.port}")
        print(f"   - Log level: {current.logging.level}")
        print(f"   - Continuous mode: {current.collection.continuous_mode}")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_validation():
    """Demo validazione configurazioni"""
    print("\n=== Demo Validazione Configurazioni ===")
    
    manager = ConfigurationManager()
    
    # Test configurazione valida
    print("\n1. Validazione configurazione valida...")
    valid_config = CollectorConfig()
    result = manager.validate_config(valid_config)
    print(f"   ✓ Configurazione valida: {result.is_valid}")
    print(f"   ✓ Errori: {len(result.errors)}")
    print(f"   ✓ Warning: {len(result.warnings)}")
    
    # Test configurazione invalida
    print("\n2. Validazione configurazione invalida...")
    invalid_config = CollectorConfig()
    invalid_config.ryu.host = ""  # Host vuoto
    invalid_config.ryu.port = 70000  # Porta invalida
    invalid_config.retry.max_attempts = 0  # Tentativi invalidi
    invalid_config.output.directory = ""  # Directory vuota
    
    result = manager.validate_config(invalid_config)
    print(f"   ✗ Configurazione valida: {result.is_valid}")
    print(f"   ✗ Errori trovati: {len(result.errors)}")
    for i, error in enumerate(result.errors, 1):
        print(f"      {i}. {error}")
    
    # Test configurazione con warning
    print("\n3. Validazione configurazione con warning...")
    warning_config = CollectorConfig()
    warning_config.ryu.use_https = True
    warning_config.ryu.verify_ssl = False  # HTTPS senza SSL verification
    warning_config.collection.interval = 0.5  # Intervallo molto basso
    
    result = manager.validate_config(warning_config)
    print(f"   ⚠ Configurazione valida: {result.is_valid}")
    print(f"   ⚠ Warning trovati: {len(result.warnings)}")
    for i, warning in enumerate(result.warnings, 1):
        print(f"      {i}. {warning}")


def demo_environment_overrides():
    """Demo override da variabili d'ambiente"""
    print("\n=== Demo Override Variabili d'Ambiente ===")
    
    # Imposta variabili d'ambiente
    env_vars = {
        'NSC_RYU_HOST': 'env-override-host',
        'NSC_RYU_PORT': '9999',
        'NSC_RYU_TIMEOUT': '45.0',
        'NSC_RYU_USE_HTTPS': 'true',
        'NSC_OUTPUT_DIR': '/tmp/env-override',
        'NSC_COLLECTION_INTERVAL': '15.0',
        'NSC_LOG_LEVEL': 'DEBUG'
    }
    
    print("\n1. Impostazione variabili d'ambiente...")
    for var, value in env_vars.items():
        os.environ[var] = value
        print(f"   {var} = {value}")
    
    try:
        manager = ConfigurationManager("config")
        
        print("\n2. Caricamento configurazione con override...")
        config = manager.load_config(environment="development")
        
        print("\n3. Verifica override applicati:")
        print(f"   ✓ Ryu host: {config.ryu.host} (era: localhost)")
        print(f"   ✓ Ryu port: {config.ryu.port} (era: 8080)")
        print(f"   ✓ Ryu timeout: {config.ryu.timeout} (era: 30.0)")
        print(f"   ✓ Ryu HTTPS: {config.ryu.use_https} (era: False)")
        print(f"   ✓ Output dir: {config.output.directory} (era: data)")
        print(f"   ✓ Collection interval: {config.collection.interval} (era: 30.0)")
        print(f"   ✓ Log level: {config.logging.level} (era: DEBUG)")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")
    finally:
        # Pulisci variabili d'ambiente
        for var in env_vars:
            os.environ.pop(var, None)


def demo_multiple_environments():
    """Demo gestione ambienti multipli"""
    print("\n=== Demo Gestione Ambienti Multipli ===")
    
    manager = ConfigurationManager("config")
    
    # Lista ambienti disponibili
    print("\n1. Ambienti disponibili:")
    environments = manager.list_available_environments()
    for env in environments:
        print(f"   - {env}")
    
    # Crea configurazioni per diversi ambienti
    print("\n2. Creazione configurazioni per ambienti:")
    
    # Development
    dev_config = manager.create_environment_config("development")
    print(f"   ✓ Development: log_level={dev_config.logging.level}, "
          f"continuous={dev_config.collection.continuous_mode}, "
          f"interval={dev_config.collection.interval}s")
    
    # Production
    prod_config = manager.create_environment_config("production")
    print(f"   ✓ Production: log_level={prod_config.logging.level}, "
          f"continuous={prod_config.collection.continuous_mode}, "
          f"interval={prod_config.collection.interval}s")
    
    # Testing
    test_config = manager.create_environment_config("testing")
    print(f"   ✓ Testing: log_level={test_config.logging.level}, "
          f"file_path={test_config.logging.file_path}, "
          f"interval={test_config.collection.interval}s")


def demo_hot_reload():
    """Demo hot reload delle configurazioni"""
    print("\n=== Demo Hot Reload Configurazioni ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = ConfigurationManager(str(temp_path))
        
        # Crea configurazione iniziale
        print("\n1. Creazione configurazione iniziale...")
        initial_config = {
            "environment": "test",
            "ryu": {"host": "initial-host", "port": 8080},
            "collection": {"interval": 30.0}
        }
        
        config_file = temp_path / "test.yaml"
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Carica configurazione
        config = manager.load_config(str(config_file))
        print(f"   ✓ Host iniziale: {config.ryu.host}")
        print(f"   ✓ Intervallo iniziale: {config.collection.interval}s")
        
        # Modifica configurazione
        print("\n2. Modifica configurazione...")
        time.sleep(0.1)  # Assicura timestamp diverso
        
        modified_config = initial_config.copy()
        modified_config["ryu"]["host"] = "modified-host"
        modified_config["collection"]["interval"] = 15.0
        
        with open(config_file, 'w') as f:
            yaml.dump(modified_config, f)
        
        # Test reload
        print("\n3. Test hot reload...")
        reloaded = manager.reload_config()
        
        if reloaded:
            new_config = manager.get_current_config()
            print(f"   ✓ Configurazione ricaricata!")
            print(f"   ✓ Nuovo host: {new_config.ryu.host}")
            print(f"   ✓ Nuovo intervallo: {new_config.collection.interval}s")
        else:
            print("   ✗ Configurazione non ricaricata")


def demo_save_load_cycle():
    """Demo ciclo completo salvataggio/caricamento"""
    print("\n=== Demo Ciclo Salvataggio/Caricamento ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        manager = ConfigurationManager(str(temp_path))
        
        # Crea configurazione personalizzata
        print("\n1. Creazione configurazione personalizzata...")
        custom_config = CollectorConfig()
        custom_config.environment = "custom"
        custom_config.ryu.host = "custom-ryu-host"
        custom_config.ryu.port = 9090
        custom_config.collection.interval = 20.0
        custom_config.logging.level = "WARNING"
        
        print(f"   ✓ Environment: {custom_config.environment}")
        print(f"   ✓ Ryu: {custom_config.ryu.host}:{custom_config.ryu.port}")
        print(f"   ✓ Interval: {custom_config.collection.interval}s")
        print(f"   ✓ Log level: {custom_config.logging.level}")
        
        # Salva configurazione
        print("\n2. Salvataggio configurazione...")
        manager.save_environment_config("custom", custom_config)
        
        config_file = temp_path / "custom.yaml"
        print(f"   ✓ Salvata in: {config_file}")
        print(f"   ✓ File esiste: {config_file.exists()}")
        
        # Ricarica configurazione
        print("\n3. Ricaricamento configurazione...")
        loaded_config = manager.load_config(environment="custom")
        
        print(f"   ✓ Environment: {loaded_config.environment}")
        print(f"   ✓ Ryu: {loaded_config.ryu.host}:{loaded_config.ryu.port}")
        print(f"   ✓ Interval: {loaded_config.collection.interval}s")
        print(f"   ✓ Log level: {loaded_config.logging.level}")
        
        # Verifica equivalenza
        print("\n4. Verifica equivalenza...")
        configs_match = (
            custom_config.environment == loaded_config.environment and
            custom_config.ryu.host == loaded_config.ryu.host and
            custom_config.ryu.port == loaded_config.ryu.port and
            custom_config.collection.interval == loaded_config.collection.interval and
            custom_config.logging.level == loaded_config.logging.level
        )
        print(f"   ✓ Configurazioni equivalenti: {configs_match}")


def main():
    """Esegue tutte le demo"""
    print("🔧 Demo ConfigurationManager - Network State Collector")
    print("=" * 60)
    
    try:
        demo_basic_usage()
        demo_validation()
        demo_environment_overrides()
        demo_multiple_environments()
        demo_hot_reload()
        demo_save_load_cycle()
        
        print("\n" + "=" * 60)
        print("✅ Tutte le demo completate con successo!")
        
    except Exception as e:
        print(f"\n❌ Errore durante l'esecuzione delle demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
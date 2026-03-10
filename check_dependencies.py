#!/usr/bin/env python3
"""
Script per verificare che tutte le dipendenze necessarie siano installate
"""

import sys
import importlib
from typing import List, Tuple

# Dipendenze critiche per main.py
CRITICAL_DEPENDENCIES = [
    ("asyncio", "asyncio"),
    ("json", "json"),
    ("logging", "logging"),
    ("pathlib", "pathlib"),
    ("datetime", "datetime"),
]

# Dipendenze dei moduli
MODULE_DEPENDENCIES = [
    # network_state_collector
    ("network_state_collector.collector", "NetworkStateCollector"),
    ("src.models", "CollectorConfig"),
    
    # src/services (LLM module)
    ("src.services.intent_parser", "IntentParser"),
    ("src.services.chatgpt_client", "ChatGPTClient"),
    ("src.services.context_analyzer", "ContextAnalyzer"),
    ("src.services.action_sequencer", "ActionSequencer"),
    ("src.services.validator", "Validator"),
    ("src.services.action_output", "ActionOutputService"),
    ("src.services.prompt_engineering", "PromptEngineeringSystem"),
    
    # northbound_script_generator
    ("northbound_script_generator.action_processor", "ActionProcessor"),
    ("northbound_script_generator.models", "NetworkAction"),
]

# Dipendenze esterne
EXTERNAL_DEPENDENCIES = [
    ("pydantic", "Pydantic"),
    ("yaml", "PyYAML"),
    ("dotenv", "python-dotenv"),
    ("requests", "requests"),
    ("httpx", "httpx"),
    ("openai", "openai"),
    ("aiohttp", "aiohttp"),
    ("structlog", "structlog"),
]


def check_import(module_name: str, display_name: str) -> Tuple[bool, str]:
    """
    Verifica se un modulo può essere importato
    
    Returns:
        (success, error_message)
    """
    try:
        importlib.import_module(module_name)
        return True, ""
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def main():
    """Verifica tutte le dipendenze"""
    print("=" * 60)
    print("Verifica Dipendenze - Network Monitoring Integration")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # Verifica dipendenze critiche
    print("1. Dipendenze Python Standard:")
    for module_name, display_name in CRITICAL_DEPENDENCIES:
        success, error = check_import(module_name, display_name)
        if success:
            print(f"  ✓ {display_name}")
        else:
            print(f"  ✗ {display_name}: {error}")
            all_ok = False
    print()
    
    # Verifica dipendenze esterne
    print("2. Dipendenze Esterne:")
    missing_external = []
    for module_name, display_name in EXTERNAL_DEPENDENCIES:
        success, error = check_import(module_name, display_name)
        if success:
            print(f"  ✓ {display_name}")
        else:
            print(f"  ✗ {display_name}: {error}")
            missing_external.append(display_name)
            all_ok = False
    print()
    
    # Verifica moduli del progetto
    print("3. Moduli del Progetto:")
    missing_modules = []
    for module_name, display_name in MODULE_DEPENDENCIES:
        success, error = check_import(module_name, display_name)
        if success:
            print(f"  ✓ {display_name}")
        else:
            print(f"  ✗ {display_name}: {error}")
            missing_modules.append(module_name)
            all_ok = False
    print()
    
    # Riepilogo
    print("=" * 60)
    if all_ok:
        print("✓ Tutte le dipendenze sono installate!")
        print()
        print("Puoi avviare l'applicazione con:")
        print("  python main.py")
    else:
        print("✗ Alcune dipendenze mancano")
        print()
        
        if missing_external:
            print("Installa le dipendenze esterne con:")
            print("  pip install -r requirements.txt")
            print()
            print("Oppure solo le dipendenze minime:")
            print("  pip install -r requirements-minimal.txt")
            print()
        
        if missing_modules:
            print("Moduli del progetto mancanti:")
            for module in missing_modules:
                print(f"  - {module}")
            print()
            print("Assicurati di essere nella directory root del progetto")
            print("e che tutti i moduli siano presenti.")
    
    print("=" * 60)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

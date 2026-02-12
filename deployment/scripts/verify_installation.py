#!/usr/bin/env python3
"""Script per verificare che l'installazione sia completa e corretta."""

import sys
import os
from pathlib import Path

# Colori per output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_success(message):
    """Stampa messaggio di successo."""
    print(f"{GREEN}✓{RESET} {message}")


def print_error(message):
    """Stampa messaggio di errore."""
    print(f"{RED}✗{RESET} {message}")


def print_warning(message):
    """Stampa messaggio di warning."""
    print(f"{YELLOW}⚠{RESET} {message}")


def print_header(message):
    """Stampa header."""
    print(f"\n{BOLD}{message}{RESET}")
    print("=" * 60)


def check_python_version():
    """Verifica versione Python."""
    print_header("1. Verifica Versione Python")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 10:
        print_success(f"Python {version_str} (>= 3.10 richiesto)")
        return True
    else:
        print_error(f"Python {version_str} (>= 3.10 richiesto)")
        return False


def check_dependencies():
    """Verifica dipendenze installate."""
    print_header("2. Verifica Dipendenze")
    
    required_packages = {
        'fastapi': '0.104.1',
        'pydantic': '2.5.0',
        'openai': '1.54.0',
        'hypothesis': '6.119.4',
        'pytest': '8.3.4',
        'httpx': '0.25.2',
        'structlog': '24.5.0',
        'python-dotenv': '1.0.0'
    }
    
    all_installed = True
    
    for package, min_version in required_packages.items():
        try:
            # Prova a importare il modulo
            module_name = package.replace('-', '_')
            if package == 'python-dotenv':
                module_name = 'dotenv'
            __import__(module_name)
            print_success(f"{package} installato")
        except ImportError:
            print_error(f"{package} NON installato (>= {min_version} richiesto)")
            all_installed = False
    
    return all_installed


def check_env_file():
    """Verifica file .env."""
    print_header("3. Verifica File di Configurazione")
    
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    if not env_path.exists():
        print_error("File .env non trovato")
        if env_example_path.exists():
            print_warning("Copia .env.example in .env e configuralo")
        return False
    
    print_success("File .env trovato")
    
    # Verifica contenuto
    with open(env_path, 'r') as f:
        content = f.read()
    
    required_vars = [
        'OPENAI_API_KEY',
        'OPENAI_MODEL'
    ]
    
    all_vars_present = True
    for var in required_vars:
        if var in content and not content.split(f'{var}=')[1].split('\n')[0].strip().startswith('#'):
            print_success(f"  {var} configurato")
        else:
            print_error(f"  {var} NON configurato")
            all_vars_present = False
    
    return all_vars_present


def check_openai_connection():
    """Verifica connessione OpenAI."""
    print_header("4. Verifica Connessione ChatGPT API")
    
    try:
        from dotenv import load_dotenv
        import openai
        
        load_dotenv()
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print_error("OPENAI_API_KEY non trovata nel file .env")
            return False
        
        if api_key.startswith('sk-proj-') or api_key.startswith('sk-'):
            print_success("Formato API key valido")
        else:
            print_warning("Formato API key potrebbe essere non valido")
        
        # Test connessione (opzionale, commentato per evitare costi)
        # client = openai.OpenAI(api_key=api_key)
        # response = client.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[{"role": "user", "content": "test"}],
        #     max_tokens=5
        # )
        # print_success("Connessione ChatGPT API funzionante")
        
        print_warning("Test connessione API saltato (per evitare costi)")
        print_warning("Esegui 'python scripts/test_chatgpt_connection.py' per testare")
        
        return True
        
    except ImportError as e:
        print_error(f"Errore import: {e}")
        return False
    except Exception as e:
        print_error(f"Errore: {e}")
        return False


def check_project_structure():
    """Verifica struttura del progetto."""
    print_header("5. Verifica Struttura Progetto")
    
    required_dirs = [
        'src',
        'src/models',
        'src/services',
        'tests',
        'scripts'
    ]
    
    required_files = [
        'src/__init__.py',
        'src/main.py',
        'src/config.py',
        'requirements.txt',
        'README.md'
    ]
    
    all_present = True
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"Directory {dir_path}/ presente")
        else:
            print_error(f"Directory {dir_path}/ mancante")
            all_present = False
    
    for file_path in required_files:
        if Path(file_path).exists():
            print_success(f"File {file_path} presente")
        else:
            print_error(f"File {file_path} mancante")
            all_present = False
    
    return all_present


def check_tests():
    """Verifica che i test possano essere eseguiti."""
    print_header("6. Verifica Test")
    
    try:
        import pytest
        print_success("pytest installato")
        
        # Conta i file di test
        test_files = list(Path('tests').glob('test_*.py'))
        print_success(f"{len(test_files)} file di test trovati")
        
        print_warning("Esegui 'pytest' per eseguire tutti i test")
        
        return True
        
    except ImportError:
        print_error("pytest non installato")
        return False


def main():
    """Funzione principale."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Verifica Installazione LLM Integration Module{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    checks = [
        check_python_version(),
        check_dependencies(),
        check_env_file(),
        check_openai_connection(),
        check_project_structure(),
        check_tests()
    ]
    
    # Riepilogo
    print_header("Riepilogo")
    
    passed = sum(checks)
    total = len(checks)
    
    print(f"\nControlli superati: {passed}/{total}")
    
    if passed == total:
        print(f"\n{GREEN}{BOLD}✓ Installazione completa e corretta!{RESET}")
        print("\nProssimi passi:")
        print("  1. Esegui i test: pytest")
        print("  2. Avvia l'applicazione: python -m src.main")
        print("  3. Consulta README.md per ulteriori informazioni")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ Installazione incompleta{RESET}")
        print("\nRisolvi i problemi evidenziati sopra.")
        print("Consulta INSTALL.md per istruzioni dettagliate.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

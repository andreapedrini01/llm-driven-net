"""
Script di installazione per gestire dipendenze con build problematici (es. ryu).
Uso: python install.py
"""
import subprocess
import sys


def pip_install(*args):
    """Esegue pip install con gli argomenti forniti."""
    cmd = [sys.executable, "-m", "pip", "install", *args]
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"ERRORE: comando fallito con codice {result.returncode}")
        sys.exit(1)


def main():
    # Step 1: setuptools e pbr compatibili con ryu
    print("\n=== Step 1: Installazione setuptools e pbr compatibili ===")
    pip_install("setuptools==67.6.1", "pbr", "wheel")

    # Step 2: ryu senza build isolation (usa il setuptools appena installato)
    print("\n=== Step 2: Installazione ryu (no build isolation) ===")
    pip_install("--no-build-isolation", "ryu>=4.34")

    # Step 3: tutte le altre dipendenze
    print("\n=== Step 3: Installazione dipendenze rimanenti ===")
    pip_install("-r", "requirements.txt")

    print("\n=== Installazione completata con successo ===")


if __name__ == "__main__":
    main()

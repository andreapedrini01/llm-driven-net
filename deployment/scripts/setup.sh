#!/bin/bash
# Script di setup automatico per Linux/macOS

set -e  # Exit on error

echo "=========================================="
echo "  LLM Integration Module - Setup"
echo "=========================================="
echo ""

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funzioni helper
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_step() {
    echo ""
    echo "[$1] $2"
    echo "----------------------------------------"
}

# 1. Verifica Python
print_step "1/6" "Verifica Python"

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 non trovato. Installa Python 3.10 o superiore."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python $PYTHON_VERSION trovato"

# 2. Crea ambiente virtuale
print_step "2/6" "Creazione ambiente virtuale"

if [ -d "venv" ]; then
    print_warning "Ambiente virtuale già esistente"
    read -p "Vuoi ricrearlo? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        print_success "Ambiente virtuale ricreato"
    fi
else
    python3 -m venv venv
    print_success "Ambiente virtuale creato"
fi

# 3. Attiva ambiente virtuale
print_step "3/6" "Attivazione ambiente virtuale"

source venv/bin/activate
print_success "Ambiente virtuale attivato"

# 4. Aggiorna pip
print_step "4/6" "Aggiornamento pip"

python -m pip install --upgrade pip --quiet
print_success "pip aggiornato"

# 5. Installa dipendenze
print_step "5/6" "Installazione dipendenze"

read -p "Installare dipendenze di sviluppo? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -r requirements-dev.txt --quiet
    print_success "Dipendenze di sviluppo installate"
else
    pip install -r requirements.txt --quiet
    print_success "Dipendenze di produzione installate"
fi

# 6. Configura .env
print_step "6/6" "Configurazione file .env"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "File .env creato da .env.example"
        print_warning "IMPORTANTE: Configura OPENAI_API_KEY nel file .env"
    else
        print_error "File .env.example non trovato"
    fi
else
    print_warning "File .env già esistente"
fi

# Verifica installazione
echo ""
echo "=========================================="
echo "  Verifica Installazione"
echo "=========================================="
echo ""

python scripts/verify_installation.py

# Istruzioni finali
echo ""
echo "=========================================="
echo "  Setup Completato!"
echo "=========================================="
echo ""
echo "Prossimi passi:"
echo "  1. Attiva l'ambiente virtuale:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Configura il file .env con la tua OPENAI_API_KEY"
echo ""
echo "  3. Esegui i test:"
echo "     pytest"
echo ""
echo "  4. Avvia l'applicazione:"
echo "     python -m src.main"
echo ""

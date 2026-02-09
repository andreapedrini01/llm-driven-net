#!/bin/bash
# Script per deployare il Network State Collector su Multipass VM

set -e  # Exit on error

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurazione
VM_NAME="${1:-ryu-vm}"
PROJECT_DIR="$(pwd)"
VM_PROJECT_DIR="/home/ubuntu/network-state-collector"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Network State Collector Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Funzione per stampare messaggi
print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Verifica che Multipass sia installato
print_step "Verifica Multipass..."
if ! command -v multipass &> /dev/null; then
    print_error "Multipass non trovato. Installalo con: brew install multipass"
    exit 1
fi
print_success "Multipass installato"

# 2. Verifica che la VM esista
print_step "Verifica VM '$VM_NAME'..."
if ! multipass list | grep -q "$VM_NAME"; then
    print_warning "VM '$VM_NAME' non trovata"
    read -p "Vuoi crearla? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Creazione VM '$VM_NAME'..."
        multipass launch --name "$VM_NAME" --cpus 2 --memory 4G --disk 20G ubuntu:22.04
        print_success "VM creata"
    else
        print_error "Deployment annullato"
        exit 1
    fi
fi

# 3. Avvia la VM se non è running
VM_STATE=$(multipass list | grep "$VM_NAME" | awk '{print $2}')
if [ "$VM_STATE" != "Running" ]; then
    print_step "Avvio VM..."
    multipass start "$VM_NAME"
    sleep 3
fi
print_success "VM '$VM_NAME' in esecuzione"

# 4. Ottieni IP della VM
VM_IP=$(multipass info "$VM_NAME" | grep IPv4 | awk '{print $2}')
print_success "IP VM: $VM_IP"

# 5. Crea archivio del progetto
print_step "Creazione archivio progetto..."
ARCHIVE_NAME="network-collector-$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "/tmp/$ARCHIVE_NAME" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.hypothesis' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='data/llm_output/*' \
    --exclude='data/history/*' \
    --exclude='logs/*' \
    -C "$PROJECT_DIR" .
print_success "Archivio creato: /tmp/$ARCHIVE_NAME"

# 6. Trasferisci archivio alla VM
print_step "Trasferimento archivio alla VM..."
multipass transfer "/tmp/$ARCHIVE_NAME" "$VM_NAME:/home/ubuntu/"
print_success "Archivio trasferito"

# 7. Setup nella VM
print_step "Setup ambiente nella VM..."
multipass exec "$VM_NAME" -- bash << 'EOF'
set -e

# Colori
GREEN='\033[0;32m'
NC='\033[0m'

echo "📦 Installazione dipendenze sistema..."
sudo apt update -qq
sudo apt install -y python3 python3-pip python3-venv > /dev/null 2>&1

echo "📂 Preparazione directory..."
mkdir -p ~/network-state-collector
cd ~/network-state-collector

# Estrai archivio
ARCHIVE=$(ls /home/ubuntu/network-collector-*.tar.gz | head -1)
if [ -f "$ARCHIVE" ]; then
    tar -xzf "$ARCHIVE"
    rm "$ARCHIVE"
fi

echo "🐍 Creazione virtual environment..."
python3 -m venv venv

echo "📥 Installazione dipendenze Python..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q

echo "📁 Creazione directory..."
mkdir -p data/llm_output data/history logs config

echo -e "${GREEN}✓ Setup completato${NC}"
EOF
print_success "Setup completato"

# 8. Crea configurazione per la VM
print_step "Creazione configurazione..."
multipass exec "$VM_NAME" -- bash << 'EOF'
cat > ~/network-state-collector/config/vm_config.yaml << 'YAML'
ryu:
  host: "localhost"
  port: 8080
  timeout: 10.0

output:
  directory: "data"
  pretty_print: true

collection:
  interval: 5.0
  validate_data: true
  parallel_collection: true

logging:
  level: "INFO"
  file_path: "logs/collector.log"
  console_output: true

environment: "production"
YAML
EOF
print_success "Configurazione creata"

# 9. Crea script di test nella VM
print_step "Creazione script di test..."
multipass exec "$VM_NAME" -- bash << 'EOF'
cat > ~/network-state-collector/test_vm.sh << 'SCRIPT'
#!/bin/bash
cd ~/network-state-collector
source venv/bin/activate

echo "🧪 Test Network State Collector"
echo "================================"
echo ""

# Verifica Ryu
echo "📡 Verifica Ryu Controller..."
if curl -s http://localhost:8080/stats/switches > /dev/null 2>&1; then
    echo "   ✓ Ryu Controller raggiungibile"
    
    # Esegui test
    echo ""
    echo "📸 Raccolta snapshot..."
    python test_collector_live.py
else
    echo "   ✗ Ryu Controller non raggiungibile"
    echo ""
    echo "💡 Avvia Ryu con:"
    echo "   ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest --verbose"
    exit 1
fi
SCRIPT

chmod +x ~/network-state-collector/test_vm.sh
EOF
print_success "Script di test creato"

# 10. Verifica installazione
print_step "Verifica installazione..."
multipass exec "$VM_NAME" -- bash << 'EOF'
cd ~/network-state-collector
source venv/bin/activate
python -c "from network_state_collector.collector import NetworkStateCollector; print('✓ Import OK')"
EOF
print_success "Installazione verificata"

# 11. Cleanup
rm "/tmp/$ARCHIVE_NAME"

# 12. Riepilogo
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ Deployment Completato!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📋 Informazioni VM:${NC}"
echo "   Nome: $VM_NAME"
echo "   IP: $VM_IP"
echo "   Directory: $VM_PROJECT_DIR"
echo ""
echo -e "${BLUE}🚀 Prossimi Passi:${NC}"
echo ""
echo "1. Accedi alla VM:"
echo -e "   ${YELLOW}multipass shell $VM_NAME${NC}"
echo ""
echo "2. Installa Ryu (se non già installato):"
echo -e "   ${YELLOW}sudo pip3 install ryu${NC}"
echo ""
echo "3. Avvia Ryu Controller:"
echo -e "   ${YELLOW}ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest --verbose${NC}"
echo ""
echo "4. In un altro terminale, avvia Mininet:"
echo -e "   ${YELLOW}multipass shell $VM_NAME${NC}"
echo -e "   ${YELLOW}sudo mn --controller=remote,ip=127.0.0.1,port=6653 --topo=linear,3${NC}"
echo ""
echo "5. In un terzo terminale, esegui il collector:"
echo -e "   ${YELLOW}multipass shell $VM_NAME${NC}"
echo -e "   ${YELLOW}cd ~/network-state-collector && ./test_vm.sh${NC}"
echo ""
echo -e "${BLUE}📊 Per recuperare i dati dal Mac:${NC}"
echo -e "   ${YELLOW}multipass transfer $VM_NAME:$VM_PROJECT_DIR/data/llm_output/network_context_latest.json ./${NC}"
echo ""
echo -e "${BLUE}📖 Documentazione completa:${NC}"
echo -e "   ${YELLOW}cat DEPLOYMENT_MULTIPASS.md${NC}"
echo ""

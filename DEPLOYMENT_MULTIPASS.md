# 🚀 Deployment su Multipass VM

Guida completa per deployare e usare il Network State Collector su una VM Multipass con Mininet e Ryu Controller.

## 📋 Prerequisiti

- Multipass installato sul tuo Mac
- VM con Ubuntu (consigliato: Ubuntu 22.04 LTS)
- Mininet installato nella VM
- Ryu Controller installato nella VM

## 🔧 Setup VM Multipass

### 1. Crea/Avvia la VM

```bash
# Crea una nuova VM (se non esiste già)
multipass launch --name ryu-vm --cpus 2 --memory 4G --disk 20G

# Oppure avvia una VM esistente
multipass start ryu-vm

# Accedi alla VM
multipass shell ryu-vm
```

### 2. Installa Dipendenze nella VM

```bash
# Aggiorna il sistema
sudo apt update && sudo apt upgrade -y

# Installa Python e pip
sudo apt install -y python3 python3-pip python3-venv git

# Installa Mininet (se non già installato)
sudo apt install -y mininet

# Installa Ryu Controller
sudo pip3 install ryu

# Verifica installazioni
python3 --version
ryu --version
mn --version
```

## 📦 Trasferimento Codice alla VM

### Opzione 1: Trasferimento Diretto (Consigliato)

Dal tuo Mac, nella directory del progetto:

```bash
# Crea un archivio del progetto (escludendo venv e cache)
tar -czf network-collector.tar.gz \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.hypothesis' \
  --exclude='*.pyc' \
  --exclude='.git' \
  .

# Trasferisci alla VM
multipass transfer network-collector.tar.gz ryu-vm:/home/ubuntu/

# Accedi alla VM ed estrai
multipass shell ryu-vm
cd ~
tar -xzf network-collector.tar.gz
cd network-state-collector  # o il nome della directory estratta
```

### Opzione 2: Git Clone (se hai un repository)

```bash
# Nella VM
cd ~
git clone <your-repo-url> network-state-collector
cd network-state-collector
```

### Opzione 3: Mount Directory (per sviluppo)

```bash
# Dal Mac - monta la directory del progetto nella VM
multipass mount /path/to/your/project ryu-vm:/home/ubuntu/network-state-collector

# Accedi alla VM
multipass shell ryu-vm
cd ~/network-state-collector
```

## 🔨 Setup Ambiente nella VM

```bash
# Nella VM, nella directory del progetto
cd ~/network-state-collector

# Crea virtual environment
python3 -m venv venv

# Attiva venv
source venv/bin/activate

# Installa dipendenze
pip install --upgrade pip
pip install -r requirements.txt

# Installa il package in modalità development
pip install -e .

# Verifica installazione
python -c "from network_state_collector.collector import NetworkStateCollector; print('✓ Import OK')"
```

## 🌐 Configurazione Rete

### 1. Trova l'IP della VM

```bash
# Dal Mac
multipass info ryu-vm | grep IPv4

# Oppure nella VM
hostname -I
```

Esempio output: `192.168.64.5`

### 2. Crea Configurazione per la VM

Nella VM, crea un file di configurazione:

```bash
# Nella VM
cd ~/network-state-collector
mkdir -p config
nano config/vm_config.yaml
```

Contenuto di `config/vm_config.yaml`:

```yaml
ryu:
  host: "localhost"  # Ryu gira sulla stessa VM
  port: 8080
  timeout: 10.0

output:
  directory: "/home/ubuntu/network-data"
  pretty_print: true

collection:
  interval: 5.0
  validate_data: true
  parallel_collection: true

logging:
  level: "INFO"
  file_path: "/home/ubuntu/logs/collector.log"
  console_output: true

environment: "production"
```

## 🚀 Avvio Sistema

### 1. Avvia Ryu Controller

In un terminale della VM:

```bash
# Nella VM
ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest --verbose
```

Dovresti vedere:
```
loading app ryu.app.simple_switch_13
loading app ryu.app.ofctl_rest
instantiating app ryu.app.simple_switch_13
instantiating app ryu.app.ofctl_rest
```

### 2. Avvia Mininet (in un altro terminale)

Apri un nuovo terminale nella VM:

```bash
# Dal Mac
multipass shell ryu-vm

# Nella VM - avvia una topologia semplice
sudo mn --controller=remote,ip=127.0.0.1,port=6653 --topo=tree,depth=2,fanout=2 --mac --switch=ovsk,protocols=OpenFlow13

# Oppure una topologia lineare
sudo mn --controller=remote,ip=127.0.0.1,port=6653 --topo=linear,3 --mac --switch=ovsk,protocols=OpenFlow13
```

Nella CLI di Mininet, testa la connettività:

```bash
mininet> pingall
mininet> h1 ping -c 3 h2
```

### 3. Avvia il Collector (in un terzo terminale)

Apri un altro terminale nella VM:

```bash
# Dal Mac
multipass shell ryu-vm

# Nella VM
cd ~/network-state-collector
source venv/bin/activate

# Test singolo snapshot
python test_collector_live.py

# Oppure raccolta continua
python test_continuous_collection.py
```

## 📊 Verifica Output

### Controlla i File Generati

```bash
# Nella VM
ls -lh data/llm_output/
cat data/llm_output/network_context_latest.json | python3 -m json.tool

# Conta snapshot raccolti
ls data/llm_output/*.json | wc -l
```

### Monitora in Tempo Reale

```bash
# Nella VM
watch -n 2 'ls -lh data/llm_output/ | tail -5'

# Oppure monitora il file latest
watch -n 2 'cat data/llm_output/network_context_latest.json | python3 -m json.tool | head -30'
```

## 🔄 Accesso ai Dati dal Mac

### Opzione 1: Trasferimento File

```bash
# Dal Mac - copia i JSON dalla VM al Mac
multipass transfer ryu-vm:/home/ubuntu/network-state-collector/data/llm_output/network_context_latest.json ./

# Oppure copia tutta la directory
multipass transfer -r ryu-vm:/home/ubuntu/network-state-collector/data/llm_output ./collected_data/
```

### Opzione 2: Mount Directory (accesso diretto)

```bash
# Dal Mac - monta la directory data dalla VM
multipass mount ryu-vm:/home/ubuntu/network-state-collector/data ./vm_data

# Ora puoi accedere ai file direttamente
cat vm_data/llm_output/network_context_latest.json
```

### Opzione 3: HTTP Server (per accesso web)

Nella VM:

```bash
# Nella VM - avvia un server HTTP nella directory data
cd ~/network-state-collector/data/llm_output
python3 -m http.server 8000
```

Dal Mac:

```bash
# Trova l'IP della VM
VM_IP=$(multipass info ryu-vm | grep IPv4 | awk '{print $2}')

# Scarica il file
curl http://$VM_IP:8000/network_context_latest.json -o latest_snapshot.json

# Oppure apri nel browser
open http://$VM_IP:8000/
```

## 🧪 Test Completo End-to-End

Script di test completo nella VM:

```bash
#!/bin/bash
# test_e2e.sh

echo "🚀 Test End-to-End Network State Collector"
echo "=========================================="

# 1. Verifica Ryu
echo "📡 Verifica Ryu Controller..."
curl -s http://localhost:8080/stats/switches > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✓ Ryu Controller attivo"
else
    echo "   ✗ Ryu Controller non raggiungibile"
    exit 1
fi

# 2. Verifica Mininet
echo "🌐 Verifica Mininet..."
sudo ovs-vsctl show > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ Mininet attivo"
else
    echo "   ✗ Mininet non attivo"
    exit 1
fi

# 3. Esegui collector
echo "📸 Raccolta snapshot..."
cd ~/network-state-collector
source venv/bin/activate
python test_collector_live.py

# 4. Verifica output
echo "📊 Verifica output..."
if [ -f "data/llm_output/network_context_latest.json" ]; then
    echo "   ✓ JSON generato con successo"
    echo ""
    echo "📄 Contenuto:"
    cat data/llm_output/network_context_latest.json | python3 -m json.tool | head -20
else
    echo "   ✗ JSON non trovato"
    exit 1
fi

echo ""
echo "✅ Test completato con successo!"
```

Rendi eseguibile ed esegui:

```bash
chmod +x test_e2e.sh
./test_e2e.sh
```

## 🐛 Troubleshooting

### Problema: Ryu non raggiungibile

```bash
# Verifica che Ryu sia in ascolto
sudo netstat -tlnp | grep 8080

# Testa manualmente le API
curl http://localhost:8080/stats/switches
curl http://localhost:8080/v1.0/topology/links
```

### Problema: Mininet non connesso a Ryu

```bash
# Nella CLI di Mininet, verifica controller
mininet> net

# Riavvia Mininet con controller esplicito
sudo mn -c  # pulisci
sudo mn --controller=remote,ip=127.0.0.1,port=6653 --topo=linear,3
```

### Problema: Permessi file

```bash
# Assicurati che le directory siano scrivibili
chmod -R 755 ~/network-state-collector/data
mkdir -p ~/network-state-collector/logs
chmod 755 ~/network-state-collector/logs
```

### Problema: Import errors

```bash
# Reinstalla il package
cd ~/network-state-collector
source venv/bin/activate
pip install -e . --force-reinstall
```

## 📝 Script di Avvio Automatico

Crea uno script per avviare tutto automaticamente:

```bash
#!/bin/bash
# start_all.sh

echo "🚀 Avvio Network State Collector Environment"

# Avvia Ryu in background
echo "📡 Avvio Ryu Controller..."
ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest --verbose > ~/logs/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

# Avvia Mininet in background
echo "🌐 Avvio Mininet..."
sudo mn --controller=remote,ip=127.0.0.1,port=6653 --topo=tree,depth=2,fanout=2 --mac --switch=ovsk,protocols=OpenFlow13 &
MININET_PID=$!
sleep 5

# Avvia Collector
echo "📊 Avvio Collector..."
cd ~/network-state-collector
source venv/bin/activate
python test_continuous_collection.py

# Cleanup on exit
trap "sudo mn -c; kill $RYU_PID; exit" INT TERM
```

## 🎯 Prossimi Passi

1. **Integra con il tuo LLM**: Usa i JSON generati per alimentare i tuoi modelli
2. **Automatizza la raccolta**: Configura cron job o systemd service
3. **Monitora le performance**: Analizza i dati raccolti nel tempo
4. **Estendi le metriche**: Aggiungi metriche personalizzate se necessario

## 📚 Comandi Utili

```bash
# Stato VM
multipass list
multipass info ryu-vm

# Stop/Start VM
multipass stop ryu-vm
multipass start ryu-vm

# Pulizia Mininet
sudo mn -c

# Logs
tail -f ~/logs/collector.log
tail -f ~/logs/ryu.log

# Spazio disco
df -h
du -sh ~/network-state-collector/data/
```

---

**Buon deployment! 🚀**

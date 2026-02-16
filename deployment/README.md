# Deployment - LLM Integration Module

Questa cartella contiene tutte le risorse necessarie per il deployment del modulo LLM in vari ambienti.

## 📁 Struttura

```
deployment/
├── kubernetes/      # Manifests Kubernetes
├── docker/          # Configurazione Docker
├── monitoring/      # Setup monitoring (Prometheus)
└── scripts/         # Script deployment e utility
```

## 🚀 Quick Start

### Docker Locale
```bash
cd deployment/docker
docker-compose up -d
```

### Kubernetes
```bash
cd deployment/kubernetes
kubectl apply -f .
```

## 📦 Componenti

### Kubernetes (`kubernetes/`)
Manifests per deployment su cluster Kubernetes:

- **deployment.yaml** - Deployment principale dell'applicazione
- **hpa.yaml** - Horizontal Pod Autoscaler
- **ingress.yaml** - Ingress per routing esterno
- **secrets-template.yaml** - Template per secrets (da configurare)
- **README.md** - Guida dettagliata Kubernetes

**Setup**:
```bash
# 1. Configura secrets
cp kubernetes/secrets-template.yaml kubernetes/secrets.yaml
# Modifica secrets.yaml con i tuoi valori

# 2. Applica secrets
kubectl apply -f kubernetes/secrets.yaml

# 3. Deploy applicazione
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/hpa.yaml
kubectl apply -f kubernetes/ingress.yaml
```

### Docker (`docker/`)
Configurazione per container Docker:

- **Dockerfile** - Immagine Docker dell'applicazione
- **docker-compose.yml** - Orchestrazione multi-container

**Build e Run**:
```bash
# Build immagine
docker build -t llm-integration-module:latest -f docker/Dockerfile .

# Run con docker-compose
cd docker
docker-compose up -d

# Logs
docker-compose logs -f

# Stop
docker-compose down
```

### Monitoring (`monitoring/`)
Setup monitoring con Prometheus:

- **prometheus.yml** - Configurazione Prometheus
- **alerts.yml** - Regole alerting

**Metriche Esposte**:
- `llm_module_intents_total` - Intent processati
- `llm_module_actions_total` - Azioni generate
- `llm_module_processing_seconds` - Tempo elaborazione
- `llm_module_anomalies_total` - Anomalie rilevate

**Accesso Metriche**:
```
http://localhost:8000/metrics
```

### Scripts (`scripts/`)
Script utility per deployment e gestione:

- **deploy.sh** / **deploy.bat** - Script deployment automatico
- **setup.sh** / **setup.bat** - Setup iniziale ambiente
- **health_check.py** - Health check applicazione
- **config_manager.py** - Gestione configurazioni
- **secrets_manager.py** - Gestione secrets
- **verify_installation.py** - Verifica installazione
- **verify_chatgpt_client.py** - Test connessione ChatGPT
- **test_chatgpt_connection.py** - Test API ChatGPT

**Uso**:
```bash
# Linux/Mac
./scripts/deploy.sh

# Windows
scripts\deploy.bat

# Health check
python scripts/health_check.py

# Verifica installazione
python scripts/verify_installation.py
```

## 🌍 Ambienti

### Development
```bash
# Usa configurazione dev
export ENV=dev
docker-compose -f docker/docker-compose.yml up
```

### Staging
```bash
# Usa configurazione staging
export ENV=staging
kubectl apply -f kubernetes/ --namespace=staging
```

### Production
```bash
# Usa configurazione production
export ENV=prod
kubectl apply -f kubernetes/ --namespace=production
```

## ⚙️ Configurazione

### Variabili d'Ambiente
Le configurazioni per ambiente sono in `../config/`:
- `dev.env` - Sviluppo
- `staging.env` - Staging
- `prod.env` - Produzione

### Secrets
**IMPORTANTE**: Non committare mai secrets reali!

1. Copia template: `cp kubernetes/secrets-template.yaml kubernetes/secrets.yaml`
2. Modifica con valori reali
3. Applica: `kubectl apply -f kubernetes/secrets.yaml`

**Secrets richiesti**:
- `OPENAI_API_KEY` - Chiave API OpenAI
- `JWT_SECRET_KEY` - Chiave JWT
- `ADMIN_PASSWORD` - Password admin
- `OPERATOR_PASSWORD` - Password operator
- `VIEWER_PASSWORD` - Password viewer

## 🔍 Monitoring e Logging

### Health Checks
```bash
# Health check base
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/health/ready

# Liveness check
curl http://localhost:8080/health/live
```

### Logs
```bash
# Docker
docker-compose logs -f

# Kubernetes
kubectl logs -f deployment/llm-integration-module

# Logs specifici
kubectl logs -f <pod-name>
```

### Metriche Prometheus
```bash
# Accedi a Prometheus
http://localhost:9090

# Query esempio
llm_module_intents_total
rate(llm_module_processing_seconds[5m])
```

## 🔧 Troubleshooting

### Container non si avvia
```bash
# Verifica logs
docker logs <container-id>

# Verifica configurazione
docker inspect <container-id>

# Verifica network
docker network ls
```

### Pod Kubernetes in CrashLoopBackOff
```bash
# Verifica logs
kubectl logs <pod-name>

# Descrivi pod
kubectl describe pod <pod-name>

# Verifica secrets
kubectl get secrets
```

### Problemi di Connessione
```bash
# Test connessione ChatGPT
python scripts/test_chatgpt_connection.py

# Verifica network
kubectl get svc
kubectl get ingress
```

## 📊 Scaling

### Manuale
```bash
# Docker
docker-compose up --scale app=3

# Kubernetes
kubectl scale deployment llm-integration-module --replicas=3
```

### Automatico (HPA)
L'HPA è configurato per scalare automaticamente basandosi su:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)
- Custom metrics (request rate)

```bash
# Verifica HPA
kubectl get hpa

# Descrivi HPA
kubectl describe hpa llm-integration-module
```

## 🔐 Security

### Best Practices
1. ✅ Usa secrets per dati sensibili
2. ✅ Abilita HTTPS in produzione
3. ✅ Limita accesso network con NetworkPolicy
4. ✅ Usa immagini Docker verificate
5. ✅ Aggiorna regolarmente dipendenze
6. ✅ Monitora vulnerabilità con scanner

### Network Policies
```bash
# Applica network policy
kubectl apply -f kubernetes/network-policy.yaml
```

## 📚 Documentazione Dettagliata

- **[Deployment Guide](../docs/deployment/DEPLOYMENT.md)** - Guida completa
- **[Deployment Architecture](../docs/DEPLOYMENT_ARCHITECTURE.md)** - Architettura
- **[Kubernetes README](kubernetes/README.md)** - Dettagli Kubernetes
- **[Scripts README](scripts/README.md)** - Dettagli script

## 🆘 Supporto

Per problemi di deployment:
1. Controlla i logs
2. Verifica configurazione e secrets
3. Consulta la documentazione
4. Esegui health checks

---

**Nota**: Testa sempre in ambiente dev/staging prima di deployare in produzione!

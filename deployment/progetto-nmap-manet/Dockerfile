# Partiamo da un'immagine leggera con Python
FROM python:3.9-slim

# Installiamo nmap direttamente nel sistema operativo del container
RUN apt-get update && apt-get install -y nmap iproute2 net-tools iputils-ping curl && rm -rf /var/lib/apt/lists/*

# Cartella di lavoro interna
WORKDIR /app

# Copiamo i file creati sopra dentro il container
COPY . /app

# Installiamo le librerie Python
RUN pip install --no-cache-dir -r requirements.txt

# Apriamo la porta per il Web Server
EXPOSE 5000

# Avviamo l'applicazione
CMD ["python", "app.py"]

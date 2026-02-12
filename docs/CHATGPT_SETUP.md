# ChatGPT API Setup Guide

## Overview

Il modulo LLM Integration utilizza esclusivamente ChatGPT API di OpenAI per interpretare intent di rete e generare azioni di configurazione.

## Ottenere una API Key

1. Vai su [OpenAI Platform](https://platform.openai.com/)
2. Crea un account o effettua il login
3. Naviga su [API Keys](https://platform.openai.com/api-keys)
4. Clicca su "Create new secret key"
5. Copia la chiave (la vedrai solo una volta!)

## Configurazione

### 1. Crea il file .env

Copia il file `.env.example` in `.env`:

```bash
copy .env.example .env
```

### 2. Configura la tua API Key

Apri il file `.env` e sostituisci `your-openai-api-key-here` con la tua chiave API:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
```

### 3. Scegli il modello

Il sistema supporta tre modelli ChatGPT:

#### GPT-4-turbo (Raccomandato)
- **Bilanciamento ottimale** tra qualità, velocità e costo
- Context window: 128k token
- Latenza: ~2-5 secondi
- Costo: ~$0.01 input / $0.03 output per 1K token

```env
OPENAI_MODEL=gpt-4-turbo
```

#### GPT-4
- **Massima qualità** e accuratezza
- Context window: 8k-32k token
- Latenza: ~5-10 secondi
- Costo: ~$0.03 input / $0.06 output per 1K token

```env
OPENAI_MODEL=gpt-4
```

#### GPT-3.5-turbo
- **Velocità massima**, costo minimo
- Context window: 16k token
- Latenza: ~1-2 secondi
- Costo: ~$0.0005 input / $0.0015 output per 1K token

```env
OPENAI_MODEL=gpt-3.5-turbo
```

## Parametri Avanzati

### Temperature
Controlla la creatività delle risposte (0.0 = deterministico, 1.0 = creativo):

```env
OPENAI_TEMPERATURE=0.1
```

Per networking, si raccomanda un valore basso (0.1-0.3) per risposte più precise.

### Max Tokens
Numero massimo di token nella risposta:

```env
OPENAI_MAX_TOKENS=2000
```

### Rate Limiting
Richieste massime al minuto:

```env
OPENAI_RATE_LIMIT_RPM=60
```

### Timeout e Retry
```env
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3
```

## Verifica della Configurazione

Per verificare che la configurazione funzioni:

```python
from src.services.chatgpt_client import ChatGPTClient, ChatGPTConfig
import asyncio

async def test_connection():
    config = ChatGPTConfig(
        api_key="your-api-key",
        model="gpt-4-turbo"
    )
    
    client = ChatGPTClient(config=config)
    
    response = await client.generate_response(
        "Say 'Connection successful!'"
    )
    
    print(f"Response: {response.content}")
    print(f"Tokens used: {response.tokens_used}")
    print(f"Cost: ${client._total_cost:.4f}")

asyncio.run(test_connection())
```

## Gestione dei Costi

### Monitoraggio
Il client traccia automaticamente:
- Numero totale di richieste
- Token utilizzati
- Costo stimato

Accedi alle statistiche con:

```python
stats = client.get_stats()
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Total tokens: {stats['total_tokens']}")
```

### Budget Alerts
Configura alert quando si avvicinano soglie di costo (da implementare nel task 6.3).

### Best Practices per Ridurre i Costi

1. **Usa GPT-3.5-turbo** per operazioni semplici
2. **Cache delle risposte** per intent simili
3. **Ottimizza i prompt** per ridurre token
4. **Batch requests** quando possibile
5. **Monitora l'utilizzo** regolarmente

## Troubleshooting

### Errore: "Invalid API Key"
- Verifica che la chiave sia corretta
- Controlla che non ci siano spazi extra
- Assicurati che la chiave non sia scaduta

### Errore: "Rate Limit Exceeded"
- Il client gestisce automaticamente con retry
- Riduci `OPENAI_RATE_LIMIT_RPM` se necessario
- Considera un piano con limiti più alti

### Errore: "Insufficient Quota"
- Aggiungi crediti al tuo account OpenAI
- Verifica il billing su [OpenAI Platform](https://platform.openai.com/account/billing)

### Timeout Errors
- Aumenta `OPENAI_TIMEOUT`
- Verifica la connessione internet
- Prova con un modello più veloce (gpt-3.5-turbo)

## Sicurezza

⚠️ **IMPORTANTE**: Non committare mai il file `.env` con la tua API key!

Il file `.gitignore` è già configurato per escludere `.env`, ma verifica sempre prima di fare commit:

```bash
git status
```

Se accidentalmente committi la chiave:
1. Revoca immediatamente la chiave su OpenAI Platform
2. Genera una nuova chiave
3. Rimuovi la chiave dalla history di Git

## Limiti e Quote

OpenAI applica limiti basati sul piano:

- **Free tier**: Limiti molto bassi, solo per testing
- **Pay-as-you-go**: Limiti più alti, scala con l'uso
- **Enterprise**: Limiti personalizzati

Controlla i tuoi limiti su: https://platform.openai.com/account/limits

## Supporto

Per problemi con l'API OpenAI:
- [OpenAI Documentation](https://platform.openai.com/docs)
- [OpenAI Community](https://community.openai.com/)
- [OpenAI Support](https://help.openai.com/)

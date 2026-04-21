# ChatGPT API Setup

The LLM Integration Module uses the OpenAI API to interpret network intents and generate configuration actions when the rule-based engine doesn't have enough confidence.

## Getting an API Key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Create an account or log in
3. Navigate to [API Keys](https://platform.openai.com/api-keys)
4. Click "Create new secret key" and copy it

## Configuration

Copy `.env_example` to `.env` and set your key:

```bash
cp .env_example .env
```

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-5.4-nano
OPENAI_MAX_TOKENS=6000
OPENAI_TEMPERATURE=0.1
```

### Model

The app has been tested with `gpt-5.4-nano`, which is the default. It offers a good balance of cost and quality — costs are low enough that we set `OPENAI_MAX_TOKENS=6000` to get more detailed responses, especially for nmap security scan summaries from Docker hosts.

For networking tasks, keep temperature low (0.1-0.3) for more precise responses.

### Optional Parameters

```env
OPENAI_RATE_LIMIT_RPM=60    # Max requests per minute
OPENAI_TIMEOUT=30            # Request timeout in seconds
OPENAI_MAX_RETRIES=3         # Retry attempts on failure
```

## How It's Used

The app uses ChatGPT in two scenarios:

1. **Low confidence intents** — when the rule-based parser scores below 0.8, the intent is sent to ChatGPT with network context for action generation
2. **Fallback** — when rule-based generation produces only generic actions, ChatGPT takes over

You can test the connection from the CLI:

```
> intent create slice between h1 h2 with bandwidth at 10 mbps
```

If confidence is high enough, the rule-based engine handles it directly without calling the API.

## Cost Tracking

The `ChatGPTClient` tracks usage automatically:

```python
from llm_integration_module.services.chatgpt_client import ChatGPTClient

client = ChatGPTClient()
stats = client.get_stats()
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Total tokens: {stats['total_tokens']}")
```

Budget alerts trigger at configurable thresholds (default: $10 warning, $50 critical).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API Key" | Check for extra spaces in `.env`, verify key is active |
| "Rate Limit Exceeded" | Client retries automatically; lower `OPENAI_RATE_LIMIT_RPM` if needed |
| "Insufficient Quota" | Add credits at [platform.openai.com/account/billing](https://platform.openai.com/account/billing) |
| Timeout errors | Increase `OPENAI_TIMEOUT` |

## Security

Never commit `.env` to version control. The `.gitignore` already excludes it, but always double-check before pushing.

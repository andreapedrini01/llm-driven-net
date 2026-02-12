# ChatGPT API Setup Guide

## Overview

The LLM Integration module uses exclusively ChatGPT API from OpenAI to interpret network intents and generate configuration actions.

## Getting an API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an account or log in
3. Navigate to [API Keys](https://platform.openai.com/api-keys)
4. Click on "Create new secret key"
5. Copy the key (you'll only see it once!)

## Configuration

### 1. Create the .env file

Copy the `.env.example` file to `.env`:

```bash
copy .env.example .env
```

### 2. Configure your API Key

Open the `.env` file and replace `your-openai-api-key-here` with your API key:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
```

### 3. Choose the model

The system supports three ChatGPT models:

#### GPT-4-turbo (Recommended)
- **Optimal balance** between quality, speed and cost
- Context window: 128k tokens
- Latency: ~2-5 seconds
- Cost: ~$0.01 input / $0.03 output per 1K tokens

```env
OPENAI_MODEL=gpt-4-turbo
```

#### GPT-4
- **Maximum quality** and accuracy
- Context window: 8k-32k tokens
- Latency: ~5-10 seconds
- Cost: ~$0.03 input / $0.06 output per 1K tokens

```env
OPENAI_MODEL=gpt-4
```

#### GPT-3.5-turbo
- **Maximum speed**, minimum cost
- Context window: 16k tokens
- Latency: ~1-2 seconds
- Cost: ~$0.0005 input / $0.0015 output per 1K tokens

```env
OPENAI_MODEL=gpt-3.5-turbo
```

## Advanced Parameters

### Temperature
Controls response creativity (0.0 = deterministic, 1.0 = creative):

```env
OPENAI_TEMPERATURE=0.1
```

For networking, a low value (0.1-0.3) is recommended for more precise responses.

### Max Tokens
Maximum number of tokens in the response:

```env
OPENAI_MAX_TOKENS=2000
```

### Rate Limiting
Maximum requests per minute:

```env
OPENAI_RATE_LIMIT_RPM=60
```

### Timeout and Retry
```env
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3
```

## Configuration Verification

To verify that the configuration works:

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

## Cost Management

### Monitoring
The client automatically tracks:
- Total number of requests
- Tokens used
- Estimated cost

Access statistics with:

```python
stats = client.get_stats()
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Total tokens: {stats['total_tokens']}")
```

### Budget Alerts
Configure alerts when approaching cost thresholds (to be implemented in task 6.3).

### Best Practices to Reduce Costs

1. **Use GPT-3.5-turbo** for simple operations
2. **Cache responses** for similar intents
3. **Optimize prompts** to reduce tokens
4. **Batch requests** when possible
5. **Monitor usage** regularly

## Troubleshooting

### Error: "Invalid API Key"
- Verify the key is correct
- Check for extra spaces
- Make sure the key hasn't expired

### Error: "Rate Limit Exceeded"
- The client handles automatically with retry
- Reduce `OPENAI_RATE_LIMIT_RPM` if necessary
- Consider a plan with higher limits

### Error: "Insufficient Quota"
- Add credits to your OpenAI account
- Check billing on [OpenAI Platform](https://platform.openai.com/account/billing)

### Timeout Errors
- Increase `OPENAI_TIMEOUT`
- Verify internet connection
- Try with a faster model (gpt-3.5-turbo)

## Security

⚠️ **IMPORTANT**: Never commit the `.env` file with your API key!

The `.gitignore` file is already configured to exclude `.env`, but always verify before committing:

```bash
git status
```

If you accidentally commit the key:
1. Immediately revoke the key on OpenAI Platform
2. Generate a new key
3. Remove the key from Git history

## Limits and Quotas

OpenAI applies limits based on the plan:

- **Free tier**: Very low limits, only for testing
- **Pay-as-you-go**: Higher limits, scales with usage
- **Enterprise**: Custom limits

Check your limits at: https://platform.openai.com/account/limits

## Support

For issues with the OpenAI API:
- [OpenAI Documentation](https://platform.openai.com/docs)
- [OpenAI Community](https://community.openai.com/)
- [OpenAI Support](https://help.openai.com/)

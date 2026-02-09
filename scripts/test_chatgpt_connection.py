"""
Script to test ChatGPT API connection.

Usage:
    python scripts/test_chatgpt_connection.py

Make sure to set OPENAI_API_KEY in your .env file first!
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.chatgpt_client import ChatGPTClient, ChatGPTConfig
from src.config import get_settings


async def test_connection():
    """Test ChatGPT API connection."""
    
    settings = get_settings()
    
    # Check if API key is configured
    if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key-here":
        print("❌ Error: OPENAI_API_KEY not configured!")
        print("\nPlease:")
        print("1. Copy .env.example to .env")
        print("2. Add your OpenAI API key to .env")
        print("3. Run this script again")
        return False
    
    print("🔄 Testing ChatGPT API connection...")
    print(f"Model: {settings.openai_model}")
    print(f"API Key: {settings.openai_api_key[:20]}...")
    print()
    
    try:
        # Create client
        config = ChatGPTConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature
        )
        
        client = ChatGPTClient(config=config)
        
        # Test simple request
        print("📤 Sending test request...")
        response = await client.generate_response(
            "Respond with exactly: 'Connection successful!'"
        )
        
        print("✅ Connection successful!")
        print()
        print(f"Response: {response.content}")
        print(f"Model: {response.model}")
        print(f"Tokens used: {response.tokens_used}")
        print(f"Latency: {response.latency:.2f}s")
        print(f"Finish reason: {response.finish_reason}")
        print()
        
        # Show stats
        stats = client.get_stats()
        print("📊 Client Statistics:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
        print(f"  Available: {stats['is_available']}")
        print()
        
        # Test with context
        print("📤 Testing with network context...")
        context = {
            "network_state": "active",
            "topology": "mesh",
            "switches": 5
        }
        
        response2 = await client.generate_response(
            "Summarize the network state in one sentence",
            context=context
        )
        
        print(f"Response: {response2.content}")
        print(f"Tokens used: {response2.tokens_used}")
        print()
        
        # Final stats
        stats = client.get_stats()
        print("📊 Final Statistics:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
        print()
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print()
        print("Common issues:")
        print("- Invalid API key")
        print("- Insufficient quota/credits")
        print("- Network connectivity issues")
        print("- Rate limit exceeded")
        return False


def main():
    """Main entry point."""
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

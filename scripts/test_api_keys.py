"""Quick API key validation test."""

import asyncio
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()


async def test_deepseek():
    key = os.getenv("DEEPSEEK_API_KEY", "")
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Say hi"}],
                "max_tokens": 10,
            },
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        text = await resp.text()
        print(f"DeepSeek: status={resp.status}")
        print(f"  Response: {text[:200]}")


async def test_perplexity():
    key = os.getenv("PERPLEXITY_API_KEY", "")
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://api.perplexity.ai/chat/completions",
            json={
                "model": "sonar-pro",
                "messages": [{"role": "user", "content": "Say hi"}],
                "max_tokens": 10,
            },
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        text = await resp.text()
        print(f"Perplexity: status={resp.status}")
        print(f"  Response: {text[:200]}")


async def test_qwen():
    key = os.getenv("QWEN_API_KEY", "")
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": "Say hi"}],
                "max_tokens": 10,
            },
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        text = await resp.text()
        print(f"Qwen: status={resp.status}")
        print(f"  Response: {text[:200]}")


async def main():
    print("=== API Key Validation ===\n")
    await test_deepseek()
    print()
    await test_perplexity()
    print()
    await test_qwen()


if __name__ == "__main__":
    asyncio.run(main())

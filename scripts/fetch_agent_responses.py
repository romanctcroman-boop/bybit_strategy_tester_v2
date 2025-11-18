import asyncio
import httpx
from datetime import datetime, timezone

async def fetch_responses():
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Get previous DeepSeek response
        r1 = await client.post(
            "http://127.0.0.1:8000/api/v1/agent/send",
            json={
                "from_agent": "copilot",
                "to_agent": "deepseek",
                "message_type": "query",
                "content": "Please repeat your full technical review response from the previous staging deployment report, including all circuit breaker and semaphore recommendations."
            }
        )
        
        # Get previous Perplexity response
        r2 = await client.post(
            "http://127.0.0.1:8000/api/v1/agent/send",
            json={
                "from_agent": "copilot",
                "to_agent": "perplexity",
                "message_type": "query",
                "content": "Please repeat your full best practices validation response from the previous staging deployment report, including API key auth and rate limiting recommendations."
            }
        )
        
        deepseek_content = r1.json().get("content", "[ERROR: No content]")
        perplexity_content = r2.json().get("content", "[ERROR: No content]")
        
        # Append to feedback file
        with open("AGENT_FEEDBACK_STAGING_DEPLOYMENT.md", "a", encoding="utf-8") as f:
            f.write(f"\n\n{'='*70}\n")
            f.write(f"AGENT FEEDBACK UPDATE - {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"{'='*70}\n\n")
            
            f.write("## DeepSeek Technical Review (Full Response)\n\n")
            f.write(deepseek_content)
            f.write("\n\n")
            
            f.write("## Perplexity Best Practices Review (Full Response)\n\n")
            f.write(perplexity_content)
            f.write("\n")
        
        print("✅ Saved full agent responses to AGENT_FEEDBACK_STAGING_DEPLOYMENT.md")

if __name__ == "__main__":
    asyncio.run(fetch_responses())

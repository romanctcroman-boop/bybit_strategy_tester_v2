"""
Parallel Audit Submission with 12 API Keys
===========================================

Strategy:
- DeepSeek: 8 parallel requests using 8 API keys simultaneously
- Perplexity: 4 parallel requests using 4 API keys simultaneously
- Total: 12 concurrent API calls for maximum throughput
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from simplified_reliable_mcp import SimplifiedReliableMCP

def split_into_sections(text: str, num_sections: int) -> list[str]:
    """Split text into N roughly equal sections by paragraph boundaries"""
    paragraphs = text.split('\n\n')
    total_paras = len(paragraphs)
    paras_per_section = total_paras // num_sections
    
    sections = []
    current_idx = 0
    
    for i in range(num_sections):
        # Last section gets remaining paragraphs
        if i == num_sections - 1:
            section_paras = paragraphs[current_idx:]
        else:
            section_paras = paragraphs[current_idx:current_idx + paras_per_section]
            current_idx += paras_per_section
        
        sections.append('\n\n'.join(section_paras))
    
    return sections

def create_parallel_prompts(sections: list[str], agent: str, total: int) -> list[str]:
    """Create prompts for parallel processing"""
    prompts = []
    
    for i, section in enumerate(sections, 1):
        prompt = f"""# {agent} AI - Parallel Audit Part {i}/{total}

**Task:** Analyze Phase 1-3 implementation (part {i} of {total})

**Your Role:** Code quality expert validating against your original recommendations

**Analysis Required:**
1. Code Quality Score (1-10)
2. Compliance with your recommendations
3. Security vulnerabilities (if any)
4. Performance issues (if any)
5. Critical gaps

{'=' * 70}
{section}
{'=' * 70}

**Output Format:**
```json
{{
  "part": {i},
  "code_quality": <1-10>,
  "compliance_percentage": <0-100>,
  "critical_issues": ["issue1", "issue2"],
  "recommendations": ["rec1", "rec2"],
  "security_score": <1-10>
}}
```

Note: Part {i}/{total} - Final summary will aggregate all parts.
"""
        prompts.append(prompt)
    
    return prompts

async def parallel_deepseek_audit(
    server: SimplifiedReliableMCP,
    audit_text: str,
    num_requests: int,
):
    """Send N parallel requests to DeepSeek using different API keys"""
    print(f"\n{'=' * 70}")
    print(f"🟣 DEEPSEEK PARALLEL AUDIT ({num_requests} concurrent requests)")
    print(f"{'=' * 70}")
    print(f"Original size: {len(audit_text):,} chars")
    
    # Split into sections for num_requests API keys
    sections = split_into_sections(audit_text, num_sections=num_requests)
    prompts = create_parallel_prompts(sections, "DeepSeek", total=num_requests)
    
    print(f"Split into: {num_requests} sections")
    for i, (section, prompt) in enumerate(zip(sections, prompts), 1):
        print(f"  Part {i}: {len(section):,} chars → prompt {len(prompt):,} chars")
    
    # Create parallel tasks (each uses different API key automatically via rotation)
    print(f"\n🚀 Launching {num_requests} parallel requests...")
    tasks = [
        server.send_to_deepseek(prompt) 
        for prompt in prompts
    ]
    
    # Execute all simultaneously
    start_time = datetime.now()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n✅ Completed in {elapsed:.1f}s")
    
    # Process results
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"  Part {i}/{num_requests}: ❌ Error: {result}")
        elif "error" in result:
            print(f"  Part {i}/{num_requests}: ❌ Failed: {result.get('error', 'Unknown')}")
        else:
            try:
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"  Part {i}/{num_requests}: ✅ Success ({len(content):,} chars)")
                success_count += 1
            except:
                print(f"  Part {i}/{num_requests}: ⚠️ Received but parsing failed")
    
    print(f"\n📊 Success Rate: {success_count}/{num_requests} ({success_count/num_requests*100:.0f}%)")
    
    return results

async def parallel_perplexity_audit(
    server: SimplifiedReliableMCP,
    audit_text: str,
    num_requests: int,
):
    """Send N parallel requests to Perplexity using different API keys"""
    print(f"\n{'=' * 70}")
    print(f"🔵 PERPLEXITY PARALLEL AUDIT ({num_requests} concurrent requests)")
    print(f"{'=' * 70}")
    print(f"Original size: {len(audit_text):,} chars")
    
    # Split into sections for num_requests API keys
    sections = split_into_sections(audit_text, num_sections=num_requests)
    prompts = create_parallel_prompts(sections, "Perplexity", total=num_requests)
    
    print(f"Split into: {num_requests} sections")
    for i, (section, prompt) in enumerate(zip(sections, prompts), 1):
        print(f"  Part {i}: {len(section):,} chars → prompt {len(prompt):,} chars")
    
    # Create parallel tasks
    print(f"\n🚀 Launching {num_requests} parallel requests...")
    tasks = [
        server.send_to_perplexity(prompt) 
        for prompt in prompts
    ]
    
    # Execute simultaneously
    start_time = datetime.now()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n✅ Completed in {elapsed:.1f}s")
    
    # Process results
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"  Part {i}/{num_requests}: ❌ Error: {result}")
        elif "error" in result:
            print(f"  Part {i}/{num_requests}: ❌ Failed: {result.get('error', 'Unknown')}")
        else:
            try:
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"  Part {i}/{num_requests}: ✅ Success ({len(content):,} chars)")
                success_count += 1
            except:
                print(f"  Part {i}/{num_requests}: ⚠️ Received but parsing failed")
    
    print(f"\n📊 Success Rate: {success_count}/{num_requests} ({success_count/num_requests*100:.0f}%)")
    
    return results

def save_parallel_results(agent: str, results: list[dict], num_parts: int):
    """Save results from parallel execution"""
    output_file = f"{agent.upper()}_PARALLEL_AUDIT_RESPONSE.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {agent} AI Parallel Audit Results\n\n")
        f.write(f"**Execution:** {num_parts} parallel requests\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write("=" * 70 + "\n\n")
        
        total_chars = 0
        success_parts = []
        
        for i, result in enumerate(results, 1):
            f.write(f"## Part {i}/{num_parts}\n\n")
            
            if isinstance(result, Exception):
                f.write(f"**Status:** ❌ Exception\n\n")
                f.write(f"**Error:** {str(result)}\n\n")
            elif "error" in result:
                f.write(f"**Status:** ❌ Failed\n\n")
                f.write(f"**Error:** {result.get('error', 'Unknown')}\n\n")
            else:
                f.write(f"**Status:** ✅ Success\n\n")
                
                try:
                    # Extract response content
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        f.write(f"**Response Length:** {len(content):,} chars\n\n")
                        f.write("**Analysis:**\n\n")
                        f.write(content)
                        f.write("\n\n")
                        total_chars += len(content)
                        success_parts.append(i)
                    else:
                        f.write("**Raw Response:**\n\n```json\n")
                        f.write(json.dumps(result, indent=2))
                        f.write("\n```\n\n")
                except Exception as e:
                    f.write(f"**Parse Error:** {e}\n\n")
                    f.write("**Raw Response:**\n\n```json\n")
                    f.write(json.dumps(result, indent=2))
                    f.write("\n```\n\n")
            
            f.write("=" * 70 + "\n\n")
        
        # Summary
        f.write(f"## Summary\n\n")
        f.write(f"- **Total Parts:** {num_parts}\n")
        f.write(f"- **Successful:** {len(success_parts)}/{num_parts}\n")
        f.write(f"- **Success Rate:** {len(success_parts)/num_parts*100:.1f}%\n")
        f.write(f"- **Total Response:** {total_chars:,} characters\n")
        f.write(f"- **Successful Parts:** {', '.join(map(str, success_parts))}\n")
    
    print(f"\n💾 Results saved to: {output_file}")
    print(f"   Total response: {total_chars:,} characters")
    print(f"   Success rate: {len(success_parts)}/{num_parts}")

async def main():
    """Main parallel audit execution"""
    print("=" * 70)
    print("🚀 PARALLEL AUDIT SUBMISSION WITH 12 API KEYS")
    print("=" * 70)
    print("\nStrategy:")
    print("  - DeepSeek:   8 parallel requests (8 API keys)")
    print("  - Perplexity: 4 parallel requests (4 API keys)")
    print("  - Total:      12 concurrent API calls")
    print("=" * 70)
    
    # Initialize server with 12 encrypted keys
    print("\n🔐 Initializing server...")
    server = SimplifiedReliableMCP()
    print(f"   ✅ DeepSeek: {len(server.deepseek_keys)} keys loaded")
    print(f"   ✅ Perplexity: {len(server.perplexity_keys)} keys loaded")

    deepseek_requests = min(8, len(server.deepseek_keys)) or 1
    perplexity_requests = min(8, len(server.perplexity_keys)) or 1
    
    if len(server.deepseek_keys) < 8:
        print(f"   ⚠️ Only {len(server.deepseek_keys)} DeepSeek keys available; using {deepseek_requests} parallel requests")
    if len(server.perplexity_keys) < 8:
        print(f"   ⚠️ Only {len(server.perplexity_keys)} Perplexity keys available; using {perplexity_requests} parallel requests")
    
    # Load audit requests
    print("\n📄 Loading audit requests...")
    deepseek_request = Path("DEEPSEEK_AUDIT_REQUEST.md").read_text(encoding='utf-8')
    perplexity_request = Path("PERPLEXITY_AUDIT_REQUEST.md").read_text(encoding='utf-8')
    
    print(f"   ✅ DeepSeek: {len(deepseek_request):,} chars")
    print(f"   ✅ Perplexity: {len(perplexity_request):,} chars")
    
    # Execute BOTH agents in parallel (12 total requests)
    print("\n" + "=" * 70)
    print("🚀 STARTING PARALLEL EXECUTION (12 concurrent API calls)")
    print("=" * 70)
    
    overall_start = datetime.now()
    
    # Run DeepSeek (8 requests) and Perplexity (4 requests) simultaneously
    deepseek_task = parallel_deepseek_audit(server, deepseek_request, deepseek_requests)
    perplexity_task = parallel_perplexity_audit(server, perplexity_request, perplexity_requests)
    
    deepseek_results, perplexity_results = await asyncio.gather(
        deepseek_task,
        perplexity_task
    )
    
    overall_elapsed = (datetime.now() - overall_start).total_seconds()
    
    # Save results
    print("\n" + "=" * 70)
    print("💾 SAVING RESULTS")
    print("=" * 70)
    
    save_parallel_results("DeepSeek", deepseek_results, num_parts=deepseek_requests)
    save_parallel_results("Perplexity", perplexity_results, num_parts=perplexity_requests)
    
    # Final summary
    print("\n" + "=" * 70)
    print("🎉 PARALLEL AUDIT COMPLETE")
    print("=" * 70)
    print(f"\n📊 Execution Summary:")
    print(f"   Total time: {overall_elapsed:.1f}s")
    print(f"   DeepSeek: {deepseek_requests} parallel requests")
    print(f"   Perplexity: {perplexity_requests} parallel requests")
    print(f"   Total API calls: {deepseek_requests + perplexity_requests} concurrent")
    print(f"\n📁 Output Files:")
    print(f"   - DEEPSEEK_PARALLEL_AUDIT_RESPONSE.md")
    print(f"   - PERPLEXITY_PARALLEL_AUDIT_RESPONSE.md")
    print(f"\n💡 Throughput Improvement:")
    print(f"   Sequential (old): ~120s (10s per request × 12)")
    print(f"   Parallel (new): ~{overall_elapsed:.1f}s")
    print(f"   Speedup: {120/overall_elapsed:.1f}x faster")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

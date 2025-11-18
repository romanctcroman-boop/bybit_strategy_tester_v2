"""Agent-based audit of MCP Bridge reliability improvements"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def audit_with_agents():
    from backend.agents.unified_agent_interface import get_agent_interface
    from backend.agents.models import AgentRequest, AgentType
    
    agent = get_agent_interface()
    
    print("=" * 80)
    print("AGENT-BASED AUDIT: MCP Bridge Reliability Improvements")
    print("=" * 80)
    
    # Audit context with implementation details
    audit_context = """
# MCP Bridge Reliability Improvements - Audit Request

## Implemented Changes:

1. **Accurate Duration Measurement**
   - Moved start_time before try block
   - Both success/failure paths use time.perf_counter() - start_time
   - Location: backend/mcp/mcp_integration.py:call_tool()

2. **Fine-Grained Histogram Buckets**
   - Added microsecond-level precision (0.001s to 30s)
   - Buckets: 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30
   - Location: backend/api/app.py:MCP_BRIDGE_DURATION

3. **Single Correlation ID Fetch**
   - Correlation ID fetched once at start of call_tool()
   - Stored in local variable, accessible to both paths
   - Eliminates duplicate contextvars lookups

4. **Argument Schema Validation**
   - TOOL_SCHEMAS registry with 6 tools registered
   - Validates: required args, unknown args, type checking
   - Returns StructuredError on validation failure

5. **Structured Error Model**
   - StructuredError dataclass with fields:
     * error_type (ValidationError, ToolNotFoundError, etc.)
     * message (human-readable)
     * stage (validation, invocation, normalization)
     * retryable (bool)
     * correlation_id
     * details (dict with context)

## Test Results:
- 6/6 validation tests passing
- All error types properly structured
- Correlation ID propagated correctly

## Files Changed:
- backend/mcp/mcp_integration.py (+165, -30 lines)
- backend/api/app.py (+1, -1 line)
- test_mcp_validation.py (new, 130 lines)
"""
    
    # Task 1: DeepSeek code review
    print("\n" + "=" * 80)
    print("1️⃣ DeepSeek: Code Review & Error Detection")
    print("=" * 80)
    
    deepseek_request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="review",
        prompt="""Проведи глубокий code review реализации MCP Bridge reliability improvements.

Проверь:
1. Корректность переноса start_time перед try блоком - действительно ли теперь измеряется точная длительность в обоих путях?
2. Buckets гистограммы - достаточно ли гранулярности для микросекундных вызовов?
3. Оптимизация correlation_id - действительно ли устранено дублирование?
4. Валидация аргументов - полнота проверок (required, unknown, types)?
5. StructuredError модель - все ли необходимые поля присутствуют?
6. Потенциальные баги, race conditions, memory leaks

Верни JSON с полями:
{
  "overall_rating": "excellent|good|needs_improvement|critical_issues",
  "code_quality_score": 0-100,
  "issues_found": [
    {"severity": "critical|major|minor", "description": "...", "location": "file:line", "fix": "..."}
  ],
  "correctness_verification": {
    "duration_measurement": "correct|incorrect|needs_review",
    "histogram_buckets": "optimal|acceptable|insufficient",
    "correlation_id_optimization": "correct|incorrect",
    "validation_completeness": "complete|partial|insufficient",
    "error_model": "robust|adequate|needs_improvement"
  },
  "recommendations": ["..."]
}
""",
        code=audit_context,
        context={"use_file_access": True}
    )
    
    print("Отправляю запрос DeepSeek для code review...")
    deepseek_result = await agent.send_request(deepseek_request)
    
    print(f"\n✅ DeepSeek Response (channel: {deepseek_result.channel}):")
    print("-" * 80)
    print(deepseek_result.content[:2000])  # First 2000 chars
    if len(deepseek_result.content) > 2000:
        print(f"\n... (truncated, total {len(deepseek_result.content)} chars)")
    print("-" * 80)
    
    if deepseek_result.error:
        print(f"⚠️ DeepSeek Error: {deepseek_result.error}")
    
    # Task 2: Perplexity best practices verification
    print("\n" + "=" * 80)
    print("2️⃣ Perplexity: Best Practices & Industry Standards")
    print("=" * 80)
    
    perplexity_request = AgentRequest(
        agent_type=AgentType.PERPLEXITY,
        task_type="research",
        prompt="""Проверь соответствие реализации MCP Bridge reliability improvements индустриальным best practices.

Исследуй:
1. Duration measurement patterns - правильно ли реализован паттерн с start_time перед try?
2. Prometheus histogram buckets - соответствуют ли buckets рекомендациям для latency tracking?
3. Correlation ID patterns - оптимальна ли стратегия single fetch для distributed tracing?
4. API argument validation - полнота валидации (OpenAPI schema, JSON Schema стандарты)?
5. Structured error responses - соответствие RFC 7807 Problem Details, REST API best practices?

Верни оценку с рекомендациями в JSON:
{
  "compliance_score": 0-100,
  "best_practices_met": ["..."],
  "deviations": [
    {"practice": "...", "current_implementation": "...", "recommended": "...", "priority": "high|medium|low"}
  ],
  "industry_benchmarks": {
    "duration_tracking": "compliant|partially_compliant|non_compliant",
    "histogram_design": "optimal|acceptable|suboptimal",
    "correlation_patterns": "best_practice|acceptable|needs_improvement",
    "validation_standards": "compliant|partially_compliant|non_compliant",
    "error_response_format": "rfc_compliant|custom_adequate|needs_standardization"
  },
  "security_concerns": ["..."],
  "performance_implications": ["..."],
  "references": ["URL or standard name"]
}
""",
        code=audit_context,
        context={"use_file_access": False}
    )
    
    print("Отправляю запрос Perplexity для best practices проверки...")
    perplexity_result = await agent.send_request(perplexity_request)
    
    print(f"\n✅ Perplexity Response (channel: {perplexity_result.channel}):")
    print("-" * 80)
    print(perplexity_result.content[:2000])  # First 2000 chars
    if len(perplexity_result.content) > 2000:
        print(f"\n... (truncated, total {len(perplexity_result.content)} chars)")
    print("-" * 80)
    
    if perplexity_result.error:
        print(f"⚠️ Perplexity Error: {perplexity_result.error}")
    
    # Task 3: Consensus verification
    print("\n" + "=" * 80)
    print("3️⃣ Agent Consensus: Final Verdict")
    print("=" * 80)
    
    print("Формирую consensus между DeepSeek и Perplexity...")
    
    # Create summary based on both responses
    summary = f"""
# Agent Audit Summary

## DeepSeek Code Review:
{deepseek_result.content[:500]}...

## Perplexity Best Practices:
{perplexity_result.content[:500]}...

## Status:
- DeepSeek Channel: {deepseek_result.channel}
- Perplexity Channel: {perplexity_result.channel}
- DeepSeek Success: {deepseek_result.success}
- Perplexity Success: {perplexity_result.success}
"""
    
    print(summary)
    
    print("\n" + "=" * 80)
    print("✅ AGENT AUDIT COMPLETE")
    print("=" * 80)
    print(f"\nDeepSeek: {'✅ Success' if deepseek_result.success else '❌ Failed'}")
    print(f"Perplexity: {'✅ Success' if perplexity_result.success else '❌ Failed'}")
    print(f"\nFull responses saved above (total: {len(deepseek_result.content) + len(perplexity_result.content)} chars)")
    
    return {
        "deepseek": deepseek_result,
        "perplexity": perplexity_result
    }

if __name__ == "__main__":
    results = asyncio.run(audit_with_agents())

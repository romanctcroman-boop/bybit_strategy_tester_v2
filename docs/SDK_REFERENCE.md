# 📚 LLM SDK Reference — DeepSeek & Qwen

> **Created:** 2026-02-07
> **Purpose:** Detailed SDK/API documentation for optimizing AI agent configuration
> **Source:** Official API docs from DeepSeek and Alibaba Cloud Model Studio

---

## 🔷 DeepSeek API

### Endpoint

```
https://api.deepseek.com/v1/chat/completions
```

### Models

| Model                  | Context | Max Output        | Input $/1M                        | Output $/1M | Notes                                  |
| ---------------------- | ------- | ----------------- | --------------------------------- | ----------- | -------------------------------------- |
| `deepseek-chat` (V3.2) | 128K    | 8K (default 4K)   | $0.28 (miss) / $0.028 (cache hit) | $0.42       | Main chat model                        |
| `deepseek-reasoner`    | 128K    | 64K (default 32K) | $0.88 (miss) / $0.14 (cache hit)  | $2.19       | Thinking mode, NOW supports tool calls |

### Temperature Recommendations (OFFICIAL)

| Task Type         | Recommended Temperature             |
| ----------------- | ----------------------------------- |
| **Coding / Math** | **0.0** ⬅️ CRITICAL for our agents! |
| Data Analysis     | 1.0                                 |
| Conversation      | 1.3                                 |
| Translation       | 1.3                                 |
| Creative Writing  | 1.5                                 |

### Parameters

```python
{
    "model": "deepseek-chat",
    "messages": [...],
    "temperature": 0.0,          # 0-2, default 1. USE 0.0 FOR CODE!
    "top_p": 1.0,                # 0-1, default 1
    "max_tokens": 8192,          # Max output tokens
    "frequency_penalty": 0.0,    # -2 to 2
    "presence_penalty": 0.0,     # -2 to 2 (increase to reduce repetition)
    "tool_choice": "auto",       # "none", "auto", or specific function
    "response_format": {"type": "text"},  # or "json_object"
    "stream": False,
    "logprobs": False,
    "tools": [...]               # Tool definitions
}
```

### Strict Mode (Beta)

- Use `base_url="https://api.deepseek.com/beta"`
- Add `"strict": true` to tool function definitions
- Requires `"additionalProperties": false` and all properties in `"required"`
- Supports: object, string (with pattern/format), number/integer (with min/max), array, enum, anyOf, $ref/$def

### DeepSeek-Reasoner (Thinking Model)

- **NOW supports Tool Calls** (was previously unsupported)
- `reasoning_content` field in response for chain-of-thought
- temperature/top_p/penalties have **no effect** on reasoner
- Max output: 64K tokens (32K default)
- `"thinking": {"type": "enabled"}` or `{"type": "disabled"}`

### Key Notes

- **Cache hits**: Repeated prefixes get 90% discount ($0.028 vs $0.28)
- Rate limits: Check dashboard
- Supports JSON mode: `response_format: {"type": "json_object"}`

---

## 🟡 Qwen API (Alibaba Cloud Model Studio)

### Endpoint (Singapore/International)

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
```

### Models (International Region)

| Model               | Context | Max Output                    | Input $/1M    | Output $/1M                    | Notes                              |
| ------------------- | ------- | ----------------------------- | ------------- | ------------------------------ | ---------------------------------- |
| `qwen-flash`        | 1M      | 32K                           | $0.05 (≤256K) | $0.40                          | Cheapest, fastest                  |
| `qwen-plus`         | 1M      | 32K                           | $0.40 (≤256K) | $1.20 (non-think) / $4 (think) | Best balance                       |
| `qwen3-max`         | 262K    | 32K (think) / 65K (non-think) | $1.20 (≤32K)  | $6.00                          | Most powerful                      |
| `qwen3-coder-plus`  | 1M      | 65K                           | $1.00 (≤32K)  | $5.00                          | Best for code + tool calling       |
| `qwen3-coder-flash` | 1M      | 65K                           | $0.30 (≤32K)  | $1.50                          | Fast code model                    |
| `qwq-plus`          | 131K    | 8K                            | $0.80         | $2.40                          | Reasoning model (like DeepSeek-R1) |

### Parameters

```python
{
    "model": "qwen-plus",
    "messages": [...],
    "temperature": 0.3,          # [0, 2), default varies by model
    "top_p": 1.0,                # (0, 1.0]
    "top_k": None,               # Integer, if null or >100, disabled
    "max_tokens": 2000,          # Controls output length
    "presence_penalty": 0.0,     # [-2.0, 2.0]
    "seed": 42,                  # [0, 2^31-1] for reproducible results!
    "tool_choice": "auto",       # "auto" (default), "none", or specific
    "parallel_tool_calls": True,  # ⬅️ ENABLE for parallel tool calling!
    "tools": [...],
    "response_format": {"type": "text"},  # text, json_object, or json_schema
    "n": 1,                      # 1-4, multiple candidates
    "stream": False
}
```

### Thinking Mode (Qwen3 Models)

```python
# Via extra_body with OpenAI SDK:
extra_body = {
    "enable_thinking": True,      # Enable thinking mode
    "thinking_budget": 500        # Limit thinking tokens (optional)
}
```

- Supported by: qwen-plus, qwen-flash, qwen-turbo, qwen3-max, all Qwen3 open source
- Thinking process in `reasoning_content` field
- `/think` and `/no_think` tags in prompt for dynamic control
- Thinking mode output billed separately (higher cost)

### Parallel Tool Calling

```python
# Enable parallel tool calls:
completion = client.chat.completions.create(
    model="qwen-plus",
    messages=messages,
    tools=tools,
    parallel_tool_calls=True  # Returns ALL needed tool calls at once
)
```

- Suitable for independent tasks (no dependencies between tools)
- Returns multiple tool_calls in single response

### Tool Calling with Deep Thinking

```python
# Combine thinking + tools:
completion = client.chat.completions.create(
    model="qwen-plus",
    messages=messages,
    tools=tools,
    parallel_tool_calls=True,
    extra_body={"enable_thinking": True},
    stream=True  # Recommended for thinking mode
)
```

- `tool_choice` only supports `"auto"` or `"none"` with thinking mode
- Model thinks before deciding which tools to call
- Improves interpretability and reliability

### Qwen-Coder Models

- `qwen3-coder-plus`: Best for code + tool calling + environment interaction
- `qwen3-coder-flash`: Faster, cheaper code model
- Both: 1M context, 65K max output
- Excels at: tool calling, autonomous programming, coding agent tasks

### Best Practices from Docs

1. **System message**: Emphasize when to call tools → improves accuracy
2. **Tool descriptions**: Clear, concise `description` field is critical
3. **Max 20 tools**: Keep candidate set concise for best accuracy
4. **Retry strategy**: Max 3 retries for tool execution failures
5. **Timeout**: Set independent timeout per step
6. **Semantic routing**: For many tools, pre-filter with embeddings

---

## 🎯 Optimal Configuration for Our Agents

### Agent-Auditor (DeepSeek) — Code Analysis

```python
{
    "model": "deepseek-chat",
    "temperature": 0.0,          # Official recommendation for coding!
    "max_tokens": 4000,          # Increase from 2500 (default is only 4K max)
    "presence_penalty": 0.3,     # Reduce repetitive analysis
    "tool_choice": "auto",       # Let model decide
}
```

**Why `temperature=0.0`**: DeepSeek officially recommends 0.0 for coding/math tasks.
This gives the most deterministic, accurate code analysis.

### Agent-Fixer (Qwen) — Code Fixes

```python
{
    "model": "qwen3-coder-flash", # Better for code than qwen-flash!
    "temperature": 0.1,          # Very low for precise code fixes
    "max_tokens": 4000,          # Increase for detailed fixes
    "parallel_tool_calls": True,  # Read multiple files at once
    "seed": 42,                  # Reproducible during development
    "tool_choice": "auto",
}
```

**Why `qwen3-coder-flash`**: Specifically trained for code + tool calling.
$0.30/1M input — only slightly more expensive than qwen-flash ($0.05).
Massively better code quality.

### Alternative: Thinking Mode for Complex Audits

```python
# For Phase 1 (Audit) — use thinking to reason about code:
{
    "model": "qwen-plus",
    "extra_body": {"enable_thinking": True, "thinking_budget": 1000},
    "stream": True,
}
```

---

## 📊 Cost Comparison (per 1M tokens)

| Role        | Current       | Recommended       | Input Cost | Output Cost |
| ----------- | ------------- | ----------------- | ---------- | ----------- |
| Auditor     | deepseek-chat | deepseek-chat     | $0.28      | $0.42       |
| Fixer       | qwen-flash    | qwen3-coder-flash | $0.30      | $1.50       |
| Alt Fixer   | -             | qwen-plus         | $0.40      | $1.20       |
| Alt Auditor | -             | deepseek-reasoner | $0.88      | $2.19       |

**Current session cost** (~9 API calls, ~20K tokens): ~$0.01-0.02
**With coder model**: Still under $0.05 per session

---

## 🔗 Documentation Links

- [DeepSeek API Docs](https://api-docs.deepseek.com/)
- [DeepSeek Function Calling](https://api-docs.deepseek.com/guides/function_calling)
- [DeepSeek Parameter Settings](https://api-docs.deepseek.com/quick_start/parameter_settings)
- [DeepSeek Reasoning Model](https://api-docs.deepseek.com/guides/reasoning_model)
- [Qwen Model List](https://www.alibabacloud.com/help/en/model-studio/models)
- [Qwen Function Calling](https://www.alibabacloud.com/help/en/model-studio/qwen-function-calling)
- [Qwen Deep Thinking](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)
- [Qwen API Reference](https://www.alibabacloud.com/help/en/model-studio/qwen-api-reference/)

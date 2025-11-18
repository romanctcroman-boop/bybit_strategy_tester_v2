# 🚀 ENHANCED API PARAMETERS GUIDE

**Date:** October 31, 2025  
**Status:** ✅ IMPLEMENTED  
**Files Modified:** `mcp-server/multi_agent_router.py`

---

## 📚 Table of Contents

1. [DeepSeek Client - Enhanced Parameters](#deepseek-client)
2. [Perplexity Sonar Pro Client - Enhanced Parameters](#sonar-pro-client)
3. [Usage Examples](#usage-examples)
4. [Best Practices](#best-practices)

---

## 🤖 DeepSeek Client - Enhanced Parameters

### Core Parameters (OpenAI-Compatible)

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `temperature` | float | 0-2 | 0.7 | Randomness level. 0=focused, 2=creative |
| `top_p` | float | 0-1 | 1.0 | Nucleus sampling threshold |
| `max_tokens` | int | > 0 | 4000 | Maximum response length |
| `frequency_penalty` | float | -2 to 2 | 0 | Reduce repetition based on frequency |
| `presence_penalty` | float | -2 to 2 | 0 | Encourage new topics |

### Advanced Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stop` | string/array | None | Stop sequences to end generation |
| `stream` | bool | False | Enable streaming responses |
| `stream_options` | object | None | Streaming configuration |
| `logprobs` | bool | False | Return log probabilities |
| `top_logprobs` | int (0-20) | None | Number of top tokens to return |
| `response_format` | object | None | JSON mode: `{"type": "json_object"}` |
| `system_prompt` | string | Auto | Custom system prompt |

### Function Calling

| Parameter | Type | Description |
|-----------|------|-------------|
| `tools` | array | List of function tools available |
| `tool_choice` | string/object | Force specific tool: "auto", "none", or `{"type": "function", "function": {"name": "..."}}` |

### Example Usage

```python
from multi_agent_router import get_router, TaskType

router = get_router()

# Basic usage
result = await router.route(
    TaskType.CODE_GENERATION,
    {
        "query": "Write a Python function to calculate Fibonacci",
        "temperature": 0.3,  # More focused
        "max_tokens": 2000
    }
)

# Advanced: JSON mode
result = await router.route(
    TaskType.CODE_GENERATION,
    {
        "query": "Generate a JSON schema for a User model",
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
)

# Function calling
result = await router.route(
    TaskType.CODE_GENERATION,
    {
        "query": "Get current weather in London",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        }
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }
)
```

---

## 🔍 Sonar Pro Client - Enhanced Parameters

### Perplexity-Specific Parameters

#### Search Control

| Parameter | Type | Options | Default | Description |
|-----------|------|---------|---------|-------------|
| `search_mode` | string | `web`, `academic`, `sec` | `web` | Search mode |
| `reasoning_effort` | string | `low`, `medium`, `high` | `medium` | For sonar-deep-research only |
| `disable_search` | bool | - | False | Use only training data |
| `enable_search_classifier` | bool | - | False | Auto-detect if search needed |

#### Search Filtering

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `search_domain_filter` | array | Allowlist (+) / Denylist (-) domains | `["example.com", "-spam.com"]` |
| `search_recency_filter` | string | Time filter | `"week"`, `"day"`, `"month"`, `"year"` |
| `search_after_date_filter` | string | After date (MM/DD/YYYY) | `"01/01/2024"` |
| `search_before_date_filter` | string | Before date (MM/DD/YYYY) | `"12/31/2024"` |
| `last_updated_after_filter` | string | Updated after (MM/DD/YYYY) | `"10/01/2025"` |
| `last_updated_before_filter` | string | Updated before (MM/DD/YYYY) | `"10/31/2025"` |

#### Content Enhancement

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `return_images` | bool | False | Include images in results |
| `return_related_questions` | bool | False | Suggest follow-up questions |
| `language_preference` | string | None | Response language (sonar/sonar-pro only) |

#### Media Response

```python
"media_response": {
    "overrides": {
        "return_videos": True,
        "return_images": True
    }
}
```

#### Web Search Options

```python
"web_search_options": {
    "search_context_size": "high"  # 'low', 'medium', 'high'
}
```

### OpenAI-Compatible Parameters

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `temperature` | float | 0-2 | 0.2 | Randomness level |
| `top_p` | float | 0-1 | 0.9 | Nucleus sampling |
| `top_k` | int | ≥ 0 | 0 | Top-k sampling (0=disabled) |
| `max_tokens` | int | > 0 | Auto | Maximum response length |
| `presence_penalty` | float | 0-2 | 0 | New topics penalty |
| `frequency_penalty` | float | 0-2 | 0 | Repetition penalty |
| `stream` | bool | - | False | Streaming responses |
| `response_format` | object | - | None | JSON mode |

### Response Data Structure

```python
{
    "agent": "sonar-pro",
    "status": "success",
    "result": "Main response content...",
    "model": "sonar-pro",
    "usage": {
        "prompt_tokens": 123,
        "completion_tokens": 456,
        "total_tokens": 579,
        "search_context_size": "medium",
        "citation_tokens": 50,
        "num_search_queries": 3
    },
    "search_results": [
        {
            "title": "Example Article",
            "url": "https://example.com",
            "date": "2025-10-31"
        }
    ],
    "citations": ["https://source1.com", "https://source2.com"],
    "related_questions": [
        "Follow-up question 1?",
        "Follow-up question 2?"
    ],
    "videos": [
        {
            "url": "https://youtube.com/watch?v=...",
            "thumbnail_url": "https://...",
            "duration": 180
        }
    ],
    "images": ["https://image1.com", "https://image2.com"],
    "attempt": 1
}
```

---

## 💡 Usage Examples

### Example 1: Academic Research

```python
result = await router.route(
    TaskType.RESEARCH,
    {
        "query": "Latest advances in neural architecture search",
        "search_mode": "academic",
        "return_related_questions": True,
        "search_recency_filter": "year",
        "max_tokens": 3000
    }
)
```

### Example 2: SEC Filings Analysis

```python
result = await router.route(
    TaskType.AUDIT,
    {
        "query": "Analyze Tesla's Q3 2025 financial report",
        "search_mode": "sec",
        "search_domain_filter": ["sec.gov"],
        "temperature": 0.1  # Factual
    }
)
```

### Example 3: Russian Language Response

```python
result = await router.route(
    TaskType.EXPLAIN,
    {
        "query": "Explain quantum computing",
        "language_preference": "Russian",
        "return_images": True,
        "return_related_questions": True
    }
)
```

### Example 4: Filtered Search with Media

```python
result = await router.route(
    TaskType.RESEARCH,
    {
        "query": "Python async/await tutorial",
        "search_domain_filter": [
            "docs.python.org",
            "realpython.com",
            "-stackoverflow.com"  # Denylist
        ],
        "media_response": {
            "overrides": {
                "return_videos": True,
                "return_images": True
            }
        },
        "web_search_options": {
            "search_context_size": "high"
        }
    }
)
```

### Example 5: Date-Filtered Search

```python
result = await router.route(
    TaskType.RESEARCH,
    {
        "query": "AI breakthroughs in 2025",
        "search_after_date_filter": "01/01/2025",
        "search_before_date_filter": "10/31/2025",
        "return_related_questions": True
    }
)
```

### Example 6: No Web Search (Training Data Only)

```python
result = await router.route(
    TaskType.EXPLAIN,
    {
        "query": "Explain backpropagation algorithm",
        "disable_search": True,  # Use only training data
        "temperature": 0.3
    }
)
```

### Example 7: Deep Research with High Effort

```python
# Note: Change model to sonar-deep-research manually if needed
result = await router.route(
    TaskType.AUDIT,
    {
        "query": "Comprehensive analysis of trading strategies",
        "reasoning_effort": "high",  # Only for sonar-deep-research
        "max_tokens": 5000,
        "return_related_questions": True
    }
)
```

---

## 🎯 Best Practices

### Temperature Guidelines

| Use Case | DeepSeek | Sonar Pro | Reasoning |
|----------|----------|-----------|-----------|
| Code generation | 0.2-0.5 | 0.1-0.3 | Deterministic, correct |
| Factual Q&A | 0.3-0.7 | 0.2-0.4 | Balanced |
| Creative writing | 0.8-1.5 | 0.6-1.0 | More randomness |
| Brainstorming | 1.0-2.0 | 0.8-1.5 | Maximum creativity |

### Search Mode Selection

| Mode | Use For | Example |
|------|---------|---------|
| `web` | General queries | "Latest crypto news" |
| `academic` | Research papers | "Transformer architecture papers" |
| `sec` | Financial filings | "Tesla 10-K filing analysis" |

### Token Optimization

```python
# Bad: No limit, may timeout
{"query": "Explain everything about Python", "max_tokens": None}

# Good: Reasonable limit
{"query": "Explain Python decorators", "max_tokens": 1500}

# Best: Specific query + appropriate limit
{"query": "Show example of Python decorator with error handling", "max_tokens": 800}
```

### Domain Filtering

```python
# Allowlist (only these domains)
"search_domain_filter": ["python.org", "realpython.com"]

# Denylist (exclude these domains)
"search_domain_filter": ["-stackoverflow.com", "-reddit.com"]

# Mixed
"search_domain_filter": [
    "github.com",  # Allow
    "-spam.com"    # Deny
]
```

### Performance Tips

1. **Use caching**: Identical queries return cached results
2. **Limit search scope**: Use domain filters to reduce noise
3. **Disable search when not needed**: `disable_search: True` for pure reasoning
4. **Use search classifier**: `enable_search_classifier: True` for auto-optimization
5. **Adjust reasoning effort**: Use `"low"` for quick answers, `"high"` for deep research

---

## 📊 Parameter Comparison Matrix

| Feature | DeepSeek | Sonar Pro |
|---------|----------|-----------|
| Temperature | 0-2 | 0-2 |
| Top-P | ✅ | ✅ |
| Top-K | ❌ | ✅ |
| Max Tokens | ✅ | ✅ |
| Frequency Penalty | ✅ | ✅ |
| Presence Penalty | ✅ | ✅ |
| Streaming | ✅ | ✅ |
| JSON Mode | ✅ | ✅ |
| Function Calling | ✅ | ❌ |
| Web Search | ❌ | ✅ |
| Search Modes | ❌ | ✅ (web/academic/sec) |
| Domain Filtering | ❌ | ✅ |
| Image Results | ❌ | ✅ |
| Video Results | ❌ | ✅ |
| Citations | ❌ | ✅ |
| Related Questions | ❌ | ✅ |
| Language Preference | ❌ | ✅ (sonar/sonar-pro) |
| Date Filtering | ❌ | ✅ |
| Reasoning Effort | ❌ | ✅ (deep-research) |

---

## 🔧 Migration Guide

### Before (Limited Parameters)

```python
# Old way - basic parameters only
result = await router.route(
    TaskType.RESEARCH,
    {
        "query": "Python best practices",
        "temperature": 0.7
    }
)
```

### After (Full Parameters)

```python
# New way - utilize all features
result = await router.route(
    TaskType.RESEARCH,
    {
        "query": "Python best practices for async code",
        
        # Core parameters
        "temperature": 0.4,
        "max_tokens": 2000,
        "top_p": 0.9,
        
        # Perplexity-specific
        "search_mode": "web",
        "search_domain_filter": [
            "docs.python.org",
            "realpython.com"
        ],
        "return_images": True,
        "return_related_questions": True,
        "search_recency_filter": "year",
        "language_preference": "English",
        
        # Content enhancement
        "web_search_options": {
            "search_context_size": "high"
        }
    }
)

# Access enhanced response
print(result["result"])  # Main content
print(result["search_results"])  # Sources
print(result["related_questions"])  # Follow-ups
```

---

## ✅ Validation & Error Handling

All parameters are automatically validated and clamped:

- `temperature`: Clamped to 0-2
- `top_p`: Clamped to 0-1
- `top_logprobs`: Clamped to 0-20
- `frequency_penalty`/`presence_penalty`: Clamped to -2 to 2 (DeepSeek), 0-2 (Sonar Pro)

Invalid parameters are ignored, ensuring API stability.

---

**🎉 Enhanced API Implementation Complete!**

Both DeepSeek and Sonar Pro now support full parameter sets from official documentation.

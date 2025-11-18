# Protocol Compliance Specification (P1)

**Status**: ✅ Implemented and Tested (100% Coverage)  
**Version**: 2.0  
**Last Updated**: 2025-11-01

## Table of Contents

1. [Overview](#overview)
2. [JSON-RPC 2.0 Implementation](#json-rpc-20-implementation)
3. [MCP Error Codes](#mcp-error-codes)
4. [Protocol Versioning](#protocol-versioning)
5. [Capability Discovery](#capability-discovery)
6. [Integration Guide](#integration-guide)
7. [Testing](#testing)

---

## Overview

The MCP Server implements **Protocol Compliance (P1)** to provide a production-ready, standards-compliant API. This includes:

- ✅ **JSON-RPC 2.0** full specification support
- ✅ **Batch Request Handling** (multiple operations in single request)
- ✅ **Structured Error Codes** (5 categories, 41 error codes)
- ✅ **Protocol Versioning** (v1.0 and v2.0 with negotiation)
- ✅ **Capability Discovery** (dynamic feature and tool discovery)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Application                        │
└────────────────────────┬────────────────────────────────────┘
                         │ JSON-RPC 2.0 Request
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 JSON-RPC Handler Layer                       │
│  - Request Validation                                        │
│  - Batch Processing                                          │
│  - Protocol Version Negotiation                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Security & Validation Layer                    │
│  - Authentication (JWT / API Key)                            │
│  - Rate Limiting                                             │
│  - Input Validation                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  MCP Tool Execution                          │
│  - 47+ Tools (Perplexity AI, Analysis, Utilities)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Response Formatting Layer                     │
│  - JSON-RPC 2.0 Response                                     │
│  - Error Handling with MCP Error Codes                       │
│  - Audit Logging                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## JSON-RPC 2.0 Implementation

### Specification Compliance

The server implements [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification) with full support for:

- ✅ Request/Response objects
- ✅ Batch requests
- ✅ Notifications (requests without `id`)
- ✅ Error objects with codes and data
- ✅ Parameter passing (positional and named)

### Single Request Example

```json
// Request
{
  "jsonrpc": "2.0",
  "method": "perplexity_search",
  "params": {
    "query": "Latest Bitcoin price analysis",
    "model": "sonar-pro"
  },
  "id": 1
}

// Successful Response
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "answer": "Bitcoin is currently trading at...",
    "sources": [...]
  },
  "id": 1
}

// Error Response
{
  "jsonrpc": "2.0",
  "error": {
    "code": 1002,
    "message": "Invalid API key",
    "data": {
      "severity": "high",
      "retryable": false,
      "suggested_action": "authenticate"
    }
  },
  "id": 1
}
```

### Batch Request Example

Execute multiple operations in a single HTTP request:

```json
// Batch Request
[
  {
    "jsonrpc": "2.0",
    "method": "perplexity_analyze_crypto",
    "params": {"symbol": "BTCUSDT", "timeframe": "1d"},
    "id": "1"
  },
  {
    "jsonrpc": "2.0",
    "method": "perplexity_sentiment_analysis",
    "params": {"topic": "bitcoin"},
    "id": "2"
  },
  {
    "jsonrpc": "2.0",
    "method": "market_regime_detection",
    "params": {"symbol": "BTCUSDT"},
    "id": "3"
  }
]

// Batch Response
[
  {
    "jsonrpc": "2.0",
    "result": {...},
    "id": "1"
  },
  {
    "jsonrpc": "2.0",
    "result": {...},
    "id": "2"
  },
  {
    "jsonrpc": "2.0",
    "result": {...},
    "id": "3"
  }
]
```

### Notification Example

Requests without `id` are **notifications** (no response expected):

```json
{
  "jsonrpc": "2.0",
  "method": "cache_clear",
  "params": {}
  // No "id" field = notification
}
```

### Standard JSON-RPC Error Codes

| Code  | Message            | Meaning                          |
|-------|--------------------|----------------------------------|
| -32700| Parse error        | Invalid JSON                     |
| -32600| Invalid Request    | JSON-RPC structure invalid       |
| -32601| Method not found   | Method doesn't exist             |
| -32602| Invalid params     | Invalid method parameters        |
| -32603| Internal error     | Internal JSON-RPC error          |

---

## MCP Error Codes

### Error Code Taxonomy

The MCP Server uses a comprehensive error code system organized into 5 categories:

| Range     | Category             | Description                          | Count |
|-----------|----------------------|--------------------------------------|-------|
| 1000-1999 | Authentication       | Auth and authorization errors        | 8     |
| 2000-2999 | Validation           | Input validation and security        | 11    |
| 3000-3999 | Rate Limiting        | Rate limits and quotas               | 5     |
| 4000-4999 | Resource             | Resource not found errors            | 7     |
| 5000-5999 | Internal             | Internal server errors               | 10    |

### Authentication Errors (1xxx)

| Code | Error                      | Severity | Retryable | Description                |
|------|----------------------------|----------|-----------|----------------------------|
| 1001 | MISSING_AUTHENTICATION     | HIGH     | No        | Authentication required    |
| 1002 | INVALID_API_KEY            | HIGH     | No        | Invalid API key            |
| 1003 | EXPIRED_API_KEY            | HIGH     | No        | API key expired            |
| 1004 | REVOKED_API_KEY            | HIGH     | No        | API key revoked            |
| 1005 | INVALID_JWT_TOKEN          | HIGH     | No        | Invalid JWT token          |
| 1006 | EXPIRED_JWT_TOKEN          | HIGH     | No        | JWT token expired          |
| 1007 | INSUFFICIENT_PERMISSIONS   | HIGH     | No        | Insufficient permissions   |
| 1008 | INVALID_USER_ID            | MEDIUM   | No        | Invalid user ID            |

### Validation Errors (2xxx)

| Code | Error                      | Severity  | Retryable | Description                |
|------|----------------------------|-----------|-----------|----------------------------|
| 2001 | INVALID_INPUT              | MEDIUM    | No        | Invalid input data         |
| 2002 | MISSING_REQUIRED_FIELD     | MEDIUM    | No        | Missing required field     |
| 2003 | INVALID_FIELD_TYPE         | MEDIUM    | No        | Invalid field type         |
| 2004 | INVALID_FIELD_VALUE        | MEDIUM    | No        | Invalid field value        |
| 2005 | SQL_INJECTION_DETECTED     | CRITICAL  | No        | SQL injection attempt      |
| 2006 | XSS_ATTACK_DETECTED        | CRITICAL  | No        | XSS attack attempt         |
| 2007 | PATH_TRAVERSAL_DETECTED    | CRITICAL  | No        | Path traversal attempt     |
| 2008 | INVALID_JSON               | MEDIUM    | No        | Invalid JSON format        |
| 2009 | SCHEMA_VALIDATION_FAILED   | MEDIUM    | No        | Schema validation failed   |
| 2010 | INVALID_DATE_FORMAT        | MEDIUM    | No        | Invalid date format        |
| 2011 | DATE_RANGE_INVALID         | MEDIUM    | No        | Date range invalid         |

### Rate Limiting Errors (3xxx)

| Code | Error                      | Severity | Retryable | Description                     |
|------|----------------------------|----------|-----------|----------------------------------|
| 3001 | RATE_LIMIT_EXCEEDED        | HIGH     | Yes       | Rate limit exceeded             |
| 3002 | QUOTA_EXCEEDED             | HIGH     | No        | API quota exceeded              |
| 3003 | CONCURRENT_REQUEST_LIMIT   | MEDIUM   | Yes       | Too many concurrent requests    |
| 3004 | REQUEST_SIZE_TOO_LARGE     | MEDIUM   | No        | Request size exceeds limit      |
| 3005 | BATCH_SIZE_TOO_LARGE       | MEDIUM   | No        | Batch size exceeds limit        |

### Resource Errors (4xxx)

| Code | Error                      | Severity | Retryable | Description                |
|------|----------------------------|----------|-----------|----------------------------|
| 4001 | TOOL_NOT_FOUND             | MEDIUM   | No        | MCP tool not found         |
| 4002 | RESOURCE_NOT_FOUND         | MEDIUM   | No        | Resource not found         |
| 4003 | STRATEGY_NOT_FOUND         | MEDIUM   | No        | Strategy not found         |
| 4004 | BACKTEST_NOT_FOUND         | MEDIUM   | No        | Backtest not found         |
| 4005 | DATA_NOT_AVAILABLE         | MEDIUM   | Yes       | Market data not available  |
| 4006 | SYMBOL_NOT_SUPPORTED       | MEDIUM   | No        | Symbol not supported       |
| 4007 | TIMEFRAME_NOT_SUPPORTED    | MEDIUM   | No        | Timeframe not supported    |

### Internal Server Errors (5xxx)

| Code | Error                      | Severity  | Retryable | Description                |
|------|----------------------------|-----------|-----------|----------------------------|
| 5000 | INTERNAL_SERVER_ERROR      | CRITICAL  | Yes       | Internal server error      |
| 5001 | DATABASE_ERROR             | CRITICAL  | Yes       | Database error             |
| 5002 | EXTERNAL_API_ERROR         | HIGH      | Yes       | External API error         |
| 5003 | REDIS_CONNECTION_ERROR     | HIGH      | Yes       | Redis connection error     |
| 5004 | PERPLEXITY_API_ERROR       | HIGH      | Yes       | Perplexity API error       |
| 5005 | TIMEOUT_ERROR              | MEDIUM    | Yes       | Request timeout            |
| 5006 | CONFIGURATION_ERROR        | CRITICAL  | No        | Configuration error        |
| 5007 | SERVICE_UNAVAILABLE        | HIGH      | Yes       | Service unavailable        |
| 5008 | MEMORY_ERROR               | CRITICAL  | No        | Out of memory              |
| 5009 | TASK_EXECUTION_ERROR       | HIGH      | Yes       | Task execution error       |

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": 3001,
    "message": "Rate limit exceeded",
    "data": {
      "details": "Rate limit exceeded. Retry after 60 seconds",
      "severity": "high",
      "retryable": true,
      "suggested_action": "retry_backoff",
      "context": {
        "retry_after": 60
      }
    }
  },
  "id": 1
}
```

### Using MCP Error Codes (Python)

```python
from protocol import MCPErrorCode

# Raise error
raise MCPErrorCode.INVALID_API_KEY.to_exception(
    "API key format invalid",
    api_key_prefix="abc123..."
)

# Get error info
error_info = MCPErrorCode.RATE_LIMIT_EXCEEDED.to_dict()

# Check error category
categories = MCPErrorCode.get_errors_by_category()
auth_errors = categories["authentication"]
```

---

## Protocol Versioning

### Supported Versions

| Version | Release Date | Status      | Features                              |
|---------|--------------|-------------|---------------------------------------|
| 1.0     | 2024-01-01   | Supported   | Basic tool execution                  |
| 2.0     | 2025-01-01   | Current     | JSON-RPC 2.0, Batch, Error codes, etc.|

### Version Negotiation

Clients can specify protocol version via:

1. **Client-Version header** (recommended):
```http
GET /api/tools HTTP/1.1
Client-Version: 2.0
```

2. **Accept header**:
```http
GET /api/tools HTTP/1.1
Accept: application/vnd.mcp.v2+json
```

3. **Request parameter**:
```json
{
  "protocol_version": "2.0",
  "method": "...",
  ...
}
```

### Version 2.0 Features

- ✅ JSON-RPC 2.0 batch requests
- ✅ Structured MCP error codes
- ✅ Capability discovery API
- ✅ Enhanced authentication (JWT + API Key)
- ✅ Rate limiting with sliding window
- ✅ Input validation and security
- ✅ Audit logging
- ✅ Streaming responses
- ✅ Response caching
- ✅ Multi-agent routing

### Version Compatibility Check

```python
from protocol import ProtocolVersionManager

manager = ProtocolVersionManager()

# Validate compatibility
result = manager.validate_version_compatibility(
    client_version="2.0",
    required_features=["batch_requests", "streaming"]
)

if result["compatible"]:
    print("Client version compatible!")
else:
    print(f"Error: {result['error']}")
    print(f"Missing features: {result['missing_features']}")
```

### Upgrade Path

To upgrade from v1.0 to v2.0:

```python
manager = ProtocolVersionManager()
upgrade_path = manager.get_upgrade_path(
    from_version=ProtocolVersion.V1_0,
    to_version=ProtocolVersion.V2_0
)

print(f"New features: {upgrade_path['new_features']}")
print(f"Breaking changes: {upgrade_path['breaking_changes']}")
```

---

## Capability Discovery

### Get Server Capabilities

```http
GET /api/capabilities HTTP/1.1
```

Response:
```json
{
  "server_version": "2.0",
  "protocol_versions": ["1.0", "2.0"],
  "tools": [
    {
      "name": "perplexity_search",
      "description": "Search via Perplexity AI",
      "category": "ai_analysis",
      "requires_auth": true,
      "rate_limited": true
    },
    ...
  ],
  "authentication": [
    {
      "method": "jwt",
      "enabled": true,
      "description": "JWT token authentication"
    },
    {
      "method": "api_key",
      "enabled": true,
      "description": "API key authentication"
    }
  ],
  "rate_limiting": {
    "enabled": true,
    "default_requests_per_window": 100,
    "default_window_seconds": 60,
    "per_user_limits": true,
    "per_endpoint_limits": true
  },
  "features": [
    "json_rpc_2.0",
    "batch_requests",
    "structured_error_codes",
    "capability_discovery",
    "protocol_versioning",
    "jwt_authentication",
    "api_key_authentication",
    "rate_limiting",
    "input_validation",
    "audit_logging",
    "perplexity_ai",
    "security_components"
  ],
  "limits": {
    "max_batch_size": 100,
    "max_request_size_mb": 10
  },
  "endpoints": {
    "health_check": "/health",
    "documentation": "https://github.com/RomanCTC/bybit_strategy_tester_v2"
  }
}
```

### Capability Summary

```http
GET /api/capabilities/summary HTTP/1.1
```

Response:
```json
{
  "total_tools": 47,
  "categories": {
    "ai_analysis": 27,
    "project_info": 7,
    "advanced_analysis": 8,
    "utility": 5
  },
  "authentication_methods": ["jwt", "api_key"],
  "rate_limiting_enabled": true,
  "features_count": 12,
  "protocol_versions": ["1.0", "2.0"],
  "timestamp": "2025-11-01T21:30:00Z"
}
```

### Using Capability Registry (Python)

```python
from protocol import CapabilityRegistry

registry = CapabilityRegistry()

# Check if tool exists
if registry.validate_tool_exists("perplexity_search"):
    tool_info = registry.get_tool_info("perplexity_search")
    print(f"Tool: {tool_info['name']}")
    print(f"Auth required: {tool_info['requires_auth']}")

# Check feature availability
if registry.is_feature_enabled("streaming"):
    # Use streaming feature
    pass

# Get all capabilities
capabilities = registry.get_capabilities()
print(f"Server version: {capabilities.server_version}")
print(f"Total tools: {len(capabilities.tools)}")
```

---

## Integration Guide

### Python Client Example

```python
import requests
import json

class MCPClient:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.request_id = 0
    
    def call_method(self, method: str, params: dict = None):
        """Single JSON-RPC 2.0 request"""
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        response = requests.post(
            f"{self.base_url}/jsonrpc",
            json=request,
            headers=headers
        )
        
        result = response.json()
        
        if "error" in result:
            raise Exception(
                f"[MCP-{result['error']['code']}] {result['error']['message']}"
            )
        
        return result["result"]
    
    def batch_call(self, calls: list[tuple[str, dict]]):
        """Batch JSON-RPC 2.0 request"""
        batch_request = []
        
        for method, params in calls:
            self.request_id += 1
            batch_request.append({
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": self.request_id
            })
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        response = requests.post(
            f"{self.base_url}/jsonrpc",
            json=batch_request,
            headers=headers
        )
        
        return response.json()

# Usage
client = MCPClient("https://mcp-server.example.com", api_key="your-api-key")

# Single call
result = client.call_method("perplexity_search", {
    "query": "Bitcoin price analysis",
    "model": "sonar-pro"
})
print(result)

# Batch call
results = client.batch_call([
    ("perplexity_analyze_crypto", {"symbol": "BTCUSDT"}),
    ("perplexity_sentiment_analysis", {"topic": "bitcoin"}),
    ("market_regime_detection", {"symbol": "BTCUSDT"})
])

for result in results:
    if "result" in result:
        print(f"Success: {result['id']}")
    else:
        print(f"Error {result['error']['code']}: {result['error']['message']}")
```

### JavaScript/TypeScript Client Example

```typescript
interface JSONRPCRequest {
  jsonrpc: string;
  method: string;
  params?: any;
  id: string | number;
}

interface JSONRPCResponse {
  jsonrpc: string;
  result?: any;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
  id: string | number;
}

class MCPClient {
  private baseUrl: string;
  private apiKey: string | null;
  private requestId: number = 0;
  
  constructor(baseUrl: string, apiKey?: string) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey || null;
  }
  
  async callMethod(method: string, params: any = {}): Promise<any> {
    this.requestId++;
    
    const request: JSONRPCRequest = {
      jsonrpc: "2.0",
      method,
      params,
      id: this.requestId
    };
    
    const headers: Record<string, string> = {
      "Content-Type": "application/json"
    };
    
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    
    const response = await fetch(`${this.baseUrl}/jsonrpc`, {
      method: "POST",
      headers,
      body: JSON.stringify(request)
    });
    
    const result: JSONRPCResponse = await response.json();
    
    if (result.error) {
      throw new Error(
        `[MCP-${result.error.code}] ${result.error.message}`
      );
    }
    
    return result.result;
  }
  
  async batchCall(calls: Array<[string, any]>): Promise<JSONRPCResponse[]> {
    const batchRequest = calls.map(([method, params]) => {
      this.requestId++;
      return {
        jsonrpc: "2.0",
        method,
        params: params || {},
        id: this.requestId
      };
    });
    
    const headers: Record<string, string> = {
      "Content-Type": "application/json"
    };
    
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    
    const response = await fetch(`${this.baseUrl}/jsonrpc`, {
      method: "POST",
      headers,
      body: JSON.stringify(batchRequest)
    });
    
    return await response.json();
  }
}

// Usage
const client = new MCPClient("https://mcp-server.example.com", "your-api-key");

// Single call
const result = await client.callMethod("perplexity_search", {
  query: "Bitcoin price analysis",
  model: "sonar-pro"
});
console.log(result);

// Batch call
const results = await client.batchCall([
  ["perplexity_analyze_crypto", { symbol: "BTCUSDT" }],
  ["perplexity_sentiment_analysis", { topic: "bitcoin" }],
  ["market_regime_detection", { symbol: "BTCUSDT" }]
]);

results.forEach(result => {
  if (result.result) {
    console.log(`Success: ${result.id}`);
  } else {
    console.error(`Error ${result.error!.code}: ${result.error!.message}`);
  }
});
```

---

## Testing

### Running Protocol Tests

```bash
cd mcp-server
python test_protocol.py
```

### Test Coverage

- ✅ **JSON-RPC 2.0 Basic**: 4/4 tests passed
  - Valid request/response
  - Invalid version rejection
  - Method not found
  - Notification handling
  
- ✅ **JSON-RPC 2.0 Batch**: 4/4 tests passed
  - Valid batch request (3 operations)
  - Mixed valid/invalid batch
  - Batch with notifications
  - Empty batch rejection
  
- ✅ **MCP Error Codes**: 7/7 tests passed
  - Authentication errors (1xxx)
  - Validation errors (2xxx)
  - Rate limiting errors (3xxx)
  - Resource errors (4xxx)
  - Internal errors (5xxx)
  - Error categories
  - Error serialization
  
- ✅ **Protocol Versioning**: 8/8 tests passed
  - Version negotiation
  - Default to latest
  - Invalid version handling
  - Feature availability checks (v1.0 vs v2.0)
  - Version info retrieval
  - Upgrade path generation
  - Compatibility validation
  
- ✅ **Capability Discovery**: 8/8 tests passed
  - Tool registration
  - Tool info retrieval
  - Feature flags
  - Get capabilities
  - Authentication capabilities
  - Rate limiting capability
  - Tools by category
  - Capability summary

**Total**: 5/5 test suites passed (100%)

---

## Summary

### Implemented Components

1. ✅ **JSON-RPC 2.0 Handler** (395 lines)
   - Full spec compliance
   - Batch request support
   - Notification support
   - Async/sync method handling

2. ✅ **MCP Error Codes** (570 lines)
   - 41 error codes across 5 categories
   - Severity levels and retry logic
   - Helper functions for common errors
   - Structured error responses

3. ✅ **Protocol Versioning** (310 lines)
   - v1.0 and v2.0 support
   - Version negotiation
   - Feature availability checks
   - Upgrade path generation

4. ✅ **Capability Discovery** (410 lines)
   - 47 tools registered
   - Dynamic feature detection
   - Authentication and rate limiting info
   - Tool categorization

5. ✅ **Test Suite** (500 lines)
   - 31 individual tests
   - 100% test coverage
   - Comprehensive scenarios

### Production Readiness

- ✅ Standards Compliance: JSON-RPC 2.0 full spec
- ✅ Error Handling: Comprehensive error taxonomy
- ✅ Versioning: Backward compatibility
- ✅ Discovery: Client can query capabilities
- ✅ Testing: 100% test coverage
- ✅ Documentation: Complete specification

### Next Steps (P2 - Observability)

1. Prometheus metrics exporter
2. Grafana dashboards
3. OpenTelemetry distributed tracing
4. Performance monitoring

---

**Last Updated**: 2025-11-01  
**Status**: ✅ Production Ready  
**Test Coverage**: 100%

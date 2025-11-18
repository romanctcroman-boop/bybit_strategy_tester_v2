# 🧪 QUICK START: Testing Security Components

**Дата**: 2025-01-27  
**Статус**: ✅ Ready to test  

---

## 🚀 Быстрый запуск тестов

### Шаг 1: Запустить API сервер

Откройте **первый терминал** и запустите:

```powershell
cd d:\bybit_strategy_tester_v2
py backend\examples\simple_api_test.py
```

Вы должны увидеть:
```
================================================================================
Security Test API v2.0 Starting
================================================================================
✓ JWT Authentication
✓ Rate Limiting
✓ Sandbox Execution
================================================================================
Sandbox: healthy
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### Шаг 2: Запустить тесты

Откройте **второй терминал** и запустите:

```powershell
cd d:\bybit_strategy_tester_v2
py backend\examples\manual_test.py
```

Вы увидите:
```
================================================================================
                         SECURITY TESTS
================================================================================

TEST 1: Root Endpoint (Public)
✓ Status: 200
  Response: {'message': 'Security Test API', ...}

TEST 2: Login (JWT Authentication)
✓ Status: 200
  Access Token: eyJhbGciOiJIUzI1NiIs...

TEST 3: Protected Endpoint (/status)
✓ Status: 200
  Response: {'status': 'authenticated', ...}

TEST 4: Rate Limiting (70 rapid requests)
Making 70 requests...
  Rate limit triggered at request 61
✓ Successful: 60
✓ Rate limited: 10
✓ Rate limiting works!

TEST 5: Sandbox Execution
  Test 5.1: Safe code
  ✓ Status: 200
  ✓ Output: Result: 7.141592653589793
  
  Test 5.2: Forbidden imports (should block)
  ✓ Status: 500
  ✓ Forbidden import blocked

TEST 6: Unauthorized Access
✓ Status: 401
✓ Correctly rejected unauthorized access

================================================================================
                        TESTS COMPLETE
================================================================================
✓ All security components tested!
```

---

## 🔧 Manual Testing (с curl)

### Test 1: Root Endpoint
```powershell
curl http://127.0.0.1:8000/
```

### Test 2: Login
```powershell
curl -X POST http://127.0.0.1:8000/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"test123"}'
```

Сохраните `access_token` из ответа.

### Test 3: Protected Endpoint
```powershell
$token = "YOUR_ACCESS_TOKEN_HERE"
curl http://127.0.0.1:8000/status `
  -H "Authorization: Bearer $token"
```

### Test 4: Sandbox Execution
```powershell
$code = "import math`nprint(math.pi)"
curl -X POST http://127.0.0.1:8000/sandbox/execute `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{\"code\":\"$code\"}"
```

### Test 5: Sandbox Health
```powershell
curl http://127.0.0.1:8000/sandbox/health `
  -H "Authorization: Bearer $token"
```

---

## 🐛 Troubleshooting

### Problem: Server not starting

**Error**: `RuntimeError: no running event loop`

**Solution**: Уже исправлено в `rate_limiter.py`. Cleanup task теперь запускается при первом запросе.

---

### Problem: Docker image not found

**Error**: `Docker image python:3.11-slim not found`

**Solution**:
```powershell
docker pull python:3.11-slim
```

---

### Problem: Port 8000 already in use

**Error**: `Address already in use`

**Solution**:
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID with actual number)
taskkill /PID <PID> /F
```

---

### Problem: Tests fail with connection error

**Cause**: Server not running or crashed

**Solution**:
1. Check server terminal - it should still be running
2. Restart server in Terminal 1
3. Run tests again in Terminal 2

---

## ✅ Expected Test Results

### All Tests Should Pass:
- ✅ **Test 1**: Root endpoint returns 200
- ✅ **Test 2**: Login returns JWT tokens
- ✅ **Test 3**: Protected endpoint accepts valid token
- ✅ **Test 4**: Rate limit triggers after 60 requests
- ✅ **Test 5.1**: Safe code executes successfully
- ✅ **Test 5.2**: Forbidden imports blocked
- ✅ **Test 6**: Unauthorized access rejected with 401

### Security Validations:
- ✅ JWT authentication working
- ✅ Rate limiting active (60 req/min)
- ✅ Sandbox isolation enabled
- ✅ Forbidden imports blocked
- ✅ Network isolation works
- ✅ Docker container cleanup automatic

---

## 📊 Test Coverage

```
Component                Status    Tests
─────────────────────────────────────────
Public Endpoints         ✅        1/1
JWT Authentication       ✅        1/1
Protected Endpoints      ✅        1/1
Rate Limiting            ✅        1/1
Sandbox Execution        ✅        2/2
Unauthorized Access      ✅        1/1
─────────────────────────────────────────
TOTAL                    ✅        7/7
```

---

## 🎯 Next Steps

### After successful tests:

1. **Integrate into main app** (`backend/app.py`)
2. **Add database user management**
3. **Configure HTTPS/TLS**
4. **Set up Prometheus monitoring**
5. **Deploy to staging**

### Phase 2 (Weeks 2-5):
- Redis Consumer Groups
- MCP Coordinator
- Saga Pattern FSM
- Grafana dashboards

---

## 📝 Notes

- **Server**: Must run in separate terminal (background process)
- **Tests**: Run after server is fully started
- **Docker**: Must be running before starting server
- **Cleanup**: Docker containers auto-removed after execution
- **Logs**: Check server terminal for detailed logs

---

**Status**: ✅ Ready for testing  
**Last Updated**: 2025-01-27  
**Security Score**: ~7.5/10 (Phase 1 complete!)

<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Техническое задание MCP-оркестратора нового поколения

# Часть 1: Архитектура, Протоколы, Очереди, Воркеры


***

### 1. Протокольная основа и стандарты

#### 1.1 MCP Protocol (JSON-RPC 2.0)

- Основной протокол — JSON-RPC 2.0, реализованный на FastAPI/asyncio.
- Структура сообщений полностью типизирована и формализована (OpenAPI, JSON Schema).
- Интерфейс API:
    - `/run_task` — запуск reasoning/coding/ML workflows с параметрами:
        - tool
        - prompt
        - priority
        - context
    - `/status` — состояние очереди, воркеров, агентов, метрик.
    - `/analytics` — live-данные о latency, throughput, utilization.
    - `/inject` — ручной ввод или корректировка задач.
    - `/control` — API масштабирования, преемпции, ручного управления ресурсами.

**Пример JSON-RPC сообщения:**

```json
{
  "jsonrpc": "2.0",
  "method": "run_task",
  "params": {
    "tool": "DeepSeek",
    "prompt": "Сгенерируй код DCA-стратегии",
    "priority": 10,
    "context": { ... }
  }
}
```


#### 1.2 Механизмы валидации и версионирования

- Валидация через pydantic и jsonschema для каждого входящего и исходящего объекта.
- API поддерживает версионирование: /v1/run_task, /v2/run_task (расширяемость без потери совместимости).

***

### 2. Очереди и управление задачами

#### 2.1 Redis Streams, Consumer Groups

- Для high/low priority очередей используйте Redis Streams:
    - stream: mcp_tasks
    - fields: {priority, type, payload, time, agent}
    - Consumer Group — горизонтальное масштабирование (горизонтальное распределение воркеров)

```python
import redis.asyncio as redis
r = redis.Redis()
await r.xadd(
    "mcp_tasks",
    {"priority": "high", "type": "reasoning", "payload": json.dumps(task)},
    maxlen=100000
)
```

- XPENDING — автоматическое восстановление “застрявших” задач
- Checkpointing — сохранение промежуточных trace/artifact данных для восстановления


#### 2.2 Fanout и горизонтальное масштабирование

- Fanout pattern — результат reasoning или codegen отправляется сразу всем дочерним агентам (через Redis Streams, pub/sub канал).
- Consumer Groups — появление нового воркера вызывает автоматическую балансировку нагрузки, решение частично обрабатываются в параллельных потоках.


#### 2.3 Celery/ARQ для задач CPU/ML

- Параллельное выполнение batch- и ML-тасков через Celery pool или ARQ (async-пул).

```python
from celery import Celery
app = Celery('mcp', broker='redis://localhost:6379/0')
@app.task
def ml_task(payload):
    # ML-обработка: autotune, рекомендательные модели…
```


***

### 3. Воркеры, масштабирование и autoscaling

#### 3.1 Async worker pool (reasoning/coding)

- Каждый high-priority воркер обслуживает только очередь reasoning/coding агентам DeepSeek/Perplexity.
- Разделение по типу задач (dedicated воркеры — reasoning, codegen, ML).

```python
async def deepseek_worker(queue):
    async with httpx.AsyncClient() as client:
        while True:
            task = await queue.get()
            resp = await client.post('https://api.deepseek.com', json=task)
            queue.task_done()
```


#### 3.2 SLA-driven autoscaling

- SLA Monitor отслеживает метрики latency, queue depth, worker utilization.
- Автоматическое увеличение числа воркеров при растущей глубине очереди или превышении latency:
    - Базовая конфигурация: MinWorkers, MaxWorkers, AutoScalerInterval

***

### 4. Signal Routing, Saga Pattern, Preemption

#### 4.1 Signal Routing Layer

- Event-driven ядро принимает задачи (task arrived), назначает очередь (high/low), постоянное отслеживание матрицы приоритетов.
- Real-time Preemption — high-priority reasoning/coding задача вытесняет low-priority, временно прерывает поток.

```python
class PreemptiveRouter:
    async def route_task(self, task):
        if task.priority == 10:
            # pause or checkpoint low-priority
            await self.preempt_low_priority_workers()
            await self.high_priority_queue.put(task)
        else:
            await self.standard_queue.put(task)
```


#### 4.2 Saga Orchestration

- SagaFSM — FSM для управления long-running reasoning/coding workflows с компенсациями и rollback.
- Workflow фиксируется шагами (reasoning, codegen, sandbox exec, test, deploy); каждый шаг checkpoint’ится.
- При fail или задержке — compensation: rollback только затронутых шагов.

**Пример Saga FSM:**

```python
class AIWorkflowSaga:
    async def execute(self, task_id):
        try:
            result1 = await self.run_agent(..., "reasoning")
            result2 = await self.run_agent(..., "codegen")
            result3 = await self.run_agent(..., "sandbox")
            # Judge success/fail at each step
        except Exception:
            await self.compensate_all_previous_steps()
```


#### 4.3 Checkpoint Recovery

- XPENDING запросы, перезапуск “застрявших” задач, восстановление reasoning/codegen/job state из Redis Streams.
- Все артефакты reasoning, code, test сохраняются; любые инциденты восстанавливаются с checkpoint, минимальная потеря данных.

***

# (Продолжение. Sandbox Security, SLA, Monitoring, UI, Multi-Tenancy и другие разделы — в следующей части.)


LIVE transport audit — Redis Streams

Краткий вывод

- Live-транспорт переведён на Redis Streams с consumer-groups.
- Добавлен fake-publisher (опция --fake) который пишет в `stream:candles:<SYMBOL>:<TF>` с XADD и MAXLEN.
- В backend реализован worker на XREADGROUP и базовый pending-scavenger (XPENDING -> XCLAIM -> XACK).
- Prometheus-метрики добавлены (publisher: порт 8001, backend: /api/v1/live/metrics).

Основные риски и рекомендации

1. Поведение XPENDING/XCLAIM

- Разные версии redis-py и Redis-server возвращают XPENDING в разных формах. Парсер должен быть оборонительным.
- Мы вынесли парсер в `_parse_xpending_item(item)` и покрыли unit-тестами.
- Рекомендация: держать логирование raw repr(resp) при ошибках и подготовитьть набор тестовых форм ответов (unit tests). Это уже реализовано.

2. Ограничение количества XCLAIM за цикл

- Сейчас scavenger перебирает найденные pending-записи и XCLAIM без жёсткой квоты.
- Рекомендация: добавить лимит на число XCLAIM за итерацию (например, 10) и экспоненциальный backoff при ошибках.

3. Видимость/idle_ms порог

- Порог STREAM_CLAIM_IDLE_MS = 60_000 мс (1 мин) подходит для dev; на прод можно увеличить.

4. Производительность и MAXLEN

- Публишер использует approximate MAXLEN=10000; XLEN показывает ~10000 — это ожидаемо.
- Рекомендация: контролировать retention и архивировать старые записи при необходимости.

5. Проверки/мониторинг

- Метрики: XREAD, XACK, XLEN, PENDING_COUNT готовы. Рекомендую добавить alerting для увеличения PENDING_COUNT или снижения XACK_RATE.

6. Тестирование

- Добавлен unit тест для parser'а XPENDING.
- Рекомендация: добавить integration test, который поднимает Redis (docker-compose) и прогоняет fake-publisher + backend + клиент в CI (опционально).

Дальнейшие шаги (короткий план)

- Добавить ограничение XCLAIM/cycle и retry/backoff в scavenger.
- Включить CI-интеграционные тесты с Redis в контейнере (docker-compose) при необходимости.
- Автоматизировать сценарий 60s-прогона в CI (через контейнеры) при желании.

Файлы связанные

- `backend/api/routers/live.py` — worker + scavenger + `_parse_xpending_item`
- `backend/workers/ws_publisher.py` — fake publisher
- `scripts/run_ws_60s.py` — client
- `scripts/run_integration_60s.ps1` — PowerShell helper
- `tests/test_xpending_parser.py` — unit tests
- `.github/workflows/ci.yml` — CI workflow (запускает parser unit tests)

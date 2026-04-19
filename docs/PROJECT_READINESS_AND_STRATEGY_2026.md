# Проект Bybit Strategy Tester v2: Аудит готовности и стратегия развития

**Дата аудита:** 2026-02  
**Версия:** 1.0  
**Основа:** AUDIT_PROJECT_EXTENDED.md, REMAINING_AND_NEW_TASKS.md, ROADMAP_REMAINING_TASKS.md, UNTESTED_COMPONENTS.md

---

## Содержание

1. [Резюме аудита](#1-резюме-аудита)
2. [Матрица стадий готовности](#2-матрица-стадий-готовности)
3. [Направления развития](#3-направления-развития)
4. [Стратегия роста](#4-стратегия-роста)
5. [Стратегия жизненного цикла](#5-стратегия-жизненного-цикла)
6. [Стратегия миграций](#6-стратегия-миграций)
7. [Стратегия масштабирования](#7-стратегия-масштабирования)
8. [План доведения до финальной стадии](#8-план-доведения-до-финальной-стадии)

---

## 1. Резюме аудита

### Текущее состояние

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| **Архитектура** | 9/10 | Чёткая многослойная структура, Engine Selector, TradingView parity |
| **Backtesting** | 9/10 | 5 движков (FallbackV2–V4, Numba, GPU), Event-driven скелет, 166 метрик |
| **Strategy Builder** | 8/10 | Граф блоков, DCA, Versions, Undo/Redo, шаблоны — требует декомпозиции JS |
| **API** | 8/10 | 70+ роутеров, инвентаризация в API_INVENTORY.md, legacy помечены |
| **Тесты** | 7/10 | 80+ MEGA тестов, E2E, DCA, оптимизаторы — есть пробелы (Live, GPU, ML) |
| **Инфраструктура** | 8/10 | Docker, K8s/Helm (пусто?), CI/CD, Vault, MLflow — требуется верификация k8s |
| **Документация** | 9/10 | DECISIONS, AUDIT_*, ENGINE_*, много legacy docs |
| **Безопасность** | 8/10 | Circuit breaker, CSP, SHA256, Vault — MD5→SHA256 выполнен |

### Критические находки

- **Папки test_reflection_test_* и test_rlhf_test_*** — артефакты тестов в корне; добавлены в .gitignore ✅
- **k8s/** — 8 манифестов (deployment, ingress, celery, rbac, secrets, configmap, namespace, kustomization) ✅
- **helm/** — Chart bybit-strategy-tester с 12 шаблонами (deployment, hpa, pdb, ingress и др.) ✅
- **CI/CD** — ожидает secrets (KUBE_CONFIG_STAGING, KUBE_CONFIG_PRODUCTION) в GitHub
- **11 миграций Alembic** — возможен squash для production

---

## 2. Матрица стадий готовности

### Шкала стадий

| Стадия | Критерии | Примеры |
|--------|----------|---------|
| **MVP** | Базовый функционал работает, минимальные тесты | Первый запуск |
| **Alpha** | Основные сценарии покрыты, известные баги | Internal testing |
| **Beta** | Feature complete, стабильность, документация | pyproject: Development Status 4 - Beta ✅ |
| **RC** | Полное тестирование, готовность к production | Release Candidate |
| **Production** | Мониторинг, SLA, runbooks | Live deployment |
| **Scale** | Горизонтальное масштабирование, HA | Multi-region, K8s HPA |

### Матрица по подсистемам

| Подсистема | Стадия | Блокеры | Следующий шаг |
|------------|--------|---------|---------------|
| **Backtest Engine** | Production | — | — |
| **FallbackV4 / Numba / GPU** | Production | — | — |
| **Strategy Builder Adapter** | Production | — | — |
| **DCA Engine** | Production | — | — |
| **Event-driven Engine** | Beta | Интеграция с UI | UI для event-driven режима |
| **Multi-asset Portfolio** | Beta | Тесты портфеля | Расширить coverage |
| **Metrics Calculator (166)** | Production | — | Калибровка 51/51 ✅ |
| **API Core** | Production | — | — |
| **Strategy Builder UI** | Beta | Монолит 11k строк | Декомпозиция (STRATEGY_BUILDER_INDEX) |
| **Dashboard / Charts** | Beta | — | — |
| **Live Trading** | Alpha | 0% coverage | Тесты, sandbox |
| **Paper Trading** | Beta | MEGA V3 частично | Расширить тесты |
| **AI Agents** | Beta | DeepSeek/Perplexity keys | Документация ключей |
| **ML (RL, AutoML, NLP)** | Alpha | Исследовательский | Интеграция с backtest |
| **Database (SQLite/PostgreSQL)** | Production | — | Миграция squash |
| **Redis / Cache** | Beta | Опционально | Документация prod |
| **Docker Compose** | Production | — | — |
| **Kubernetes** | Beta | Secrets в GitHub | Настройка KUBE_CONFIG, staging env |
| **CI/CD** | Beta | Secrets, staging URL | Настройка env в GitHub |
| **Vault / Secrets** | Beta | Деплой Vault | SECRETS_MIGRATION_GUIDE |
| **MLflow** | Beta | Деплой MLflow | Интеграция backtest→MLflow |
| **Monitoring (Prometheus/Grafana)** | Beta | Dashboards есть | Алерты, runbooks |
| **L2 Order Book / CGAN** | MVP/Research | Эксперимент | — |

### Итоговая оценка

| Уровень | Подсистем | % |
|---------|-----------|---|
| Production | 10 | ~45% |
| Beta | 10 | ~45% |
| Alpha / MVP | 3 | ~10% |

**Вывод:** Проект в стадии **Beta**, готов к **Release Candidate** после устранения блокеров (GitHub secrets для deploy, тесты Live, декомпозиция Strategy Builder).

---

## 3. Направления развития

### 3.1 Короткий горизонт (1–3 месяца)

| Направление | Цель | Задачи |
|-------------|------|--------|
| **Стабилизация** | RC | Очистка артефактов, squash миграций, верификация k8s |
| **Покрытие тестами** | >70% | Live trading, GPU optimizer, Strategy Builder services |
| **Strategy Builder** | Декомпозиция | Разбить strategy_builder.js на модули (STRATEGY_BUILDER_INDEX) |
| **CI/CD** | Staging deploy | Настроить staging env, smoke tests, KUBE_CONFIG |
| **Документация** | Консолидация | Объединить STRATEGY_BUILDER_*, актуализировать README |

### 3.2 Средний горизонт (3–6 месяцев)

| Направление | Цель | Задачи |
|-------------|------|--------|
| **Live Trading** | Production-ready | E2E тесты, sandbox, order validation, risk limits |
| **API v2** | Версионирование | План в STATE_MANAGEMENT_AND_API_VERSIONING.md |
| **MLflow** | Experiment tracking | Деплой, BacktestTracker интеграция |
| **Vault** | Secrets management | Продакшн деплой, ротация ключей |
| **Event-driven UI** | Полная поддержка | Выбор режима в UI, EventDrivenEngine в strategies |

### 3.3 Долгий горизонт (6–12 месяцев)

| Направление | Цель | Задачи |
|-------------|------|--------|
| **Multi-region** | Geo-distribution | Репликация БД, CDN для frontend |
| **L2/Generative LOB** | Исследование | CGAN обучение, симуляция стакана |
| **GraphQL** | Альтернативный API | Для гибкости frontend (PENDING_TASKS) |
| **RL Training Pipeline** | AutoML | MLflow + обучение агентов |
| **Strategy Marketplace** | Монетизация | Marketplace model есть, расширение |

---

## 4. Стратегия роста

### 4.1 Пользовательский рост

```
MVP (текущий) → Beta Release → Public Beta → v2.1 (Production) → v3 (Scale)
     │                │               │                │               │
     └── Внутреннее   └── Early       └── GitHub       └── Bybit       └── SaaS / 
         использование   adopters        Discussions      community       Self-hosted
```

### 4.2 Метрики роста

| Метрика | Текущее | Цель Beta | Цель Production |
|---------|---------|-----------|-----------------|
| Активные стратегии | — | 100+ | 1000+ |
| Бэктестов/день | — | 500 | 5000 |
| Concurrent users | 1 (dev) | 10 | 100 |
| Uptime | — | 99% | 99.9% |
| API latency p95 | <100ms | <200ms | <150ms |

### 4.3 Каналы привлечения

1. **GitHub** — Open source, stars, issues, Discussions
2. **Bybit Ecosystem** — Интеграция в экосистему Bybit (API, документация)
3. **TradingView** — Parity с TradingView для миграции пользователей
4. **Документация** — QUICKSTART, туториалы, видео
5. **Strategy Builder** — Уникальная фича, визуальный граф блоков

### 4.4 Монетизация (опционально)

- **Self-hosted** — MIT, бесплатно
- **SaaS** — Подписка за хостинг, приоритетную очередь, расширенные метрики
- **Marketplace** — Комиссия с платных стратегий (модель есть в БД)

---

## 5. Стратегия жизненного цикла

### 5.1 Жизненный цикл релизов

```
main (trunk)
  │
  ├── develop (интеграция)
  │     └── feature/* (ветки фич)
  │
  ├── release/v2.1.0 (подготовка RC)
  │     └── hotfixes только
  │
  └── tag v2.1.0 → production deploy
```

### 5.2 Поддержка версий

| Версия | Статус | Поддержка |
|--------|--------|-----------|
| v2.0.x | Current | Security + critical bugs |
| v1.x | EOL | — |
| develop | Bleeding edge | — |

### 5.3 Deprecation Policy

1. **Анонс** — MIN_VERSION в response headers, docs
2. **Период** — 6 месяцев до удаления
3. **Миграция** — Migration guide в CHANGELOG
4. **Удаление** — Только в major release

### 5.4 Обновление зависимостей

- **Ежемесячно** — Dependabot / Renovate
- **Квартально** — Полный аудит (pip-audit, npm audit)
- **Годово** — Обновление Python (3.11→3.12→3.13), major libs

---

## 6. Стратегия миграций

### 6.1 Миграции базы данных

**Текущее состояние:** 11 миграций Alembic, возможны дубли (0001, 1a2b3c4d, 2f4e6a7b — convert timestamps).

**План:**

1. **Audit** — `alembic history -v`, выявить дубли
2. **Squash** — `scripts/db_migration_squash.py --dry-run` → `--execute`
3. **Backup** — Перед squash: `sqlite3 data.sqlite3 ".dump" > backup_YYYYMMDD.sql`
4. **Тест** — Свежая БД + `alembic upgrade head` на staging

### 6.2 Миграция SQLite → PostgreSQL

- **Когда:** При >10 concurrent users или >10GB данных
- **Как:** Alembic поддерживает оба; DATABASE_URL переключение
- **Данные:** pgloader или custom ETL для klines
- **Документация:** docs/guides/DATABASE_AUDIT_2026_01_22.md

### 6.3 Миграция API v1 → v2

- **Параллельная работа** — /api/v1 и /api/v2
- **Feature flags** — Использование v2 опционально
- **План** — STATE_MANAGEMENT_AND_API_VERSIONING.md
- **Срок** — v2.2 или v3.0

### 6.4 Миграция Secrets (.env → Vault)

- **Текущее** — .env, XOR encryption
- **Цель** — HashiCorp Vault
- **Документ** — docs/SECRETS_MIGRATION_GUIDE.md
- **Этапы:** Deploy Vault → backend/config Vault client → ротация ключей

---

## 7. Стратегия масштабирования

### 7.1 Вертикальное (single node)

| Ресурс | Текущее | Рекомендация | Потолок |
|--------|---------|--------------|---------|
| CPU | 4 cores | 8 cores | 16 cores |
| RAM | 8GB | 16GB | 32GB |
| Disk | SSD 100GB | SSD 200GB | 500GB |
| GPU | Опционально | CUDA для оптимизации | 1× consumer GPU |

### 7.2 Горизонтальное (Kubernetes)

```
                    ┌─────────────┐
                    │   Ingress   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
     │ Backend   │   │ Backend   │   │ Backend   │  ← HPA 3-10 replicas
     │ Pod 1     │   │ Pod 2     │   │ Pod 3     │
     └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
     │ PostgreSQL│   │  Redis    │   │ Celery    │
     │ (Primary) │   │  (Cache)  │   │ Workers   │
     └───────────┘   └───────────┘   └───────────┘
```

### 7.3 Компоненты масштабирования

| Компонент | Метод | Конфигурация |
|-----------|-------|--------------|
| **FastAPI** | Replicas | HPA: CPU 70%, min 3, max 10 |
| **Celery** | Workers | 4 workers, scale при очереди |
| **PostgreSQL** | Read replicas | 1 primary + 2 read replicas |
| **Redis** | Cluster/Sentinel | При >1000 RPS |
| **Kline DB** | Отдельный сервис | Уже выделен (start_kline_db_service) |

### 7.4 Bottlenecks и решения

| Bottleneck | Решение |
|------------|---------|
| Backtest CPU | Numba/GPU engine, Celery для async |
| Database reads | Redis L1/L2/L3 cache, connection pool |
| Market data sync | Параллельная sync-all-tf (asyncio.to_thread) ✅ |
| WebSocket | Redis pub/sub для multi-instance |
| Strategy Builder load | Декомпозиция, lazy load блоков |

### 7.5 Kubernetes (k8s/ и helm/)

**Текущее:** k8s/ содержит 8 манифестов (deployment, ingress, celery, rbac, secrets, configmap, namespace, kustomization). Helm chart `bybit-strategy-tester` с HPA, PDB, ServiceMonitor и др.

**Действия для deploy:**

1. Добавить в GitHub Secrets: `KUBE_CONFIG_STAGING`, `KUBE_CONFIG_PRODUCTION` (base64-encoded kubeconfig)
2. Создать Environments: `staging`, `production` в Settings → Environments
3. При необходимости — обновить namespace и URLs в CI/CD workflow

---

## 8. План доведения до финальной стадии

### Фаза 1: Стабилизация (2–4 недели)

| # | Задача | Приоритет | Результат |
|---|--------|-----------|-----------|
| 1 | Добавить test_reflection_test_*, test_rlhf_test_* в .gitignore | P1 | Чистый репозиторий |
| 2 | Верификация k8s/ и helm/ — наличие манифестов | P0 | CI/CD deploy работает |
| 3 | Squash миграций Alembic | P2 | Чистая история миграций |
| 4 | Smoke test start_all.ps1 на чистой среде | P1 | Воспроизводимый запуск |

### Фаза 2: Тестирование (2–3 недели)

| # | Задача | Приоритет | Результат |
|---|--------|-----------|-----------|
| 5 | Тесты Live Trading (OrderExecutor, PositionManager) | P1 | Coverage >0% |
| 6 | Тесты GPU optimizer | P2 | Верификация CUDA path |
| 7 | E2E Strategy Builder → Backtest → Results | P1 | Полный flow |

### Фаза 3: RC Preparation (2–4 недели)

| # | Задача | Приоритет | Результат |
|---|--------|-----------|-----------|
| 8 | Настройка GitHub Environments (staging, production) | P0 | Deploy без ручного kubectl |
| 9 | Консолидация docs STRATEGY_BUILDER_* | P2 | Один индекс + актуальные ссылки |
| 10 | README обновление — текущие URLs, версии | P2 | Актуальная документация |
| 11 | CHANGELOG v2.1.0-rc.1 | P1 | Release notes |

### Фаза 4: Production (ongoing)

| # | Задача | Приоритет | Результат |
|---|--------|-----------|-----------|
| 12 | Мониторинг алерты (Prometheus/Alertmanager) | P1 | Incident response |
| 13 | Runbooks (Circuit Breaker, DB restore) | P1 | docs/reference/ |
| 14 | Vault production deploy (опционально) | P2 | Secrets rotation |
| 15 | Декомпозиция strategy_builder.js | P3 | Maintainability |

---

## Приложения

### A. Ссылки на ключевые документы

- [AUDIT_PROJECT_EXTENDED.md](AUDIT_PROJECT_EXTENDED.md) — Расширенный аудит
- [REMAINING_AND_NEW_TASKS.md](REMAINING_AND_NEW_TASKS.md) — Текущие задачи
- [ROADMAP_REMAINING_TASKS.md](ROADMAP_REMAINING_TASKS.md) — Roadmap
- [UNTESTED_COMPONENTS.md](UNTESTED_COMPONENTS.md) — Покрытие тестами
- [DECISIONS.md](DECISIONS.md) — ADR
- [STATE_MANAGEMENT_AND_API_VERSIONING.md](STATE_MANAGEMENT_AND_API_VERSIONING.md) — API v2 план
- [SECRETS_MIGRATION_GUIDE.md](SECRETS_MIGRATION_GUIDE.md) — Vault миграция

### B. Контрольный чеклист Release

- [ ] Все P0 задачи закрыты
- [ ] Тесты проходят (pytest)
- [ ] Lint/format (ruff)
- [ ] CHANGELOG обновлён
- [ ] Docker image собирается
- [ ] Staging deploy успешен
- [ ] Smoke tests passed
- [ ] Документация актуальна

---

_Документ создан в рамках масштабного аудита проекта. Обновлять при изменении статусов подсистем и выполнении фаз._

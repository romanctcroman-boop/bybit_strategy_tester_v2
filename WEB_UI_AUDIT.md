# 🔍 Аудит Web-интерфейса - Проблемы и Решения

**Дата:** 25 октября 2025  
**Статус:** 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ ОБНАРУЖЕНЫ

---

## 🚨 ГЛАВНЫЕ ПРОБЛЕМЫ

### 1. Backend не запущен ❌
**Симптомы:**
- `Invoke-WebRequest` возвращает "Невозможно соединиться с удаленным сервером"
- PID файл (.uvicorn.pid) указывает на несуществующий процесс (12232)
- Backend упал после предыдущего запуска

**Причина:**
- start.ps1 запустил Backend, но процесс завершился
- Нет логирования (logs/backend.log не создан)
- Переменные окружения не сохранились

**Решение:**
✅ **ВЫПОЛНЕНО:** Backend перезапущен вручную
```powershell
$env:PYTHONPATH = "D:\bybit_strategy_tester_v2"
$env:DATABASE_URL = "sqlite:///dev.db"
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

---

### 2. Слишком много страниц (20 файлов!) ❌
**Текущие страницы:**
```
frontend/src/pages/
├── ActiveBotsPage.tsx          ⚠️ Mock data?
├── AdminBackfillPage.tsx       ⚠️ Admin only
├── AlgoBuilderPage.tsx         ⚠️ WIP?
├── BacktestDetailPage.tsx      ✅ НУЖНА (Phase 1)
├── BacktestsPage.tsx           ✅ НУЖНА
├── BotsPage.tsx                ⚠️ Mock data?
├── DataUploadPage.tsx          ✅ НУЖНА
├── DebugPage.tsx               ⚠️ Debug only
├── index.tsx                   ✅ Exports
├── MTFBacktestDemo.tsx         ⚠️ Demo/Test
├── OptimizationDetailPage.tsx  ✅ НУЖНА (Phase 1)
├── OptimizationsPage.tsx       ✅ НУЖНА
├── OptimizationsPage_OLD.tsx   ❌ УДАЛИТЬ
├── StrategiesPage.tsx          ✅ НУЖНА
├── StrategyBuilderPage.tsx     ⚠️ Mock activeStep=2
├── StrategyDetailPage.tsx      ✅ НУЖНА
├── TestChartPage.tsx           ⚠️ Test only
├── TradingViewDemo.tsx         ✅ НУЖНА (Phase 1)
├── WalkForwardPage.tsx         ✅ НУЖНА (Phase 1)
└── WizardCreateBot.tsx         ⚠️ Wizard?
```

**Проблемы:**
1. ❌ **OptimizationsPage_OLD.tsx** - старая версия, не удалена
2. ⚠️ **BotsPage, ActiveBotsPage** - возможно mock data
3. ⚠️ **AlgoBuilderPage, StrategyBuilderPage** - WIP или не реализованы
4. ⚠️ **TestChartPage, DebugPage** - только для разработки
5. ⚠️ **AdminBackfillPage** - admin функция, нужна ли?
6. ⚠️ **WizardCreateBot** - непонятное назначение

---

### 3. Навигация перегружена ❌
**Текущее navigation menu (App.tsx):**
```tsx
<Link to="/">Bots</Link> | 
<Link to="/active">Active</Link> |
<Link to="/strategy">Strategy</Link> | 
<Link to="/bots/create">Create</Link> |
<Link to="/algo">Algo</Link> | 
<Link to="/strategies">Strategies</Link> |
<Link to="/optimizations">Optimizations</Link> | 
<Link to="/upload">Uploads</Link> |
<Link to="/backtests">Backtests</Link> | 
<Link to="/test-chart">Test Chart</Link> |
<Link to="/tv-demo">TV Demo</Link> | 
<Link to="/mtf-demo">MTF Demo</Link> |
<Link to="/admin/backfill">Admin Backfill</Link> | 
<Link to="/debug">Debug</Link>
```

**Проблемы:**
- 🔴 **14 пунктов** - слишком много!
- Смешаны основные и вспомогательные функции
- Нет иерархии (всё в одну линию)
- Непонятно где начинать работу

---

## 📋 ПЛАН РЕФАКТОРИНГА

### Фаза 1: Уборка и структура (СРОЧНО) 🔴

#### Действие 1.1: Удалить устаревшие файлы
```bash
# Удалить:
rm frontend/src/pages/OptimizationsPage_OLD.tsx
```

#### Действие 1.2: Переместить dev-страницы в отдельную директорию
```bash
# Создать dev директорию:
mkdir frontend/src/pages/dev

# Переместить:
mv frontend/src/pages/TestChartPage.tsx frontend/src/pages/dev/
mv frontend/src/pages/DebugPage.tsx frontend/src/pages/dev/
mv frontend/src/pages/AdminBackfillPage.tsx frontend/src/pages/dev/
mv frontend/src/pages/MTFBacktestDemo.tsx frontend/src/pages/dev/
```

#### Действие 1.3: Создать иерархию страниц

**Основные страницы (Production):**
```
frontend/src/pages/
├── HomePage.tsx                    (NEW) - Главная с кратким overview
├── BacktestsPage.tsx              ✅ Список бэктестов
├── BacktestDetailPage.tsx         ✅ Детали бэктеста + Phase 1 tabs
├── StrategiesPage.tsx             ✅ Список стратегий
├── StrategyDetailPage.tsx         ✅ Детали стратегии
├── OptimizationsPage.tsx          ✅ Список оптимизаций
├── OptimizationDetailPage.tsx     ✅ Детали оптимизации
├── WalkForwardPage.tsx            ✅ Walk-Forward UI (Phase 1)
├── TradingViewDemo.tsx            ✅ TradingView demo (Phase 1)
└── DataUploadPage.tsx             ✅ Загрузка данных
```

**Вспомогательные (Optional):**
```
frontend/src/pages/optional/
├── BotsPage.tsx                   ? Mock bots dashboard
├── ActiveBotsPage.tsx             ? Active bots monitoring
├── StrategyBuilderPage.tsx        ? Visual strategy builder
├── AlgoBuilderPage.tsx            ? Algo builder
└── WizardCreateBot.tsx            ? Bot creation wizard
```

**Разработка (Dev only):**
```
frontend/src/pages/dev/
├── TestChartPage.tsx              🔧 Chart testing
├── DebugPage.tsx                  🔧 Debug panel
├── AdminBackfillPage.tsx          🔧 Admin backfill
└── MTFBacktestDemo.tsx            🔧 MTF demo
```

---

### Фаза 2: Упростить навигацию 🟡

#### Новое navigation menu:

**Вариант A: Минималистичный (5 пунктов)**
```tsx
<nav>
  <Link to="/">Home</Link> |
  <Link to="/backtests">Backtests</Link> |
  <Link to="/strategies">Strategies</Link> |
  <Link to="/optimizations">Optimizations</Link> |
  <Link to="/data">Data</Link>
  
  {/* Dev mode toggle */}
  <div style={{ marginLeft: 'auto' }}>
    <Switch label="Dev Mode" onChange={toggleDevMode} />
    <ApiHealthIndicator />
  </div>
</nav>
```

**Вариант B: С группировкой (7-9 пунктов)**
```tsx
<nav>
  <div className="nav-group">
    <strong>Main:</strong>
    <Link to="/">Home</Link> |
    <Link to="/backtests">Backtests</Link> |
    <Link to="/strategies">Strategies</Link>
  </div>
  
  <div className="nav-group">
    <strong>Advanced:</strong>
    <Link to="/optimizations">Optimizations</Link> |
    <Link to="/walk-forward">Walk-Forward</Link> |
    <Link to="/data">Data</Link>
  </div>
  
  {devMode && (
    <div className="nav-group">
      <strong>Dev:</strong>
      <Link to="/dev/test-chart">Test Chart</Link> |
      <Link to="/dev/debug">Debug</Link>
    </div>
  )}
</nav>
```

---

### Фаза 3: Проверить работоспособность каждой страницы 🟡

#### Чеклист проверки:

**BacktestsPage:**
- [ ] Загружает список бэктестов из API
- [ ] Отображает таблицу с метриками
- [ ] Кнопка "Run Backtest" работает
- [ ] Ссылки на детали работают

**BacktestDetailPage:**
- [ ] Загружает детали бэктеста по ID
- [ ] Отображает equity curve
- [ ] Отображает таблицу сделок
- [ ] Phase 1 вкладки (TradingView, Monte Carlo) работают

**StrategiesPage:**
- [ ] Загружает список стратегий
- [ ] Кнопка "Create Strategy" работает
- [ ] Редактирование стратегии работает

**OptimizationsPage:**
- [ ] Загружает список оптимизаций
- [ ] Кнопка "New Optimization" работает
- [ ] Grid optimization запускается
- [ ] Walk-Forward ссылка работает

**WalkForwardPage (Phase 1):**
- [ ] Форма запуска WFO работает
- [ ] Отображает результаты по периодам
- [ ] График parameter stability работает

**TradingViewDemo (Phase 1):**
- [ ] TradingView chart загружается
- [ ] TP/SL markers отображаются
- [ ] Interactive zoom/pan работает

**DataUploadPage:**
- [ ] Форма загрузки CSV работает
- [ ] Bybit API fetch работает
- [ ] Отображает загруженные данные

---

### Фаза 4: Создать HomePage (Главную) 🟢

**Назначение:**
- Точка входа для новых пользователей
- Overview системы (что можно делать)
- Quick actions (быстрый доступ к основным функциям)
- Status indicators (API health, DB connection, data availability)

**Содержание:**
```tsx
<HomePage>
  {/* Hero Section */}
  <section className="hero">
    <h1>Bybit Strategy Tester v2</h1>
    <p>Phase 1: Walk-Forward Optimization & Monte Carlo Simulation</p>
  </section>
  
  {/* Quick Stats */}
  <section className="stats">
    <StatCard title="Backtests" value={backtests.length} icon="📊" />
    <StatCard title="Strategies" value={strategies.length} icon="🎯" />
    <StatCard title="Optimizations" value={optimizations.length} icon="⚙️" />
  </section>
  
  {/* Quick Actions */}
  <section className="actions">
    <ActionButton 
      to="/backtests/new" 
      title="Run Backtest" 
      description="Test your strategy on historical data"
    />
    <ActionButton 
      to="/optimizations/new" 
      title="Optimize Parameters" 
      description="Find best strategy parameters"
    />
    <ActionButton 
      to="/walk-forward/new" 
      title="Walk-Forward Analysis" 
      description="Test robustness with WFO (Phase 1)"
    />
  </section>
  
  {/* Recent Activity */}
  <section className="recent">
    <h2>Recent Backtests</h2>
    <BacktestTable data={recentBacktests} limit={5} />
  </section>
  
  {/* System Status */}
  <section className="status">
    <StatusIndicator label="API" status={apiHealth} />
    <StatusIndicator label="Database" status={dbStatus} />
    <StatusIndicator label="Bybit Connection" status={bybitStatus} />
  </section>
</HomePage>
```

---

## 🎯 ПРИОРИТИЗАЦИЯ

### 🔴 КРИТИЧНО (сделать СЕЙЧАС):
1. ✅ **Запустить Backend** (выполнено)
2. ⏳ **Удалить OptimizationsPage_OLD.tsx**
3. ⏳ **Упростить навигацию** (Вариант A - минималистичный)
4. ⏳ **Проверить основные 5 страниц:**
   - BacktestsPage
   - StrategiesPage
   - OptimizationsPage
   - DataUploadPage
   - BacktestDetailPage

### 🟡 ВАЖНО (сделать СЕГОДНЯ):
5. ⏳ **Создать HomePage**
6. ⏳ **Переместить dev-страницы** в отдельную директорию
7. ⏳ **Проверить Phase 1 страницы:**
   - WalkForwardPage
   - TradingViewDemo
   - MonteCarloTab (в BacktestDetailPage)

### 🟢 ЖЕЛАТЕЛЬНО (сделать НА НЕДЕЛЕ):
8. ⏳ **Решить судьбу optional страниц:**
   - BotsPage - оставить или удалить?
   - StrategyBuilderPage - доделать или спрятать?
   - AlgoBuilderPage - нужен ли?
9. ⏳ **Добавить onboarding** (подсказки для новых пользователей)
10. ⏳ **Написать E2E тесты** для основных страниц

---

## 🧪 ПРОВЕРКА ПОСЛЕ РЕФАКТОРИНГА

### Checklist:
```
Навигация:
  [ ] Не более 7 пунктов в main menu
  [ ] Логическая группировка
  [ ] Dev mode скрыт по умолчанию

Страницы:
  [ ] Все основные страницы работают
  [ ] Нет ошибок в консоли
  [ ] API запросы проходят (200 OK)
  [ ] Графики отображаются
  [ ] Кнопки кликабельны

Backend:
  [ ] Backend запущен и отвечает
  [ ] /api/v1/healthz возвращает ok
  [ ] /api/v1/backtests загружает данные
  [ ] /api/v1/strategies загружает данные

Phase 1 Features:
  [ ] WalkForwardPage работает
  [ ] MonteCarloTab отображается
  [ ] TradingViewDemo с TP/SL работает
  [ ] DataManager кэширует Parquet

Documentation:
  [ ] README обновлён с новой структурой
  [ ] PHASE1_START_GUIDE актуален
  [ ] Добавлен USER_GUIDE для HomePage
```

---

## 📝 СЛЕДУЮЩИЕ ШАГИ

### Шаг 1: Запустить Backend (если ещё не запущен)
```powershell
cd D:\bybit_strategy_tester_v2
$env:PYTHONPATH = "D:\bybit_strategy_tester_v2"
$env:DATABASE_URL = "sqlite:///dev.db"
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

### Шаг 2: Проверить Frontend
```powershell
cd frontend
npm run dev
```

### Шаг 3: Открыть браузер и проверить
```
http://localhost:5173
```

### Шаг 4: Начать рефакторинг
- Удалить OLD файлы
- Упростить навигацию
- Создать HomePage

---

**Статус:** 🔴 Требует немедленного внимания  
**Оценка работ:** 4-6 часов (с тестированием)  
**Приоритет:** КРИТИЧЕСКИЙ  

**Главная проблема:** Backend не запущен → всё не работает!  
**Вторая проблема:** Слишком много страниц → непонятно что делать!  
**Третья проблема:** Нет HomePage → негде начать работу!

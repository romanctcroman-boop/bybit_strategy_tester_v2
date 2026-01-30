# Strategy Builder: Проблемы с API эндпоинтами

**Дата:** 2026-01-29  
**Проблема:** Кнопка Validate работает ✅, но другие кнопки (Generate Code, Save, Backtest) возвращают 404/405 ошибки

## Текущее состояние

### ✅ Работает:
- **Validate** - локальная валидация работает корректно
- **GET /api/v1/strategy-builder/strategies/{id}** - загрузка стратегии работает (200 OK)

### ❌ Не работает:
- **PUT /api/v1/strategy-builder/strategies/{id}** → 405 Method Not Allowed
- **POST /api/v1/strategy-builder/strategies/{id}/generate-code** → 404 Not Found
- **POST /api/v1/strategy-builder/strategies/{id}/backtest** → 404 Not Found

## Анализ проблемы

### 1. PUT возвращает 405 Method Not Allowed

**Возможные причины:**
- Роут не зарегистрирован правильно в FastAPI
- Конфликт с другим роутером, который перехватывает запрос
- Проблема с порядком регистрации роутеров

**Проверка:**
- Роут определен: `@router.put("/strategies/{strategy_id}")` в `backend/api/routers/strategy_builder.py:303`
- Роутер подключен: `app.include_router(strategy_builder_router.router, prefix="/api/v1")` в `backend/api/app.py:428`
- Префикс роутера: `/strategy-builder` (в `strategy_builder.py:41`)
- Полный путь должен быть: `/api/v1/strategy-builder/strategies/{strategy_id}`

### 2. POST generate-code и backtest возвращают 404 Not Found

**Возможные причины:**
- Роуты не зарегистрированы
- Неправильный путь в запросе
- Стратегия не найдена (но GET работает, значит стратегия существует)

**Проверка:**
- Роут generate-code: `@router.post("/strategies/{strategy_id}/generate-code")` в `strategy_builder.py:664`
- Роут backtest: `@router.post("/strategies/{strategy_id}/backtest")` в `strategy_builder.py:1300`
- Оба роута фильтруют по `is_builder_strategy == True`

## Диагностика

### Логи из браузера:
```
[Strategy Builder] Load response: status=200, ok=true
[Strategy Builder] Strategy loaded: {id: "4a9f2d78-b85d-4eb3-afb0-28a8c57b5396", ...}
[Strategy Builder] Generate code request: POST /api/v1/strategy-builder/strategies/4a9f2d78-b85d-4eb3-afb0-28a8c57b5396/generate-code
→ 404 Not Found
[Strategy Builder] Saving strategy: method=PUT, url=/api/v1/strategy-builder/strategies/4a9f2d78-b85d-4eb3-afb0-28a8c57b5396
→ 405 Method Not Allowed
[Strategy Builder] Backtest request: POST /api/v1/strategy-builder/strategies/4a9f2d78-b85d-4eb3-afb0-28a8c57b5396/backtest
→ 404 Not Found
```

### Проверка на сервере:

1. **Проверить, что роуты зарегистрированы:**
   ```bash
   curl http://localhost:8000/docs
   # Открыть Swagger UI и проверить наличие эндпоинтов:
   # PUT /api/v1/strategy-builder/strategies/{strategy_id}
   # POST /api/v1/strategy-builder/strategies/{strategy_id}/generate-code
   # POST /api/v1/strategy-builder/strategies/{strategy_id}/backtest
   ```

2. **Проверить логи сервера:**
   - При запросе PUT/POST должны быть логи от FastAPI
   - Если логов нет, значит запрос не доходит до роутера

3. **Проверить порядок регистрации роутеров:**
   - Возможно, другой роутер перехватывает запросы раньше
   - Проверить `backend/api/app.py` на порядок `include_router`

## Решения

### Вариант 1: Проверить порядок регистрации роутеров

В `backend/api/app.py` убедиться, что `strategy_builder_router` зарегистрирован **до** других роутеров, которые могут перехватывать `/strategies/{id}`.

### Вариант 2: Проверить фильтрацию в роутах

Убедиться, что стратегия действительно имеет `is_builder_strategy == True`:
```python
# В PUT/POST роутах проверить логику фильтрации
db_strategy = (
    db.query(Strategy)
    .filter(
        Strategy.id == strategy_id,
        Strategy.is_builder_strategy == True,  # ← Проверить это условие
        Strategy.is_deleted == False,
    )
    .first()
)
```

### Вариант 3: Добавить диагностику в роуты

Добавить логирование в начало каждого роута для диагностики:
```python
@router.put("/strategies/{strategy_id}")
async def update_strategy(...):
    logger.info(f"PUT /strategies/{strategy_id} called")
    # ...
```

### Вариант 4: Проверить CORS и middleware

Убедиться, что CORS и middleware не блокируют PUT/POST запросы.

## Следующие шаги

1. ✅ Исправлена CSP ошибка (`child-src` добавлен отдельно)
2. 🔄 Проверить Swagger UI на наличие эндпоинтов
3. 🔄 Проверить логи сервера при запросах PUT/POST
4. 🔄 Проверить порядок регистрации роутеров
5. 🔄 Добавить диагностическое логирование в роуты

## Связанные файлы

- `backend/api/routers/strategy_builder.py` - определение роутов
- `backend/api/app.py` - регистрация роутеров
- `frontend/js/pages/strategy_builder.js` - фронтенд запросы

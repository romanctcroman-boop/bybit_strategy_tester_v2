# Список тикеров Bybit в Strategy Builder

> **Дата:** 2026-01-31  
> **Контекст:** Поле Symbol в панели Properties Strategy Builder; загрузка названий тикеров от Bybit (без свечей).

---

## 1. Назначение

В панели **Properties** в блоке «ОСНОВНЫЕ ПАРАМЕТРЫ» поле **Symbol** должно показывать выпадающий список тикеров (названий торговых пар) с биржи Bybit, привязанный к выбранному **Типу рынка** (Futures / SPOT). Пользователь выбирает тикер из списка или вводит текст для поиска по списку. Данные берутся только из **Bybit API** (названия инструментов), **свечи при этом не загружаются**.

---

## 2. Поток данных

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Strategy Builder (Frontend)                                            │
│  Поле Symbol + кнопка «Обновить список»                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
    GET /api/v1/marketdata/symbols-list?category=linear|spot
    POST /api/v1/refresh-tickers
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Backend (tickers_api, app.add_api_route)                                │
│  app.state.symbols_cache['linear'] / ['spot']                            │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    При пустом кэше или по refresh:
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  BybitAdapter.get_symbols_list(category, trading_only=True)             │
│  GET https://api.bybit.com/v5/market/instruments-info                   │
│  Параметры: category, limit=1000, cursor (пагинация)                     │
└─────────────────────────────────────────────────────────────────────────┘
```

- **GET symbols-list** — отдаёт список из `app.state.symbols_cache` по категории; при отсутствии данных запрашивает Bybit и заполняет кэш.
- **POST refresh-tickers** — принудительно запрашивает у Bybit linear и spot, обновляет кэш только при непустом ответе (при сбое одной категории вторая не затирается).

---

## 3. Проблема, с которой столкнулись

### Симптомы

1. **В списке только 3 тикера** (например BTCUSDT, ETHBTCUSDT, PUMPBTCUSDT) вместо сотен.
2. **Список не открывается / не закрывается / не прокручивается** — выпадающий список вёл себя некорректно (всегда открыт, перекрыт соседними элементами, без скролла).
3. **При нажатии «Обновить список»** загружался только один тип рынка или при сетевой ошибке список пропадал (кэш затирался пустым).
4. **404 на symbols-list и refresh-tickers** — маршруты не находились до явной регистрации на уровне приложения.

### Причины

| Причина | Описание |
|--------|----------|
| Два обработчика на один путь | На GET `/api/v1/marketdata/symbols-list` были зарегистрированы и роутер **marketdata** (без полной пагинации Bybit), и **tickers_api**. Срабатывал первый (marketdata), ответ мог быть неполным или из старого кэша. |
| Без пагинации Bybit | Bybit API **instruments-info** отдаёт данные постранично (`limit`, `nextPageCursor`). Запрос без пагинации возвращал только первую страницу (до 500 записей); в ряде сценариев в кэше оказывалось мало записей. |
| Ограничения на фронте | Список обрезался до 100 элементов при отсутствии поиска и до 80 в разметке; выпадающий список открывался при загрузке страницы и имел низкий z-index / перекрывался блоком «Таймфрейм». |
| Затирание кэша при ошибке | В **refresh-tickers** при падении запроса по одной категории (DNS, таймаут) в кэш записывался пустой список и старые данные терялись. |

---

## 4. Внесённые исправления

### Backend

- **Один обработчик symbols-list:** обработчик GET `symbols-list` удалён из роутера marketdata; единственный источник — **tickers_api**, регистрируемый через `app.add_api_route("/api/v1/marketdata/symbols-list", ...)` в `app.py`.
- **Пагинация в BybitAdapter.get_symbols_list():** цикл по страницам с `limit=1000` и `cursor` из `nextPageCursor`; сбор всех страниц (с ограничением max_pages); проверка `retCode` в ответе Bybit; таймаут не менее 30 с; логирование `get_symbols_list category=... count=...`.
- **refresh-tickers:** обновление кэша только при непустом ответе по каждой категории (`if linear: cache["linear"] = linear`; то же для spot); при сбое одной категории вторая не перезаписывается.
- **Маршруты:** GET `symbols-list` и POST `refresh-tickers` гарантированно доступны за счёт регистрации через `add_api_route` в `app.py`.

### Frontend

- **Открытие списка только по focus/click** по полю Symbol; при загрузке страницы список не открывается (только предзагрузка тикеров).
- **Закрытие:** по клику вне поля и списка, через общую функцию `closeSymbolDropdown()` (сброс класса `open` и inline-стилей).
- **Отображение списка:** фиксированное позиционирование, `z-index: 100000`, `max-height: 220px`, `overflow-y: auto` — список поверх остального UI и с прокруткой.
- **Количество пунктов:** без обрезки до 100 при пустом поиске; в выпадающем списке показывается до **500** тикеров (`.slice(0, 500)`).

### Мониторинг и проверка

- Для путей `/api/v1/marketdata/symbols` и `/api/v1/refresh-tickers` в middleware slow_requests заданы **long_running_paths** (порог ERROR ~16 с), чтобы не засорять логи при медленных ответах Bybit.
- **Скрипт проверки:** `scripts/test_bybit_symbols_direct.py` — запрос к Bybit `instruments-info` без нашего API (проверка сети и ответа Bybit). Запуск: `py -3.14 scripts/test_bybit_symbols_direct.py`.

---

## 5. Как проверить

1. **Прямой запрос к Bybit (без нашего API):**
   ```bash
   py -3.14 scripts/test_bybit_symbols_direct.py
   ```
   Ожидается: «OK: получено 500 тикеров (category=linear)» и примеры символов.

2. **Через наш API (при запущенном сервере):**
   - GET: `http://127.0.0.1:8000/api/v1/marketdata/symbols-list?category=linear`
   - POST: `http://127.0.0.1:8000/api/v1/refresh-tickers`
   - Скрипт: `py -3.14 scripts/test_tickers_api.py --base http://127.0.0.1:8000`

3. **В UI Strategy Builder:**
   - Открыть страницу через хост API, например: `http://127.0.0.1:8000/frontend/strategy-builder.html`.
   - Нажать «Обновить список», затем клик по полю Symbol — должен открыться выпадающий список с прокруткой (до 500 тикеров).
   - Для полного списка поле Symbol должно быть **пустым**; при вводе текста список фильтруется по введённой строке.

---

## 6. Связанные файлы

| Компонент | Файл |
|-----------|------|
| API тикеров | `backend/api/routers/tickers_api.py` |
| Регистрация маршрутов | `backend/api/app.py` (add_api_route) |
| Адаптер Bybit, пагинация | `backend/services/adapters/bybit.py` (get_symbols_list) |
| Frontend: список Symbol | `frontend/js/pages/strategy_builder.js` (initSymbolPicker, showSymbolDropdown, fetchBybitSymbols) |
| Стили выпадающего списка | `frontend/css/strategy_builder.css` (.symbol-picker-dropdown) |
| Пороги slow_requests | `backend/api/middleware_setup.py`, `backend/middleware/timing.py` |
| Проверка Bybit напрямую | `scripts/test_bybit_symbols_direct.py` |
| Проверка нашего API | `scripts/test_tickers_api.py` |

---

## 7. Ссылки

- Bybit API v5: [Get Instruments Info](https://bybit-exchange.github.io/docs/v5/market/instrument-info) — пагинация `limit` (max 1000), `cursor` / `nextPageCursor`.
- В проекте: `backend/api/routers/tickers_api.py` (docstring), `AGENTS.MD` / `.cursor/rules/project.mdc` (общие правила).

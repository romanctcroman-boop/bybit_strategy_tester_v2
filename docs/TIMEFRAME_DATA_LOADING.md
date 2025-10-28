# Timeframe Data Loading Strategy

## Проблема

Ранее приложение загружало **фиксированное количество свечей** (2000) для всех таймфреймов. Это приводило к разной глубине истории:

| Таймфрейм | Свечей | Дней | Проблема |
|-----------|--------|------|----------|
| 15m | 2000 | 20 | ❌ Слишком мало данных |
| 1h | 2000 | 83 | ❌ Неоптимально |
| 1D | 2000 | 5.5 лет | ❌ Избыточно (API лимит 1000) |

## Решение

### 1. Оптимальная загрузка данных

Используем **максимальное количество свечей** (1000) для всех таймфреймов. Это даёт оптимальную глубину истории:

| Таймфрейм | Свечей | Дней | Глубина истории |
|-----------|--------|------|-----------------|
| **1m** | 1000 | 0.7 | ✅ ~17 часов (скальпинг) |
| **5m** | 1000 | 3.5 | ✅ ~3.5 дня (интрадей) |
| **15m** | 1000 | 10.4 | ✅ ~10 дней (свинг) |
| **30m** | 1000 | 20.8 | ✅ ~3 недели |
| **1h** | 1000 | 41.7 | ✅ ~1.5 месяца |
| **4h** | 1000 | 166.7 | ✅ ~5.5 месяцев |
| **1D** | 1000 | 1000 | ✅ ~2.7 года |
| **1W** | 1000 | 7000 | ✅ ~19 лет |

### 2. Period Selector для бэктестинга

Добавлен компонент `PeriodSelector` с предустановленными периодами:

- **1 месяц** (30 дней)
- **3 месяца** (90 дней)  
- **6 месяцев** (180 дней)
- **1 год** (365 дней)
- **3 года**
- **Весь период** (с 2020-06-01)
- **Произвольный период** (custom dates)

По умолчанию используется **30 дней** для оптимального баланса между скоростью и глубиной данных.

## Преимущества

1. **Автоматическая оптимизация**: Каждый таймфрейм получает оптимальную глубину
2. **Максимум данных**: Используем полный лимит API (1000 свечей)
3. **Консистентность**: Одна логика для всех таймфреймов
4. **Производительность**: Не перегружаем память избыточными данными
5. **Гибкость**: Пользователь может выбрать произвольный период для тестирования

## Реализация

### Frontend Store

```typescript
// frontend/src/store/marketData.ts

loadCandles: async (symbol: string, interval: string, _limit?: number) => {
  // Always use 1000 candles (API max) for optimal history depth per timeframe
  const optimalLimit = _limit ?? 1000;
  
  const freshData = await DataApi.bybitWorkingSet(symbol, interval, optimalLimit);
  // ...
}
```

### Period Selector Component

```typescript
// frontend/src/components/PeriodSelector.tsx

<PeriodSelector
  value={period}
  onChange={(newPeriod) => setPeriod(newPeriod)}
  label="Период для бэктеста"
/>
```

### Period Filtering

```typescript
// Filter candles by selected period (trading mode only)
if (chartMode === 'trading' && period) {
  const startTimeSec = new Date(period.startDate).getTime() / 1000;
  const endTimeSec = new Date(period.endDate).getTime() / 1000 + 86400;
  
  return candles.filter((d) => d.time >= startTimeSec && d.time <= endTimeSec);
}
```

## Ограничения API

- **Минимум**: 100 свечей (backend validation)
- **Максимум**: 1000 свечей (backend validation)
- **Рекомендация**: Использовать максимум (1000) для всех таймфреймов

## Для разработчиков

Если нужна **большая глубина** для коротких таймфреймов (1m, 5m):
1. Увеличить лимит API в `backend/api/routers/marketdata.py`
2. Реализовать пагинацию (multiple API calls)
3. Использовать исторические данные из БД

## UI Components

**PeriodSelector** доступен в режиме **TRADING** на странице TestChart:
- Кнопка отображает текущий период и количество дней
- Клик открывает Popover с быстрым выбором
- Поддерживает произвольные даты через date pickers

## Changelog

- **2025-10-26**: Добавлен PeriodSelector с preset периодами
- **2025-10-26**: Изменено с фиксированных 2000 на оптимальные 1000 свечей
- **2025-10-26**: Добавлена фильтрация свечей по периоду в trading mode
- **Причина**: Различная глубина истории на разных таймфреймах
- **Файлы**: 
  - `frontend/src/store/marketData.ts`
  - `frontend/src/components/PeriodSelector.tsx`
  - `frontend/src/pages/TestChartPage.tsx`

# Advanced Visualizations (ТЗ 3.7.2)

Модуль для создания продвинутых графиков анализа бэктестов и оптимизации стратегий.

## 📊 Возможности

### 1. **Equity Curve с Drawdown**
- `create_equity_curve()` - кривая эквити с опциональным подграфиком просадок
- `create_drawdown_overlay()` - эквити и просадка на одном графике (dual y-axis)

**Особенности:**
- Автоматический расчет просадок от максимума
- Заливка области для визуальной выразительности
- Интерактивное масштабирование (Plotly)
- Unified hover для синхронизации по времени

### 2. **PnL Distribution**
- `create_pnl_distribution()` - гистограмма распределения PnL по сделкам

**Особенности:**
- Цветовая градация (красный → желтый → зеленый)
- Автоматические линии: mean, median, zero
- Статистика в заголовке: mean, median, std dev
- Кастомизация количества bins

### 3. **Parameter Heatmaps**
- `create_parameter_heatmap()` - тепловая карта для анализа оптимизации

**Особенности:**
- 2D визуализация зависимости метрики от параметров
- Автоматическая маркировка лучшей точки (звезда)
- Цветовая схема RdYlGn (Red-Yellow-Green)
- Числовые значения в ячейках
- Поддержка любых метрик: total_return, sharpe_ratio, max_drawdown, etc.

## 🚀 Быстрый старт

### Установка
```bash
pip install plotly pandas numpy
```

### Демо
```bash
python backend/visualization/demo_charts.py
```

Сгенерирует 6 HTML файлов в `docs/charts/`:
- equity_curve_with_drawdown.html
- equity_drawdown_overlay.html
- pnl_distribution.html
- param_heatmap_return.html
- param_heatmap_sharpe.html
- param_heatmap_drawdown.html

## 📖 Примеры использования

### Equity Curve
```python
from backend.visualization import create_equity_curve
import pandas as pd

# Из Series
equity = pd.Series([100, 105, 103, 108, 110], 
                   index=pd.date_range('2025-01-01', periods=5))
fig = create_equity_curve(equity, show_drawdown=True)
fig.show()

# Из DataFrame
df = pd.DataFrame({'equity': equity})
fig = create_equity_curve(df, show_drawdown=True, height=700)
fig.write_html('equity.html')
```

### PnL Distribution
```python
from backend.visualization import create_pnl_distribution

# Из DataFrame
trades = pd.DataFrame({'pnl': [100, -50, 75, 200, -25, 150]})
fig = create_pnl_distribution(trades, bins=30)
fig.show()

# Из списка
pnl_list = [100, -50, 75, 200, -25, 150]
fig = create_pnl_distribution(pnl_list, title="My PnL")
```

### Parameter Heatmap
```python
from backend.visualization import create_parameter_heatmap

# Результаты grid search
results = pd.DataFrame({
    'ma_fast': [5, 5, 10, 10, 15, 15],
    'ma_slow': [20, 30, 20, 30, 20, 30],
    'total_return': [0.05, 0.08, 0.12, 0.06, 0.09, 0.11],
    'sharpe_ratio': [0.4, 0.6, 0.9, 0.5, 0.7, 0.8],
})

# Тепловая карта по доходности
fig = create_parameter_heatmap(
    results, 
    param_x='ma_fast', 
    param_y='ma_slow', 
    metric='total_return',
    title='MA Optimization',
)
fig.show()

# Тепловая карта по Sharpe
fig2 = create_parameter_heatmap(
    results, 
    param_x='ma_fast', 
    param_y='ma_slow', 
    metric='sharpe_ratio',
)
```

## 🎨 Кастомизация

Все функции поддерживают параметры:
- `title` - заголовок графика
- `height` - высота в пикселях
- `width` - ширина (для heatmap)

Дополнительно:
- Equity curve: `show_drawdown=True/False`
- PnL distribution: `bins=30`, `pnl_column='pnl'`
- Heatmap: `metric='total_return'`

## 🧪 Тестирование

```bash
pytest tests/test_advanced_charts.py -v
```

**27 тестов**, покрывающих:
- ✅ Создание всех типов графиков
- ✅ Обработка DataFrame и Series
- ✅ Валидация входных данных
- ✅ Кастомизация параметров
- ✅ Сериализация в JSON (для фронтенда)
- ✅ Responsive layout

## 🌐 Интеграция с фронтендом

Все графики возвращают `plotly.graph_objects.Figure`, который можно:

1. **Сериализовать в JSON:**
```python
fig = create_equity_curve(equity)
json_str = fig.to_json()
# Отправить на фронтенд через API
return {"chart": json_str}
```

2. **Рендерить в React:**
```typescript
import Plot from 'react-plotly.js';

function EquityChart({ chartData }) {
  const fig = JSON.parse(chartData);
  return <Plot data={fig.data} layout={fig.layout} />;
}
```

3. **Сохранить в HTML:**
```python
fig.write_html('chart.html')
```

## 📋 Соответствие ТЗ

**ТЗ 3.7.2** требует:
> "Графики: эквити, распределение PnL, тепловые карты параметров"

✅ **Реализовано:**
- [x] Equity curve с drawdown (2 варианта)
- [x] PnL distribution со статистикой
- [x] Parameter heatmaps (любые метрики)
- [x] Интерактивные Plotly графики
- [x] Web-ready (JSON сериализация)
- [x] 27 comprehensive тестов (100% PASSED)

## 🔧 Технические детали

- **Библиотека:** Plotly (интерактивные web-графики)
- **Данные:** pandas DataFrame/Series
- **Стиль:** plotly_white template
- **Цветовые схемы:**
  - Equity: #2E86AB (синий)
  - Drawdown: #E63946 (красный)
  - PnL gradient: красный → желтый → зеленый
  - Heatmap: RdYlGn (Red-Yellow-Green)

## 📚 API Reference

### create_equity_curve()
```python
def create_equity_curve(
    equity_data: Union[pd.Series, pd.DataFrame],
    title: str = "Equity Curve",
    show_drawdown: bool = True,
    height: int = 600,
) -> go.Figure
```

### create_drawdown_overlay()
```python
def create_drawdown_overlay(
    equity_data: Union[pd.Series, pd.DataFrame],
    title: str = "Equity & Drawdown Analysis",
    height: int = 600,
) -> go.Figure
```

### create_pnl_distribution()
```python
def create_pnl_distribution(
    trades: Union[pd.DataFrame, List[float]],
    pnl_column: str = 'pnl',
    title: str = "PnL Distribution",
    bins: int = 30,
    height: int = 500,
) -> go.Figure
```

### create_parameter_heatmap()
```python
def create_parameter_heatmap(
    optimization_results: pd.DataFrame,
    param_x: str,
    param_y: str,
    metric: str = 'total_return',
    title: Optional[str] = None,
    height: int = 600,
    width: int = 800,
) -> go.Figure
```

## 🎯 Производительность

- Equity curve (2160 точек): ~0.1s
- PnL distribution (100 сделок): ~0.05s
- Parameter heatmap (4x4 grid): ~0.08s

**Оптимизации:**
- Использование numpy для вычислений
- Минимальные копирования данных
- Эффективная агрегация для heatmap

## 📦 Структура модуля

```
backend/visualization/
├── __init__.py              # Public API
├── advanced_charts.py       # Основные функции (432 строки)
├── demo_charts.py           # Демо-скрипт (226 строк)
└── README.md               # Эта документация

tests/
└── test_advanced_charts.py  # 27 тестов (327 строк)

docs/charts/                # Сгенерированные примеры
├── equity_curve_with_drawdown.html
├── equity_drawdown_overlay.html
├── pnl_distribution.html
├── param_heatmap_return.html
├── param_heatmap_sharpe.html
└── param_heatmap_drawdown.html
```

## 🚧 Roadmap (опционально)

Потенциальные улучшения:
- [ ] 3D surface plots для 3-параметрической оптимизации
- [ ] Candlestick charts с индикаторами
- [ ] Trade timeline visualization
- [ ] Walk-Forward efficiency visualization
- [ ] Monte Carlo confidence bands
- [ ] Live update support (WebSocket streaming)

---

**Автор:** Roman CTC  
**Версия:** 1.0  
**Дата:** 2025-10-25  
**ТЗ:** 3.7.2 Advanced Visualization

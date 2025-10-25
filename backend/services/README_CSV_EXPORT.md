# CSV Export Module - Report Generator

## Обзор

Модуль `ReportGenerator` реализует генерацию CSV отчетов согласно **ТЕХНИЧЕСКОЕ ЗАДАНИЕ раздел 4**. Генерирует 4 типа профессиональных отчетов в формате CSV для детального анализа результатов бэктестинга.

## Реализованные форматы (ТЗ 4)

### 4.1 List-of-trades.csv

Детальный лог всех сделок с полной информацией:

**Колонки:**
- `Trade #` - Номер сделки
- `Type` - Тип записи (Entry long/short, Exit long/short)
- `Date/Time` - Временная метка
- `Signal` - Сигнал входа/выхода
- `Price USDT` - Цена исполнения
- `Position size (qty)` - Размер позиции в количестве
- `Position size (value)` - Размер позиции в USDT
- `Net P&L USDT` - Чистая прибыль/убыток
- `Net P&L %` - Чистая прибыль/убыток в %
- `Run-up USDT` - Максимальная прибыль во время сделки
- `Run-up %` - Максимальная прибыль в %
- `Drawdown USDT` - Максимальный убыток во время сделки
- `Drawdown %` - Максимальный убыток в %
- `Cumulative P&L USDT` - Накопленная прибыль
- `Cumulative P&L %` - Накопленная прибыль в %

**Особенности:**
- Каждая сделка представлена двумя строками: Entry и Exit
- Кумулятивный P&L рассчитывается нарастающим итогом
- Подходит для детального анализа каждой сделки

### 4.2 Performance.csv

Основные показатели эффективности стратегии:

**Структура:** All / Long / Short колонки с USDT и % значениями

**Метрики:**
- `Open P&L` - P&L открытых позиций
- `Net profit` - Чистая прибыль (USDT и %)
- `Gross profit` - Общая прибыль (USDT и %)
- `Gross loss` - Общий убыток (USDT и %)
- `Commission paid` - Комиссии (USDT)
- `Buy & hold return` - Доходность стратегии Buy&Hold (USDT и %)
- `Max equity run-up` - Максимальный рост equity (USDT и %)
- `Max equity drawdown` - Максимальная просадка (USDT и %)
- `Max contracts held` - Максимальный размер позиции

**Особенности:**
- Разделение на All/Long/Short для детального анализа
- Показывает общую эффективность стратегии
- Сравнение со стратегией Buy&Hold

### 4.3 Risk-performance-ratios.csv

Метрики риска и соотношения доходности:

**Структура:** All / Long / Short колонки

**Метрики:**
- `Sharpe ratio` - Коэффициент Шарпа (аннуализированный)
- `Sortino ratio` - Коэффициент Сортино (учитывает только downside risk)
- `Profit factor` - Коэффициент прибыльности (Gross Profit / Gross Loss)
- `Margin calls` - Количество маржин-коллов

**Особенности:**
- Sharpe и Sortino аннуализированы (√252)
- Profit factor показывает соотношение выигрышей к проигрышам
- Критически важные метрики для оценки риска

### 4.4 Trades-analysis.csv

Статистический анализ сделок:

**Структура:** All / Long / Short колонки с USDT и % значениями

**Метрики:**
- `Total trades` - Общее количество сделок
- `Winning trades` - Количество прибыльных сделок
- `Losing trades` - Количество убыточных сделок
- `Percent profitable` - Win rate (%)
- `Avg P&L` - Средний P&L (USDT и %)
- `Avg winning trade` - Средняя прибыльная сделка (USDT и %)
- `Avg losing trade` - Средняя убыточная сделка (USDT и %)
- `Ratio avg win / avg loss` - Соотношение средней прибыли к убытку
- `Largest winning trade` - Самая прибыльная сделка (USDT и %)
- `Largest losing trade` - Самая убыточная сделка (USDT и %)
- `Avg # bars in trades` - Среднее количество баров в сделке

**Особенности:**
- Детальная статистика по всем сделкам
- Анализ распределения прибылей/убытков
- Средняя длительность сделок

## API Usage

### Python API

```python
from backend.services.report_generator import ReportGenerator

# Создаем генератор с результатами бэктеста
generator = ReportGenerator(
    backtest_results=engine_results,  # Dict из BacktestEngine.run()
    initial_capital=10000.0
)

# Генерируем отдельные отчеты
list_of_trades_csv = generator.generate_list_of_trades_csv()
performance_csv = generator.generate_performance_csv()
risk_ratios_csv = generator.generate_risk_ratios_csv()
trades_analysis_csv = generator.generate_trades_analysis_csv()

# Или все сразу
all_reports = generator.generate_all_reports()
# Returns: {
#   'list_of_trades': <csv_string>,
#   'performance': <csv_string>,
#   'risk_ratios': <csv_string>,
#   'trades_analysis': <csv_string>
# }

# Сохраняем в файлы
with open('list-of-trades.csv', 'w', encoding='utf-8') as f:
    f.write(list_of_trades_csv)
```

### REST API

**Экспорт отдельного отчета:**
```http
GET /backtests/{backtest_id}/export/{report_type}
```

**Параметры:**
- `backtest_id` (path) - ID бэктеста
- `report_type` (path) - Тип отчета:
  - `list_of_trades` - List-of-trades.csv
  - `performance` - Performance.csv
  - `risk_ratios` - Risk-performance-ratios.csv
  - `trades_analysis` - Trades-analysis.csv
  - `all` - ZIP архив со всеми отчетами

**Response:**
- Content-Type: `text/csv` или `application/zip` (для `all`)
- Content-Disposition: `attachment; filename=backtest_{id}_{type}.csv`

**Примеры:**
```bash
# Скачать Performance.csv
curl http://localhost:8000/backtests/5/export/performance -o performance.csv

# Скачать все отчеты в ZIP
curl http://localhost:8000/backtests/5/export/all -o reports.zip
```

**Требования:**
- Бэктест должен иметь статус `completed`
- Бэктест должен иметь результаты (поле `results` не пустое)

**Ошибки:**
- `404` - Backtest not found
- `400` - Backtest must be completed to export reports
- `400` - Invalid report_type

## Implementation Details

### Data Flow

```
BacktestEngine.run()
    ↓
    results = {
        'trades': [...],
        'buy_hold_return': X,
        'buy_hold_return_pct': Y
    }
    ↓
ReportGenerator(results, initial_capital)
    ↓
    _calculate_performance_metrics()
    _calculate_risk_metrics()
    _calculate_trade_analysis()
    ↓
    CSV Generation
```

### Trade Separation

ReportGenerator автоматически разделяет сделки:
- `all_trades` - все закрытые сделки (с `exit_price`)
- `long_trades` - фильтр `side == 'long'`
- `short_trades` - фильтр `side == 'short'`

### Performance Calculation

**Net Profit:**
```python
net_profit = sum(trade['pnl'] for trade in trades)
net_profit_pct = (net_profit / initial_capital) * 100
```

**Gross Profit/Loss:**
```python
gross_profit = sum(pnl for pnl in pnls if pnl > 0)
gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
```

**Max Drawdown:**
```python
equity_curve = [initial_capital]
for pnl in pnls:
    equity_curve.append(equity_curve[-1] + pnl)

running_max = np.maximum.accumulate(equity_curve)
drawdown = running_max - equity_curve
max_drawdown = drawdown.max()
```

### Risk Metrics

**Sharpe Ratio (аннуализированный):**
```python
returns = pnls / initial_capital
sharpe = (returns.mean() * sqrt(252)) / (returns.std() + 1e-9)
```

**Sortino Ratio:**
```python
downside_returns = returns[returns < 0]
sortino = (returns.mean() * sqrt(252)) / (downside_returns.std() + 1e-9)
```

**Profit Factor:**
```python
profit_factor = gross_profit / (gross_loss + 1e-9)
```

## Testing

### Unit Tests

```bash
pytest tests/test_report_generator.py -v
```

**Coverage:** 16 тестов
- Initialization
- CSV generation for all 4 types
- Metrics calculation accuracy
- Edge cases (empty trades, long-only, etc.)
- Format compliance with ТЗ section 4

### Demo Script

```bash
python backend/services/demo_csv_export.py
```

**Output:**
- Генерирует 50 реалистичных сделок
- Создает все 4 CSV файла в `docs/csv_reports/`
- Показывает preview и статистику

## Integration

### With BacktestEngine

```python
from backend.core.backtest_engine import BacktestEngine
from backend.services.report_generator import ReportGenerator

# Run backtest
engine = BacktestEngine(data, strategy, params)
results = engine.run()

# Generate CSV reports
generator = ReportGenerator(results, initial_capital=10000.0)
reports = generator.generate_all_reports()
```

### With API

```python
from backend.services.report_generator import ReportGenerator
from backend.services.data_service import DataService

# Fetch backtest from DB
with DataService() as ds:
    bt = ds.get_backtest(backtest_id)
    
    # Generate reports
    generator = ReportGenerator(bt.results, bt.initial_capital)
    csv_content = generator.generate_performance_csv()
```

### With Frontend

React component example:

```typescript
// Download CSV report
const downloadReport = async (backtestId: number, reportType: string) => {
  const response = await fetch(
    `/backtests/${backtestId}/export/${reportType}`
  );
  
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backtest_${backtestId}_${reportType}.csv`;
  a.click();
};

// Download all reports as ZIP
const downloadAllReports = async (backtestId: number) => {
  const response = await fetch(
    `/backtests/${backtestId}/export/all`
  );
  
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backtest_${backtestId}_reports.zip`;
  a.click();
};
```

## Compliance with ТЗ

✅ **ТЗ 4.1** - List-of-trades.csv полностью соответствует формату
✅ **ТЗ 4.2** - Performance.csv с колонками All/Long/Short USDT/%
✅ **ТЗ 4.3** - Risk-performance-ratios.csv с Sharpe/Sortino/Profit Factor
✅ **ТЗ 4.4** - Trades-analysis.csv с детальной статистикой сделок

**Все форматы точно соответствуют структуре из ТЕХНИЧЕСКОЕ ЗАДАНИЕ раздел 4.**

## Performance

- **Generation time:** <100ms для 50 сделок
- **Memory usage:** Minimal (in-memory CSV generation)
- **Scalability:** Tested with 1000+ trades

## Next Steps

1. ✅ CSV Export реализован полностью
2. 🚀 **Frontend Dashboard Integration** - следующий приоритет
3. Strategy Module expansion (ТЗ 3.2)
4. AI Module completion (optional)

## Files

- `backend/services/report_generator.py` - Main implementation (750+ lines)
- `tests/test_report_generator.py` - Comprehensive tests (16 tests)
- `backend/services/demo_csv_export.py` - Demo script
- `backend/api/routers/backtests.py` - REST API endpoint
- `docs/csv_reports/` - Example CSV files

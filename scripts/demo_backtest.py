"""Демо-скрипт для тестирования BacktestEngine с реальными данными Bybit.

Использование:
    python scripts/demo_backtest.py BTCUSDT --interval 15 --days 30
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.adapters.bybit import BybitAdapter
from backend.core.backtest_engine import BacktestEngine


def fetch_bybit_data(symbol: str, interval: str = '15', days: int = 30, limit: int = 1000) -> pd.DataFrame:
    """Загрузка данных с Bybit."""
    print(f"📥 Загрузка данных {symbol} ({interval}m) за последние {days} дней...")
    
    adapter = BybitAdapter()
    
    try:
        # Fetch data
        raw_data = adapter.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        if not raw_data:
            print(f"❌ Нет данных для {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(raw_data)
        
        # Ensure required columns
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        # Rename columns if needed
        column_mapping = {
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close',
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        # Select relevant columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"✅ Загружено {len(df)} свечей")
        print(f"   Период: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        print(f"   Цена: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return pd.DataFrame()


def run_ema_crossover_backtest(
    data: pd.DataFrame,
    initial_capital: float = 10_000.0,
    fast_ema: int = 50,
    slow_ema: int = 200,
    tp_pct: float = 5.0,
    sl_pct: float = 2.0,
    risk_pct: float = 2.0
):
    """Запуск EMA Crossover бэктеста."""
    print(f"\n🚀 Запуск бэктеста EMA Crossover ({fast_ema}/{slow_ema})")
    print(f"   Капитал: ${initial_capital:,.0f}")
    print(f"   TP: {tp_pct}%, SL: {sl_pct}%, Risk: {risk_pct}%")
    print(f"   {'='*60}")
    
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=0.055 / 100,  # Bybit taker fee 0.055%
        slippage_pct=0.05
    )
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': fast_ema,
        'slow_ema': slow_ema,
        'take_profit_pct': tp_pct,
        'stop_loss_pct': sl_pct,
        'trailing_stop_pct': 0,  # Disable for now
        'risk_per_trade_pct': risk_pct,
        'signal_exit': False,
        'max_positions': 1,
    }
    
    results = engine.run(data, strategy_config)
    
    # Print results
    print(f"\n📊 РЕЗУЛЬТАТЫ БЭКТЕСТА")
    print(f"   {'='*60}")
    print(f"   💰 Финальный капитал: ${results['final_capital']:,.2f}")
    print(f"   📈 Доходность: {results['total_return']*100:.2f}%")
    print(f"   📉 Max Drawdown: {results['max_drawdown']*100:.2f}%")
    print(f"   {'─'*60}")
    print(f"   📊 Всего сделок: {results['total_trades']}")
    print(f"   ✅ Прибыльных: {results['winning_trades']} ({results['win_rate']*100:.1f}%)")
    print(f"   ❌ Убыточных: {results['losing_trades']}")
    print(f"   {'─'*60}")
    print(f"   🎯 Profit Factor: {results['profit_factor']:.2f}")
    print(f"   📊 Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"   📊 Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"   {'='*60}")
    
    metrics = results.get('metrics', {})
    if metrics:
        print(f"\n💵 ДЕТАЛЬНАЯ СТАТИСТИКА")
        print(f"   Чистая прибыль: ${metrics.get('net_profit', 0):.2f}")
        print(f"   Gross Profit: ${metrics.get('gross_profit', 0):.2f}")
        print(f"   Gross Loss: ${metrics.get('gross_loss', 0):.2f}")
        print(f"   Комиссии: ${metrics.get('total_commission', 0):.2f}")
        print(f"   {'─'*60}")
        print(f"   Средний PnL: ${metrics.get('avg_pnl', 0):.2f}")
        print(f"   Средняя победа: ${metrics.get('avg_win', 0):.2f}")
        print(f"   Средний убыток: ${metrics.get('avg_loss', 0):.2f}")
        print(f"   {'─'*60}")
        print(f"   Макс. победа: ${metrics.get('max_win', 0):.2f}")
        print(f"   Макс. убыток: ${metrics.get('max_loss', 0):.2f}")
        print(f"   {'─'*60}")
        print(f"   Среднее баров в сделке: {metrics.get('avg_bars', 0):.1f}")
        print(f"   Buy & Hold доходность: {metrics.get('buy_hold_return', 0):.2f}%")
    
    # Print trades if any
    if results['total_trades'] > 0 and results['total_trades'] <= 10:
        print(f"\n📋 СПИСОК СДЕЛОК")
        print(f"   {'='*80}")
        for i, trade in enumerate(results['trades'], 1):
            pnl_sign = "✅" if trade['pnl'] > 0 else "❌"
            print(f"   {pnl_sign} Сделка #{i}")
            print(f"      Вход:  {trade['entry_time'][:19]} @ ${trade['entry_price']:.2f}")
            print(f"      Выход: {trade['exit_time'][:19]} @ ${trade['exit_price']:.2f}")
            print(f"      PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
            print(f"      Причина: {trade['exit_reason']}")
            print(f"      {'─'*76}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Демо BacktestEngine с Bybit данными')
    parser.add_argument('symbol', type=str, default='BTCUSDT', nargs='?', help='Символ (по умолчанию BTCUSDT)')
    parser.add_argument('--interval', type=str, default='15', help='Интервал в минутах (по умолчанию 15)')
    parser.add_argument('--days', type=int, default=30, help='Количество дней истории (по умолчанию 30)')
    parser.add_argument('--limit', type=int, default=1000, help='Лимит свечей (по умолчанию 1000)')
    parser.add_argument('--capital', type=float, default=10000.0, help='Начальный капитал (по умолчанию 10000)')
    parser.add_argument('--fast-ema', type=int, default=50, help='Период быстрой EMA (по умолчанию 50)')
    parser.add_argument('--slow-ema', type=int, default=200, help='Период медленной EMA (по умолчанию 200)')
    parser.add_argument('--tp', type=float, default=5.0, help='Take Profit % (по умолчанию 5.0)')
    parser.add_argument('--sl', type=float, default=2.0, help='Stop Loss % (по умолчанию 2.0)')
    parser.add_argument('--risk', type=float, default=2.0, help='Риск на сделку % (по умолчанию 2.0)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"  🎯 BACKTEST ENGINE DEMO - EMA CROSSOVER STRATEGY")
    print(f"{'='*80}\n")
    
    # Fetch data
    data = fetch_bybit_data(
        symbol=args.symbol,
        interval=args.interval,
        days=args.days,
        limit=args.limit
    )
    
    if data.empty:
        print("❌ Не удалось загрузить данные")
        return 1
    
    # Run backtest
    results = run_ema_crossover_backtest(
        data=data,
        initial_capital=args.capital,
        fast_ema=args.fast_ema,
        slow_ema=args.slow_ema,
        tp_pct=args.tp,
        sl_pct=args.sl,
        risk_pct=args.risk
    )
    
    print(f"\n{'='*80}")
    print(f"  ✅ Бэктест завершён успешно!")
    print(f"{'='*80}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

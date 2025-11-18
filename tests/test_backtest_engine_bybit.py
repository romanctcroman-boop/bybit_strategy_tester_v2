"""Тесты BacktestEngine с реальными данными Bybit из базы данных."""
import os
import sys
import pandas as pd
import pytest
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.core.backtest_engine import BacktestEngine
from backend.services.adapters.bybit import BybitAdapter


def fetch_bybit_klines_from_db(symbol: str = 'BTCUSDT', limit: int = 500) -> pd.DataFrame:
    """Загрузка данных из bybit_kline_audit таблицы или через API."""
    try:
        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit
        from sqlalchemy import desc
        
        db = SessionLocal()
        
        # Try to fetch from DB first
        klines = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == symbol
        ).order_by(desc(BybitKlineAudit.open_time)).limit(limit).all()
        
        db.close()
        
        if klines:
            # Convert to DataFrame
            data = []
            for k in reversed(klines):  # Reverse to ascending order
                data.append({
                    'timestamp': k.open_time_dt or datetime.fromtimestamp(k.open_time / 1000),
                    'open': float(k.open_price or 0),
                    'high': float(k.high_price or 0),
                    'low': float(k.low_price or 0),
                    'close': float(k.close_price or 0),
                    'volume': float(k.volume or 0),
                })
            
            df = pd.DataFrame(data)
            print(f"✅ Loaded {len(df)} klines from database")
            return df
            
    except Exception as e:
        print(f"⚠️  DB fetch failed ({e}), falling back to API...")
    
    # Fallback: fetch via API
    adapter = BybitAdapter()
    raw_data = adapter.get_klines(symbol=symbol, interval='15', limit=limit)
    
    if not raw_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data)
    df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
    
    # Rename columns
    column_mapping = {
        'open_price': 'open',
        'high_price': 'high',
        'low_price': 'low',
        'close_price': 'close',
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df[old_col] = df[old_col].astype(float)
            df.rename(columns={old_col: new_col}, inplace=True)
    
    # Select relevant columns
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"✅ Loaded {len(df)} klines from Bybit API")
    return df


@pytest.mark.skipif(os.getenv('SKIP_BYBIT_TESTS') == '1', reason='Skipping Bybit API tests')
def test_real_bybit_data_long():
    """Тест с реальными данными Bybit - Long стратегия."""
    print("\n" + "="*80)
    print("🔥 REAL BYBIT DATA TEST - LONG STRATEGY")
    print("="*80)
    
    # Fetch real data
    data = fetch_bybit_klines_from_db(symbol='BTCUSDT', limit=500)
    
    if data.empty:
        pytest.skip("No Bybit data available")
    
    print(f"\n📊 Data Info:")
    print(f"   Symbol: BTCUSDT")
    print(f"   Bars: {len(data)}")
    print(f"   Period: {data['timestamp'].iloc[0]} → {data['timestamp'].iloc[-1]}")
    print(f"   Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
    
    # Backtest configuration (as per requirements)
    engine = BacktestEngine(
        initial_capital=10_000.0,  # 10000 USDT
        commission=0.055 / 100,     # Bybit taker 0.055%
        slippage_pct=0.05,
        leverage=5,                 # x5 leverage
        order_size_usd=100.0        # 100 USDT per order
    )
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'long',
        'signal_exit': False,
    }
    
    print(f"\n⚙️  Strategy Config:")
    print(f"   Type: EMA Crossover (20/50)")
    print(f"   Direction: LONG only")
    print(f"   TP: 5%, SL: 2%")
    print(f"   Leverage: 5x")
    print(f"   Order size: $100")
    
    # Run backtest
    results = engine.run(data, strategy_config)
    
    # Print results
    print(f"\n{'='*80}")
    print(f"📊 BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"💰 Initial Capital: ${10_000:.2f}")
    print(f"💰 Final Capital: ${results['final_capital']:,.2f}")
    print(f"📈 Total Return: {results['total_return']*100:.2f}%")
    print(f"📉 Max Drawdown: {results['max_drawdown']*100:.2f}%")
    print(f"{'─'*80}")
    print(f"📊 Total Trades: {results['total_trades']}")
    print(f"✅ Wins: {results['winning_trades']} ({results['win_rate']*100:.1f}%)")
    print(f"❌ Losses: {results['losing_trades']}")
    print(f"{'─'*80}")
    print(f"🎯 Profit Factor: {results['profit_factor']:.2f}")
    print(f"📊 Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"📊 Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"{'='*80}")
    
    # Print trades summary
    if results['total_trades'] > 0:
        metrics = results.get('metrics', {})
        print(f"\n💵 DETAILED STATS:")
        print(f"   Net Profit: ${metrics.get('net_profit', 0):.2f}")
        print(f"   Gross Profit: ${metrics.get('gross_profit', 0):.2f}")
        print(f"   Gross Loss: ${metrics.get('gross_loss', 0):.2f}")
        print(f"   Commissions: ${metrics.get('total_commission', 0):.2f}")
        print(f"   Avg PnL: ${metrics.get('avg_pnl', 0):.2f}")
        print(f"   Max Win: ${metrics.get('max_win', 0):.2f}")
        print(f"   Max Loss: ${metrics.get('max_loss', 0):.2f}")
        print(f"   Avg Bars: {metrics.get('avg_bars', 0):.1f}")
        
        # Print last 5 trades
        if len(results['trades']) <= 5:
            print(f"\n📋 TRADES:")
            for i, trade in enumerate(results['trades'], 1):
                pnl_sign = "✅" if trade['pnl'] > 0 else "❌"
                print(f"   {pnl_sign} #{i} {trade['side'].upper()}: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%) - {trade['exit_reason']}")
    
    # Assertions
    assert results is not None
    assert results['final_capital'] > 0
    assert results['total_trades'] >= 0
    
    print(f"\n{'='*80}\n")


@pytest.mark.skipif(os.getenv('SKIP_BYBIT_TESTS') == '1', reason='Skipping Bybit API tests')
def test_real_bybit_data_short():
    """Тест с реальными данными Bybit - Short стратегия."""
    print("\n" + "="*80)
    print("🔥 REAL BYBIT DATA TEST - SHORT STRATEGY")
    print("="*80)
    
    data = fetch_bybit_klines_from_db(symbol='BTCUSDT', limit=500)
    
    if data.empty:
        pytest.skip("No Bybit data available")
    
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=0.055 / 100,
        slippage_pct=0.05,
        leverage=5,
        order_size_usd=100.0
    )
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'short',  # SHORT only
        'signal_exit': False,
    }
    
    print(f"\n⚙️  Strategy: EMA Crossover (20/50) - SHORT only")
    
    results = engine.run(data, strategy_config)
    
    print(f"\n📊 SHORT Results:")
    print(f"   Return: {results['total_return']*100:.2f}%")
    print(f"   Trades: {results['total_trades']}")
    print(f"   Win Rate: {results['win_rate']*100:.1f}%")
    
    assert results is not None
    
    # Check that all trades are short
    if results['total_trades'] > 0:
        assert all(t['side'] == 'short' for t in results['trades'])
        print(f"   ✅ All {results['total_trades']} trades are SHORT")
    
    print(f"\n{'='*80}\n")


@pytest.mark.skipif(os.getenv('SKIP_BYBIT_TESTS') == '1', reason='Skipping Bybit API tests')
def test_real_bybit_data_both():
    """Тест с реальными данными Bybit - Both directions."""
    print("\n" + "="*80)
    print("🔥 REAL BYBIT DATA TEST - BOTH DIRECTIONS")
    print("="*80)
    
    data = fetch_bybit_klines_from_db(symbol='BTCUSDT', limit=500)
    
    if data.empty:
        pytest.skip("No Bybit data available")
    
    engine = BacktestEngine(
        initial_capital=10_000.0,
        commission=0.055 / 100,
        slippage_pct=0.05,
        leverage=5,
        order_size_usd=100.0
    )
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'both',  # Both long and short
        'signal_exit': True,  # Exit on opposite signal
    }
    
    print(f"\n⚙️  Strategy: EMA Crossover (20/50) - BOTH directions with signal exit")
    
    results = engine.run(data, strategy_config)
    
    print(f"\n📊 BOTH Directions Results:")
    print(f"   Return: {results['total_return']*100:.2f}%")
    print(f"   Trades: {results['total_trades']}")
    print(f"   Win Rate: {results['win_rate']*100:.1f}%")
    
    if results['total_trades'] > 0:
        long_trades = [t for t in results['trades'] if t['side'] == 'long']
        short_trades = [t for t in results['trades'] if t['side'] == 'short']
        
        print(f"   Long: {len(long_trades)} trades")
        print(f"   Short: {len(short_trades)} trades")
    
    assert results is not None
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

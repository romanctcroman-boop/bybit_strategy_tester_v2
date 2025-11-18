"""
QUICK E2E TEST: ML-оптимизация с simple EMA crossover strategy
Для быстрой проверки workflow: данные → оптимизация → результаты
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sqlalchemy import select

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def simple_ema_backtest(data: pd.DataFrame, fast: int = 10, slow: int = 30, take_profit: float = 0.02, stop_loss: float = 0.01):
    """Simple EMA crossover strategy"""
    try:
        df = data.copy()
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['ema_fast'] > df['ema_slow'], 'signal'] = 1  # Long
        df.loc[df['ema_fast'] < df['ema_slow'], 'signal'] = -1  # Short (skip for simplicity)
        
        # Detect crossovers
        df['position'] = df['signal'].diff()
        
        # Simulate trades
        trades = []
        position = None
        entry_price = 0
        
        for idx, row in df.iterrows():
            if row['position'] == 1 and position is None:  # Buy signal
                position = 'long'
                entry_price = row['close']
                
            elif position == 'long':
                # Check exit conditions
                pnl_pct = (row['close'] - entry_price) / entry_price
                
                if pnl_pct >= take_profit or pnl_pct <= -stop_loss or row['position'] == -1:
                    trades.append({
                        'entry': entry_price,
                        'exit': row['close'],
                        'pnl_pct': pnl_pct,
                        'win': pnl_pct > 0
                    })
                    position = None
        
        if len(trades) == 0:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'total_trades': 0
            }
        
        # Calculate metrics
        pnls = [t['pnl_pct'] for t in trades]
        wins = [t for t in trades if t['win']]
        
        total_return = sum(pnls)
        sharpe = np.mean(pnls) / (np.std(pnls) + 1e-9) * np.sqrt(252)
        win_rate = len(wins) / len(trades) if trades else 0
        
        # Max drawdown
        cumulative = np.cumsum([1 + pnl for pnl in pnls])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(min(drawdown)) if len(drawdown) > 0 else 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'total_trades': len(trades)
        }
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'total_trades': 0
        }


async def quick_ml_test():
    """Quick ML optimization test"""
    
    print("\n" + "="*80)
    print("🚀 QUICK E2E TEST: ML-ОПТИМИЗАЦИЯ (EMA CROSSOVER)")
    print("="*80 + "\n")
    
    # Load data
    print("📊 Loading data from database...")
    db = SessionLocal()
    
    try:
        stmt = select(BybitKlineAudit).where(
            BybitKlineAudit.symbol == 'BTCUSDT',
            BybitKlineAudit.interval == '15'
        ).order_by(
            BybitKlineAudit.open_time
        ).limit(2000)
        
        result = db.execute(stmt).scalars().all()
        
        data = pd.DataFrame([{
            'timestamp': r.open_time_dt or datetime.fromtimestamp(r.open_time/1000, tz=timezone.utc),
            'open': r.open_price,
            'high': r.high_price,
            'low': r.low_price,
            'close': r.close_price,
            'volume': r.volume
        } for r in result])
        
        print(f"✅ Loaded {len(data):,} bars")
        print(f"   Period: {data['timestamp'].min().date()} → {data['timestamp'].max().date()}")
        print(f"   Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}\n")
        
    finally:
        db.close()
    
    # Baseline test
    print("🔧 Baseline backtest...")
    baseline = simple_ema_backtest(data, fast=10, slow=30, take_profit=0.02, stop_loss=0.01)
    
    print(f"✅ Baseline results:")
    print(f"   Return: {baseline['total_return']*100:.2f}%")
    print(f"   Sharpe: {baseline['sharpe_ratio']:.2f}")
    print(f"   Max DD: {baseline['max_drawdown']*100:.2f}%")
    print(f"   Win Rate: {baseline['win_rate']*100:.2f}%")
    print(f"   Trades: {baseline['total_trades']}\n")
    
    # ML Optimization
    print("🤖 ML-оптимизация (LightGBM)...")
    
    from backend.ml.optimizer import LightGBMOptimizer
    
    param_space = {
        'fast': [5, 10, 15, 20],
        'slow': [20, 30, 40, 50],
        'take_profit': [0.01, 0.015, 0.02, 0.03],
        'stop_loss': [0.005, 0.01, 0.015, 0.02]
    }
    
    def objective(params):
        """Objective function"""
        result = simple_ema_backtest(
            data, 
            fast=int(params['fast']), 
            slow=int(params['slow']),
            take_profit=float(params['take_profit']),
            stop_loss=float(params['stop_loss'])
        )
        
        sharpe = result['sharpe_ratio']
        trades = result['total_trades']
        
        # Penalty for low trades
        if trades < 5:
            sharpe *= 0.1
        elif trades < 10:
            sharpe *= 0.5
        
        return sharpe
    
    optimizer = LightGBMOptimizer(
        objective_function=objective,
        param_space=param_space,
        n_jobs=-1,
        verbose=1
    )
    
    start_time = datetime.now()
    result = await optimizer.optimize(n_trials=30)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"✅ Optimization complete in {elapsed:.1f}s\n")
    
    # Final backtest with optimized params
    print("📈 Final backtest with optimized params...")
    final = simple_ema_backtest(
        data,
        fast=int(result.best_params['fast']),
        slow=int(result.best_params['slow']),
        take_profit=float(result.best_params['take_profit']),
        stop_loss=float(result.best_params['stop_loss'])
    )
    
    print(f"\nЛучшие параметры:")
    for key, value in result.best_params.items():
        print(f"  {key}: {value}")
    
    print(f"\n✅ Optimized results:")
    print(f"   Return: {final['total_return']*100:.2f}%")
    print(f"   Sharpe: {final['sharpe_ratio']:.2f}")
    print(f"   Max DD: {final['max_drawdown']*100:.2f}%")
    print(f"   Win Rate: {final['win_rate']*100:.2f}%")
    print(f"   Trades: {final['total_trades']}\n")
    
    # Comparison
    print("="*80)
    print("📊 COMPARISON")
    print("="*80)
    
    ret_improvement = ((final['total_return'] - baseline['total_return']) / (abs(baseline['total_return']) + 1e-9)) * 100
    sharpe_improvement = ((final['sharpe_ratio'] - baseline['sharpe_ratio']) / (abs(baseline['sharpe_ratio']) + 1e-9)) * 100
    
    print(f"\n{'Metric':<20} {'Baseline':<15} {'Optimized':<15} {'Change':<15}")
    print("-" * 65)
    print(f"{'Return':<20} {baseline['total_return']*100:>6.2f}% {'':<8} {final['total_return']*100:>6.2f}% {'':<8} {ret_improvement:>+6.1f}%")
    print(f"{'Sharpe Ratio':<20} {baseline['sharpe_ratio']:>14.2f} {final['sharpe_ratio']:>14.2f} {sharpe_improvement:>+14.1f}%")
    print(f"{'Win Rate':<20} {baseline['win_rate']*100:>6.2f}% {'':<8} {final['win_rate']*100:>6.2f}% {'':<8} {(final['win_rate']-baseline['win_rate'])*100:>+6.1f}%")
    print(f"{'Trades':<20} {baseline['total_trades']:>14} {final['total_trades']:>14} {final['total_trades']-baseline['total_trades']:>+14}")
    
    print("\n" + "="*80)
    print("✅ E2E TEST COMPLETE!")
    print("="*80)
    print(f"\n🎯 Summary:")
    print(f"   Data: {len(data):,} bars")
    print(f"   Optimizations: 30 trials")
    print(f"   Time: {elapsed:.1f}s")
    print(f"   Best Sharpe: {final['sharpe_ratio']:.2f}")
    print(f"   Improvement: {sharpe_improvement:+.1f}%\n")


if __name__ == '__main__':
    asyncio.run(quick_ml_test())

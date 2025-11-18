"""
Full Walk-Forward Optimization Execution - Task 1.2
22 cycles, 8K IS / 2K OOS / 2K step
Estimated duration: 4.6 hours

Sprint 1, Week 1 (Oct 30 - Nov 5, 2025)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.core.backtest_engine import BacktestEngine
from loguru import logger
import pandas as pd
import numpy as np


# Configure logger
log_file = f"logs/wfo_full_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger.add(log_file, rotation="100 MB", level="INFO")


def calculate_ema(data: pd.DataFrame, period: int) -> pd.Series:
    """Calculate EMA for given period"""
    return data['close'].ewm(span=period, adjust=False).mean()


def generate_ema_signals(data: pd.DataFrame, fast_period: int, slow_period: int):
    """
    Generate EMA crossover signals
    
    Returns:
        DataFrame with 'signal' column: 1 (long), -1 (short), 0 (flat)
    """
    df = data.copy()
    
    # Calculate EMAs
    df['ema_fast'] = calculate_ema(df, fast_period)
    df['ema_slow'] = calculate_ema(df, slow_period)
    
    # Generate signals
    df['signal'] = 0
    df.loc[df['ema_fast'] > df['ema_slow'], 'signal'] = 1  # Long
    df.loc[df['ema_fast'] < df['ema_slow'], 'signal'] = -1  # Short
    
    return df


def backtest_ema_strategy(data: pd.DataFrame, fast_ema: int, slow_ema: int, 
                          initial_capital: float = 10000.0, 
                          commission: float = 0.00075):
    """
    Backtest EMA crossover strategy
    
    Returns:
        dict with performance metrics
    """
    df = generate_ema_signals(data, fast_ema, slow_ema)
    
    # Simulate trading
    capital = initial_capital
    position = 0  # 0: flat, 1: long, -1: short
    entry_price = 0
    trades = []
    equity_curve = [initial_capital]
    
    for i in range(1, len(df)):
        current_signal = df.iloc[i]['signal']
        prev_signal = df.iloc[i-1]['signal']
        current_price = df.iloc[i]['close']
        
        # Entry
        if position == 0 and current_signal != 0 and current_signal != prev_signal:
            position = current_signal
            entry_price = current_price
            capital = capital * (1 - commission)  # Entry commission
            
        # Exit
        elif position != 0 and current_signal != position:
            exit_price = current_price
            
            # Calculate PnL
            if position == 1:  # Long exit
                pnl_pct = (exit_price - entry_price) / entry_price
            else:  # Short exit
                pnl_pct = (entry_price - exit_price) / entry_price
            
            capital = capital * (1 + pnl_pct) * (1 - commission)  # Exit commission
            
            trades.append({
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position': 'long' if position == 1 else 'short',
                'pnl_pct': pnl_pct * 100,
                'pnl': capital - equity_curve[-1],
            })
            
            position = current_signal if current_signal != 0 else 0
            if position != 0:
                entry_price = current_price
                capital = capital * (1 - commission)
        
        equity_curve.append(capital)
    
    # Calculate metrics
    if len(trades) == 0:
        return {
            'total_return': 0,
            'total_trades': 0,
            'win_rate': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'profit_factor': 0,
        }
    
    returns = [t['pnl_pct'] for t in trades]
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]
    
    total_return = ((capital - initial_capital) / initial_capital) * 100
    win_rate = len(winning_trades) / len(trades) if len(trades) > 0 else 0
    
    # Sharpe
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
    else:
        sharpe_ratio = 0
    
    # Max Drawdown
    peak = initial_capital
    max_dd = 0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = ((peak - equity) / peak) * 100
        if dd > max_dd:
            max_dd = dd
    
    # Profit Factor
    gross_profit = sum(t['pnl'] for t in winning_trades) if winning_trades else 0
    gross_loss = abs(sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    return {
        'total_return': total_return,
        'total_trades': len(trades),
        'win_rate': win_rate,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_dd,
        'profit_factor': profit_factor,
        'trades': trades,
        'equity_curve': equity_curve,
    }


def run_walk_forward_optimization():
    """
    Run full Walk-Forward Optimization with 22 cycles
    
    Configuration:
    - In-sample: 8,000 bars (~28 days)
    - Out-sample: 2,000 bars (~7 days)
    - Step: 2,000 bars
    - Cycles: 22
    - Parameter space: Fast EMA [13-17], Slow EMA [38-42]
    """
    
    logger.info("="*80)
    logger.info("🚀 FULL WALK-FORWARD OPTIMIZATION - 22 CYCLES")
    logger.info("="*80)
    logger.info(f"Start time: {datetime.now()}")
    logger.info(f"Estimated duration: 4.6 hours")
    
    start_time = datetime.now()
    
    # Configuration
    in_sample = 8000
    out_sample = 2000
    step = 2000
    
    # Parameter space
    fast_emas = [13, 14, 15, 16, 17]
    slow_emas = [38, 39, 40, 41, 42]
    
    logger.info(f"\nConfiguration:")
    logger.info(f"  In-sample: {in_sample:,} bars (~{in_sample*5/60/24:.1f} days)")
    logger.info(f"  Out-sample: {out_sample:,} bars (~{out_sample*5/60/24:.1f} days)")
    logger.info(f"  Step: {step:,} bars")
    logger.info(f"  Parameter combinations: {len(fast_emas) * len(slow_emas)}")
    
    # Load data
    logger.info(f"\nLoading data from database...")
    db = SessionLocal()
    
    try:
        bars = db.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == 'BTCUSDT',
            BybitKlineAudit.interval == '5'
        ).order_by(BybitKlineAudit.open_time).all()
        
        data = pd.DataFrame([{
            'timestamp': bar.open_time_dt,
            'open': float(bar.open_price),
            'high': float(bar.high_price),
            'low': float(bar.low_price),
            'close': float(bar.close_price),
            'volume': float(bar.volume),
        } for bar in bars])
        
        logger.info(f"Loaded {len(data):,} bars")
        logger.info(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
        
    finally:
        db.close()
    
    # Walk-Forward periods
    periods = []
    all_oos_results = []
    all_is_results = []
    period_best_params = []
    
    start_idx = 0
    period_num = 0
    
    while start_idx + in_sample + out_sample <= len(data):
        period_num += 1
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 PERIOD {period_num}/22")
        logger.info(f"{'='*80}")
        
        # Split data
        is_data = data.iloc[start_idx:start_idx + in_sample].copy()
        oos_data = data.iloc[start_idx + in_sample:start_idx + in_sample + out_sample].copy()
        
        logger.info(f"In-sample: bars {start_idx:,} to {start_idx + in_sample:,}")
        logger.info(f"  Date range: {is_data['timestamp'].min()} to {is_data['timestamp'].max()}")
        logger.info(f"Out-sample: bars {start_idx + in_sample:,} to {start_idx + in_sample + out_sample:,}")
        logger.info(f"  Date range: {oos_data['timestamp'].min()} to {oos_data['timestamp'].max()}")
        
        # Optimization on in-sample
        logger.info(f"\nOptimizing parameters on in-sample...")
        best_sharpe = -999
        best_params = None
        best_is_result = None
        
        for fast in fast_emas:
            for slow in slow_emas:
                if fast >= slow:
                    continue
                
                result = backtest_ema_strategy(is_data, fast, slow)
                
                if result['sharpe_ratio'] > best_sharpe:
                    best_sharpe = result['sharpe_ratio']
                    best_params = {'fast_ema': fast, 'slow_ema': slow}
                    best_is_result = result
        
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"  IS Sharpe: {best_is_result['sharpe_ratio']:.3f}")
        logger.info(f"  IS Return: {best_is_result['total_return']:.2f}%")
        logger.info(f"  IS Trades: {best_is_result['total_trades']}")
        logger.info(f"  IS Win Rate: {best_is_result['win_rate']:.2%}")
        
        # Test on out-sample
        logger.info(f"\nTesting on out-sample...")
        oos_result = backtest_ema_strategy(
            oos_data, 
            best_params['fast_ema'], 
            best_params['slow_ema']
        )
        
        logger.info(f"OOS Results:")
        logger.info(f"  OOS Sharpe: {oos_result['sharpe_ratio']:.3f}")
        logger.info(f"  OOS Return: {oos_result['total_return']:.2f}%")
        logger.info(f"  OOS Trades: {oos_result['total_trades']}")
        logger.info(f"  OOS Win Rate: {oos_result['win_rate']:.2%}")
        
        # Efficiency
        if best_is_result['sharpe_ratio'] > 0:
            efficiency = (oos_result['sharpe_ratio'] / best_is_result['sharpe_ratio']) * 100
        else:
            efficiency = 0
        
        logger.info(f"  Efficiency: {efficiency:.1f}%")
        
        # Store results
        periods.append({
            'period': period_num,
            'start_idx': start_idx,
            'is_start': start_idx,
            'is_end': start_idx + in_sample,
            'oos_start': start_idx + in_sample,
            'oos_end': start_idx + in_sample + out_sample,
            'best_params': best_params,
            'is_sharpe': best_is_result['sharpe_ratio'],
            'is_return': best_is_result['total_return'],
            'is_trades': best_is_result['total_trades'],
            'oos_sharpe': oos_result['sharpe_ratio'],
            'oos_return': oos_result['total_return'],
            'oos_trades': oos_result['total_trades'],
            'efficiency': efficiency,
        })
        
        all_is_results.append(best_is_result)
        all_oos_results.append(oos_result)
        period_best_params.append(best_params)
        
        # Progress
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        eta_total = (elapsed / period_num) * 22
        eta_remaining = eta_total - elapsed
        
        logger.info(f"\nProgress: {period_num}/22 ({period_num/22*100:.1f}%)")
        logger.info(f"  Elapsed: {elapsed:.1f} minutes")
        logger.info(f"  ETA: {eta_remaining:.1f} minutes (~{eta_remaining/60:.1f} hours)")
        logger.info(f"  Expected completion: {datetime.now() + timedelta(minutes=eta_remaining)}")
        
        # Move to next period
        start_idx += step
    
    # Final analysis
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📈 FINAL WALK-FORWARD RESULTS")
    logger.info(f"{'='*80}")
    logger.info(f"Execution time: {duration:.1f} minutes ({duration/60:.2f} hours)")
    logger.info(f"Periods: {len(periods)}")
    
    # Overall metrics
    avg_is_sharpe = np.mean([p['is_sharpe'] for p in periods])
    avg_oos_sharpe = np.mean([p['oos_sharpe'] for p in periods])
    overall_efficiency = (avg_oos_sharpe / avg_is_sharpe * 100) if avg_is_sharpe > 0 else 0
    
    avg_is_return = np.mean([p['is_return'] for p in periods])
    avg_oos_return = np.mean([p['oos_return'] for p in periods])
    
    logger.info(f"\nOverall Metrics:")
    logger.info(f"  Avg IS Sharpe: {avg_is_sharpe:.3f}")
    logger.info(f"  Avg OOS Sharpe: {avg_oos_sharpe:.3f}")
    logger.info(f"  Efficiency: {overall_efficiency:.1f}%")
    logger.info(f"  Avg IS Return: {avg_is_return:.2f}%")
    logger.info(f"  Avg OOS Return: {avg_oos_return:.2f}%")
    
    # Parameter stability
    fast_emas_used = [p['best_params']['fast_ema'] for p in periods]
    slow_emas_used = [p['best_params']['slow_ema'] for p in periods]
    
    fast_std = np.std(fast_emas_used)
    slow_std = np.std(slow_emas_used)
    
    # Normalized stability (0-1, higher = more stable)
    fast_range = max(fast_emas) - min(fast_emas)
    slow_range = max(slow_emas) - min(slow_emas)
    fast_stability = 1 - (fast_std / fast_range) if fast_range > 0 else 1
    slow_stability = 1 - (slow_std / slow_range) if slow_range > 0 else 1
    param_stability = (fast_stability + slow_stability) / 2
    
    logger.info(f"\nParameter Stability:")
    logger.info(f"  Fast EMA std: {fast_std:.2f}")
    logger.info(f"  Slow EMA std: {slow_std:.2f}")
    logger.info(f"  Overall stability: {param_stability:.3f}")
    
    # Consistency
    oos_returns = [p['oos_return'] for p in periods]
    consistency_cv = np.std(oos_returns) / abs(np.mean(oos_returns)) if np.mean(oos_returns) != 0 else 0
    
    logger.info(f"\nConsistency:")
    logger.info(f"  OOS returns CV: {consistency_cv:.3f}")
    logger.info(f"  Profitable periods: {sum(1 for r in oos_returns if r > 0)}/{len(periods)}")
    
    # Perplexity benchmarks
    logger.info(f"\n✅ PERPLEXITY BENCHMARKS:")
    
    if 120 <= overall_efficiency <= 160:
        logger.success(f"  ✅ Efficiency {overall_efficiency:.1f}% (target 120-160%)")
    else:
        logger.warning(f"  ⚠️ Efficiency {overall_efficiency:.1f}% (target 120-160%)")
    
    if 0.60 <= param_stability <= 0.95:
        logger.success(f"  ✅ Param Stability {param_stability:.3f} (target 0.60-0.95)")
    else:
        logger.warning(f"  ⚠️ Param Stability {param_stability:.3f} (target 0.60-0.95)")
    
    if 0.15 <= consistency_cv <= 0.45:
        logger.success(f"  ✅ Consistency CV {consistency_cv:.3f} (target 0.15-0.45)")
    else:
        logger.warning(f"  ⚠️ Consistency CV {consistency_cv:.3f} (target 0.15-0.45)")
    
    if len(periods) >= 10:
        logger.success(f"  ✅ Periods {len(periods)} (target 10+)")
    else:
        logger.warning(f"  ⚠️ Periods {len(periods)} (target 10+)")
    
    # Save results
    results = {
        'execution_time_minutes': duration,
        'periods': periods,
        'overall_metrics': {
            'avg_is_sharpe': avg_is_sharpe,
            'avg_oos_sharpe': avg_oos_sharpe,
            'efficiency': overall_efficiency,
            'avg_is_return': avg_is_return,
            'avg_oos_return': avg_oos_return,
            'param_stability': param_stability,
            'consistency_cv': consistency_cv,
        },
        'config': {
            'in_sample': in_sample,
            'out_sample': out_sample,
            'step': step,
            'fast_emas': fast_emas,
            'slow_emas': slow_emas,
        }
    }
    
    output_file = f"results/wfo_22_cycles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path("results").mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.success(f"\n✅ Results saved to: {output_file}")
    logger.success(f"\n🎉 WALK-FORWARD OPTIMIZATION COMPLETE!")
    
    return results


if __name__ == "__main__":
    try:
        results = run_walk_forward_optimization()
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

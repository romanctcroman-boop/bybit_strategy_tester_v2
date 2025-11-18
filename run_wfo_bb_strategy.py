"""
Run Walk-Forward Optimization for Bollinger Bands Mean-Reversion Strategy
Adapted from run_wfo_sr_strategy.py
"""
import json
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy

# Basic logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def load_bars_from_db(symbol: str = 'BTCUSDT', interval: str = '5') -> pd.DataFrame:
    session = SessionLocal()
    rows = session.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol, BybitKlineAudit.interval == interval).all()
    session.close()
    data = [{
        'open_time': r.open_time,
        'open': float(r.open_price),
        'high': float(r.high_price),
        'low': float(r.low_price),
        'close': float(r.close_price),
        'volume': float(r.volume)
    } for r in rows]
    df = pd.DataFrame(data)
    df['open_time'] = pd.to_datetime(df['open_time'])
    return df


def backtest_bb_strategy(data: pd.DataFrame, params: dict, initial_capital: float = 10000.0, commission: float = 0.00055) -> dict:
    """Full backtest with PnL, Sharpe, win rate, max drawdown"""
    strat = BollingerMeanReversionStrategy(**params)
    strat.on_start(data.copy())
    
    capital = initial_capital
    position = 0  # 0: flat, 1: long, -1: short
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    trades = []
    equity_curve = [initial_capital]
    
    for i in range(len(data)):
        bar = data.iloc[i]
        current_price = float(bar['close'])
        sig = strat.on_bar(bar, data.iloc[:i+1])
        
        # Check stop loss / take profit first
        if position != 0:
            hit_stop = (position == 1 and current_price <= stop_loss) or (position == -1 and current_price >= stop_loss)
            hit_tp = (position == 1 and current_price >= take_profit) or (position == -1 and current_price <= take_profit)
            
            if hit_stop or hit_tp:
                exit_price = stop_loss if hit_stop else take_profit
                if position == 1:
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                capital = capital * (1 + pnl_pct) * (1 - commission)
                trades.append({'entry_price': entry_price, 'exit_price': exit_price, 'position': 'long' if position == 1 else 'short', 'pnl_pct': pnl_pct * 100, 'pnl': capital - equity_curve[-1], 'exit_reason': 'stop_loss' if hit_stop else 'take_profit'})
                position = 0
        
        # Process signal
        if sig:
            if sig['action'] == 'LONG' and position == 0:
                position = 1
                entry_price = current_price
                stop_loss = sig.get('stop_loss', current_price * 0.992)
                take_profit = sig.get('take_profit', current_price * 1.02)
                capital = capital * (1 - commission)
            elif sig['action'] == 'SHORT' and position == 0:
                position = -1
                entry_price = current_price
                stop_loss = sig.get('stop_loss', current_price * 1.008)
                take_profit = sig.get('take_profit', current_price * 0.98)
                capital = capital * (1 - commission)
            elif sig['action'] == 'CLOSE' and position != 0:
                exit_price = current_price
                if position == 1:
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                capital = capital * (1 + pnl_pct) * (1 - commission)
                trades.append({'entry_price': entry_price, 'exit_price': exit_price, 'position': 'long' if position == 1 else 'short', 'pnl_pct': pnl_pct * 100, 'pnl': capital - equity_curve[-1], 'exit_reason': 'time_exit'})
                position = 0
        
        equity_curve.append(capital)
    
    # Calculate metrics
    if len(trades) == 0:
        return {'total_return': 0, 'total_trades': 0, 'win_rate': 0, 'sharpe_ratio': 0, 'max_drawdown': 0, 'profit_factor': 0}
    
    returns = [t['pnl_pct'] for t in trades]
    winning = [t for t in trades if t['pnl'] > 0]
    losing = [t for t in trades if t['pnl'] <= 0]
    total_return = ((capital - initial_capital) / initial_capital) * 100
    win_rate = len(winning) / len(trades) if len(trades) > 0 else 0
    sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
    
    peak = initial_capital
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = ((peak - eq) / peak) * 100
        if dd > max_dd:
            max_dd = dd
    
    gross_profit = sum(t['pnl'] for t in winning) if winning else 0
    gross_loss = abs(sum(t['pnl'] for t in losing)) if losing else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    return {'total_return': total_return, 'total_trades': len(trades), 'win_rate': win_rate, 'sharpe_ratio': sharpe, 'max_drawdown': max_dd, 'profit_factor': profit_factor, 'trades': trades}


def run_wfo():
    logger.info('Loading data...')
    df = load_bars_from_db()
    logger.info(f'Loaded {len(df)} bars')

    # WFO config
    in_sample = 8000
    out_sample = 2000
    step = 2000
    total_bars = len(df)
    
    # Parameter space for Bollinger Bands
    # Adjusted: Lower std_dev (1.5-2.0) for more frequent touches
    # entry_threshold_pct now means INSIDE band tolerance (allows entry before exact touch)
    param_space = [
        {'bb_period': 20, 'bb_std_dev': 1.5, 'entry_threshold_pct': 0.20, 'stop_loss_pct': 0.8, 'max_holding_bars': 48},
        {'bb_period': 20, 'bb_std_dev': 2.0, 'entry_threshold_pct': 0.15, 'stop_loss_pct': 1.0, 'max_holding_bars': 60},
        {'bb_period': 30, 'bb_std_dev': 1.5, 'entry_threshold_pct': 0.25, 'stop_loss_pct': 1.2, 'max_holding_bars': 72},
    ]

    logger.info(f'Will run 22 periods')
    results = []

    start_idx = 0
    period = 0
    while (start_idx + in_sample + out_sample) <= total_bars and period < 22:
        period += 1
        is_df = df.iloc[start_idx:start_idx + in_sample].reset_index(drop=True)
        oos_df = df.iloc[start_idx + in_sample:start_idx + in_sample + out_sample].reset_index(drop=True)
        logger.info(f'PERIOD {period}: IS {start_idx}-{start_idx+in_sample}, OOS {start_idx+in_sample}-{start_idx+in_sample+out_sample}')
        
        # Simple grid search on IS: Pick best params by IS Sharpe
        best = None
        best_score = -np.inf
        for p in param_space:
            is_result = backtest_bb_strategy(is_df, p)
            score = is_result['sharpe_ratio']
            if score > best_score:
                best_score = score
                best = p
        
        logger.info(f' Best params: {best} (IS Sharpe {best_score:.2f})')
        
        # Run OOS backtest
        oos_result = backtest_bb_strategy(oos_df, best)
        oos_metrics = {
            'oos_return': oos_result['total_return'],
            'oos_sharpe': oos_result['sharpe_ratio'],
            'oos_trades': oos_result['total_trades'],
            'oos_win_rate': oos_result['win_rate'],
            'oos_max_dd': oos_result['max_drawdown'],
            'oos_profit_factor': oos_result['profit_factor']
        }
        logger.info(f' OOS metrics: {oos_metrics}')
        
        results.append({
            'period': period,
            'best_params': best,
            'is_sharpe': best_score,
            'oos_metrics': oos_metrics
        })
        
        start_idx += step

    now = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    out_path = f'results/wfo_bb_22_cycles_{now}.json'
    with open(out_path, 'w') as f:
        json.dump({'execution_time_minutes': 0, 'periods': results}, f, indent=2)
    logger.info(f'Results saved to {out_path}')


if __name__ == '__main__':
    run_wfo()

"""
Demo script for Advanced Visualizations (ТЗ 3.7.2)

Generates all chart types and saves them as HTML files for review:
1. Equity curve with drawdown overlay (2 variants)
2. PnL distribution histogram
3. Parameter optimization heatmap

Run: python backend/visualization/demo_charts.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

from advanced_charts import (
    create_equity_curve,
    create_drawdown_overlay,
    create_pnl_distribution,
    create_parameter_heatmap,
)


def generate_realistic_equity_curve(
    initial_capital: float = 10000,
    days: int = 90,
    mean_daily_return: float = 0.002,
    volatility: float = 0.015,
) -> pd.Series:
    """Generate realistic equity curve with trends and drawdowns."""
    hours = days * 24
    dates = pd.date_range(
        start=datetime(2025, 1, 1),
        periods=hours,
        freq='1h'
    )
    
    # Generate returns with regime changes
    np.random.seed(42)
    returns = np.random.normal(mean_daily_return / 24, volatility / np.sqrt(24), hours)
    
    # Add trend periods
    returns[100:200] += 0.001  # Bull period
    returns[300:350] -= 0.002  # Drawdown period
    returns[500:600] += 0.0015  # Recovery
    
    # Calculate equity
    equity = initial_capital * (1 + returns).cumprod()
    
    return pd.Series(equity, index=dates, name='equity')


def generate_realistic_trades(n_trades: int = 100) -> pd.DataFrame:
    """Generate realistic trade PnL distribution."""
    np.random.seed(42)
    
    # 60% winning trades, 40% losing
    n_winners = int(n_trades * 0.6)
    n_losers = n_trades - n_winners
    
    # Winners: mean +$75, std $40
    winners = np.random.normal(75, 40, n_winners)
    
    # Losers: mean -$50, std $25
    losers = np.random.normal(-50, 25, n_losers)
    
    # Combine and shuffle
    pnl_values = np.concatenate([winners, losers])
    np.random.shuffle(pnl_values)
    
    dates = pd.date_range(
        start=datetime(2025, 1, 1),
        periods=n_trades,
        freq='3h'
    )
    
    return pd.DataFrame({
        'pnl': pnl_values,
        'entry_time': dates,
        'exit_time': dates + timedelta(hours=2),
    })


def generate_optimization_results() -> pd.DataFrame:
    """Generate grid search optimization results."""
    ma_fast_values = range(5, 25, 5)  # 5, 10, 15, 20
    ma_slow_values = range(20, 60, 10)  # 20, 30, 40, 50
    
    results = []
    np.random.seed(42)
    
    for ma_fast in ma_fast_values:
        for ma_slow in ma_slow_values:
            if ma_fast < ma_slow:
                # Simulate realistic performance surface
                # Best around ma_fast=10, ma_slow=30
                distance = abs(ma_fast - 10) + abs(ma_slow - 30) / 10
                base_return = 0.15 - distance * 0.01
                noise = np.random.normal(0, 0.02)
                
                total_return = max(base_return + noise, -0.05)
                
                results.append({
                    'ma_fast': ma_fast,
                    'ma_slow': ma_slow,
                    'total_return': total_return,
                    'sharpe_ratio': total_return * 8 if total_return > 0 else total_return * 2,
                    'max_drawdown': abs(np.random.normal(0.12, 0.03)),
                    'win_rate': np.clip(0.5 + total_return, 0.3, 0.75),
                })
    
    return pd.DataFrame(results)


def main():
    """Generate and save all chart examples."""
    print("🎨 Generating Advanced Visualization Examples (ТЗ 3.7.2)")
    print("=" * 60)
    
    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / 'docs' / 'charts'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate data
    print("\n📊 Generating sample data...")
    equity = generate_realistic_equity_curve()
    trades = generate_realistic_trades()
    opt_results = generate_optimization_results()
    
    print(f"  ✓ Equity curve: {len(equity)} points")
    print(f"  ✓ Trades: {len(trades)} trades")
    print(f"  ✓ Optimization: {len(opt_results)} parameter combinations")
    
    # 1. Equity curve with separate drawdown subplot
    print("\n1️⃣  Creating equity curve with drawdown subplot...")
    fig1 = create_equity_curve(
        equity,
        title="Backtest Equity Curve",
        show_drawdown=True,
        height=700,
    )
    output1 = output_dir / 'equity_curve_with_drawdown.html'
    fig1.write_html(str(output1))
    print(f"  ✓ Saved: {output1}")
    
    # 2. Equity curve with drawdown overlay
    print("\n2️⃣  Creating equity curve with drawdown overlay...")
    fig2 = create_drawdown_overlay(
        equity,
        title="Equity & Drawdown Analysis",
        height=600,
    )
    output2 = output_dir / 'equity_drawdown_overlay.html'
    fig2.write_html(str(output2))
    print(f"  ✓ Saved: {output2}")
    
    # 3. PnL distribution
    print("\n3️⃣  Creating PnL distribution histogram...")
    fig3 = create_pnl_distribution(
        trades,
        pnl_column='pnl',
        title="Trade PnL Distribution",
        bins=25,
        height=500,
    )
    output3 = output_dir / 'pnl_distribution.html'
    fig3.write_html(str(output3))
    print(f"  ✓ Saved: {output3}")
    
    # Calculate and display PnL stats
    mean_pnl = trades['pnl'].mean()
    median_pnl = trades['pnl'].median()
    win_rate = (trades['pnl'] > 0).mean() * 100
    print(f"  📈 Mean PnL: ${mean_pnl:.2f}")
    print(f"  📈 Median PnL: ${median_pnl:.2f}")
    print(f"  📈 Win Rate: {win_rate:.1f}%")
    
    # 4. Parameter heatmap - Total Return
    print("\n4️⃣  Creating parameter heatmap (Total Return)...")
    fig4 = create_parameter_heatmap(
        opt_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='total_return',
        title="MA Parameter Optimization: Total Return",
        height=600,
        width=900,
    )
    output4 = output_dir / 'param_heatmap_return.html'
    fig4.write_html(str(output4))
    print(f"  ✓ Saved: {output4}")
    
    # Find best parameters
    best_idx = opt_results['total_return'].idxmax()
    best_params = opt_results.loc[best_idx]
    print(f"  🏆 Best params: MA Fast={best_params['ma_fast']}, MA Slow={best_params['ma_slow']}")
    print(f"  🏆 Best return: {best_params['total_return']:.2%}")
    
    # 5. Parameter heatmap - Sharpe Ratio
    print("\n5️⃣  Creating parameter heatmap (Sharpe Ratio)...")
    fig5 = create_parameter_heatmap(
        opt_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='sharpe_ratio',
        title="MA Parameter Optimization: Sharpe Ratio",
        height=600,
        width=900,
    )
    output5 = output_dir / 'param_heatmap_sharpe.html'
    fig5.write_html(str(output5))
    print(f"  ✓ Saved: {output5}")
    
    # 6. Parameter heatmap - Max Drawdown
    print("\n6️⃣  Creating parameter heatmap (Max Drawdown)...")
    fig6 = create_parameter_heatmap(
        opt_results,
        param_x='ma_fast',
        param_y='ma_slow',
        metric='max_drawdown',
        title="MA Parameter Optimization: Max Drawdown",
        height=600,
        width=900,
    )
    output6 = output_dir / 'param_heatmap_drawdown.html'
    fig6.write_html(str(output6))
    print(f"  ✓ Saved: {output6}")
    
    print("\n" + "=" * 60)
    print("✅ All charts generated successfully!")
    print(f"📁 Output directory: {output_dir}")
    print("\n💡 Open the HTML files in your browser to view interactive charts.")
    print("\nGenerated files:")
    for html_file in sorted(output_dir.glob('*.html')):
        print(f"  • {html_file.name}")


if __name__ == '__main__':
    main()

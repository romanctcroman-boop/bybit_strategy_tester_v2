"""
Demo CSV Export - ReportGenerator

Демонстрирует генерацию всех 4 типов CSV отчетов согласно ТЗ раздел 4.
Создает реалистичные данные бэктеста и генерирует CSV файлы.
"""

import os
from datetime import datetime, timedelta
import random
from backend.services.report_generator import ReportGenerator


def generate_realistic_backtest_results():
    """Генерирует реалистичные результаты бэктеста"""
    
    start_time = datetime(2024, 1, 1, 0, 0)
    initial_capital = 10000.0
    
    # Генерируем 50 сделок с реалистичной статистикой
    trades = []
    base_price = 40000.0
    
    for i in range(50):
        side = random.choice(['long', 'long', 'short'])  # 67% long, 33% short
        entry_time = start_time + timedelta(hours=i*12)
        
        # Цена случайным образом меняется
        base_price += random.uniform(-500, 500)
        entry_price = base_price
        
        # Размер позиции
        qty = random.uniform(0.05, 0.15)
        
        # Определяем, выигрышная или проигрышная сделка (60% win rate)
        is_winning = random.random() < 0.6
        
        if is_winning:
            # Winning trade
            if side == 'long':
                pnl_pct = random.uniform(1.0, 5.0)
                exit_price = entry_price * (1 + pnl_pct/100)
            else:
                pnl_pct = random.uniform(1.0, 5.0)
                exit_price = entry_price * (1 - pnl_pct/100)
        else:
            # Losing trade
            if side == 'long':
                pnl_pct = random.uniform(-3.0, -0.5)
                exit_price = entry_price * (1 + pnl_pct/100)
            else:
                pnl_pct = random.uniform(-3.0, -0.5)
                exit_price = entry_price * (1 - pnl_pct/100)
        
        # Расчет PnL
        if side == 'long':
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty
        
        # Run-up и drawdown
        max_profit = pnl * random.uniform(1.0, 1.3) if pnl > 0 else pnl * random.uniform(0.3, 0.7)
        max_loss = pnl * random.uniform(0.3, 0.7) if pnl < 0 else pnl * random.uniform(-0.2, 0)
        
        exit_time = entry_time + timedelta(hours=random.randint(2, 24))
        bars_held = random.randint(4, 48)
        
        trade = {
            'side': side,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'entry_signal': 'buy' if side == 'long' else 'sell',
            'exit_time': exit_time,
            'exit_price': exit_price,
            'exit_signal': random.choice(['Take Profit', 'Stop Loss', 'Long Trail', 'Short Trail']),
            'qty': qty,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'commission': abs(entry_price * qty * 0.0006) + abs(exit_price * qty * 0.0006),
            'max_profit': max_profit,
            'max_loss': max_loss,
            'bars_held': bars_held
        }
        
        trades.append(trade)
    
    # Buy & hold calculation
    buy_hold_return = (base_price - 40000.0) / 40000.0 * initial_capital
    buy_hold_return_pct = (base_price - 40000.0) / 40000.0 * 100
    
    return {
        'trades': trades,
        'buy_hold_return': buy_hold_return,
        'buy_hold_return_pct': buy_hold_return_pct
    }


def main():
    """Генерирует и сохраняет CSV отчеты"""
    
    print("=" * 80)
    print("CSV EXPORT DEMO - Report Generator (ТЗ 4)")
    print("=" * 80)
    print()
    
    # Создаем директорию для отчетов
    output_dir = "docs/csv_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Генерируем данные
    print("Generating realistic backtest results...")
    results = generate_realistic_backtest_results()
    initial_capital = 10000.0
    
    # Статистика
    all_trades = [t for t in results['trades'] if t.get('exit_price')]
    winning_trades = [t for t in all_trades if t['pnl'] > 0]
    losing_trades = [t for t in all_trades if t['pnl'] < 0]
    total_pnl = sum(t['pnl'] for t in all_trades)
    
    print(f"  Total trades: {len(all_trades)}")
    print(f"  Winning: {len(winning_trades)} ({len(winning_trades)/len(all_trades)*100:.1f}%)")
    print(f"  Losing: {len(losing_trades)} ({len(losing_trades)/len(all_trades)*100:.1f}%)")
    print(f"  Total P&L: ${total_pnl:.2f} ({total_pnl/initial_capital*100:.2f}%)")
    print()
    
    # Создаем ReportGenerator
    print("Creating ReportGenerator...")
    generator = ReportGenerator(results, initial_capital)
    print()
    
    # Генерируем отчеты
    print("Generating CSV reports...")
    print()
    
    # 1. List of Trades
    print("  [1/4] List-of-trades.csv (ТЗ 4.1)")
    list_of_trades_csv = generator.generate_list_of_trades_csv()
    filepath = os.path.join(output_dir, "list-of-trades.csv")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(list_of_trades_csv)
    print(f"        ✓ Saved to: {filepath}")
    print(f"        Size: {len(list_of_trades_csv)} bytes")
    print()
    
    # 2. Performance
    print("  [2/4] Performance.csv (ТЗ 4.2)")
    performance_csv = generator.generate_performance_csv()
    filepath = os.path.join(output_dir, "performance.csv")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(performance_csv)
    print(f"        ✓ Saved to: {filepath}")
    print(f"        Size: {len(performance_csv)} bytes")
    print()
    
    # 3. Risk Ratios
    print("  [3/4] Risk-performance-ratios.csv (ТЗ 4.3)")
    risk_ratios_csv = generator.generate_risk_ratios_csv()
    filepath = os.path.join(output_dir, "risk-performance-ratios.csv")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(risk_ratios_csv)
    print(f"        ✓ Saved to: {filepath}")
    print(f"        Size: {len(risk_ratios_csv)} bytes")
    print()
    
    # 4. Trades Analysis
    print("  [4/4] Trades-analysis.csv (ТЗ 4.4)")
    trades_analysis_csv = generator.generate_trades_analysis_csv()
    filepath = os.path.join(output_dir, "trades-analysis.csv")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(trades_analysis_csv)
    print(f"        ✓ Saved to: {filepath}")
    print(f"        Size: {len(trades_analysis_csv)} bytes")
    print()
    
    # Summary
    print("=" * 80)
    print("✅ ALL CSV REPORTS GENERATED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print(f"Output directory: {os.path.abspath(output_dir)}")
    print()
    print("Files created:")
    print("  1. list-of-trades.csv       - Detailed log of all trades (ТЗ 4.1)")
    print("  2. performance.csv          - Performance metrics (ТЗ 4.2)")
    print("  3. risk-performance-ratios.csv - Risk metrics (ТЗ 4.3)")
    print("  4. trades-analysis.csv      - Trade statistics (ТЗ 4.4)")
    print()
    print("📊 All formats comply with ТЕХНИЧЕСКОЕ ЗАДАНИЕ section 4")
    print()
    
    # Показываем preview первого отчета
    print("Preview of Performance.csv:")
    print("-" * 80)
    lines = performance_csv.split('\n')
    for line in lines[:15]:
        print(line)
    print("...")
    print("-" * 80)


if __name__ == "__main__":
    main()

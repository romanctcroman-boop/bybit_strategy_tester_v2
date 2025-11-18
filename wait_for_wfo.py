"""
Auto-monitor WFO progress and show results when complete
"""

import sys
import time
from pathlib import Path
from datetime import datetime
import json

def check_wfo_status():
    """Check if WFO is still running"""
    
    logs_dir = Path("logs")
    wfo_logs = list(logs_dir.glob("wfo_full_run_*.log"))
    
    if not wfo_logs:
        print("❌ No WFO log files found")
        return False, None
    
    latest_log = max(wfo_logs, key=lambda p: p.stat().st_mtime)
    
    with open(latest_log, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if completed
    if "🎉 WALK-FORWARD OPTIMIZATION COMPLETE!" in content:
        return True, latest_log
    
    # Extract current period
    lines = content.split('\n')
    current_period = 0
    
    for line in reversed(lines):
        if "PERIOD" in line and "/" in line:
            try:
                parts = line.split("PERIOD")[1].split("/")
                current_period = int(parts[0].strip())
                break
            except:
                pass
    
    return False, (current_period, latest_log)


def show_results():
    """Show final WFO results"""
    
    results_dir = Path("results")
    result_files = list(results_dir.glob("wfo_22_cycles_*.json"))
    
    if not result_files:
        print("\n⚠️ Results file not found yet")
        return False
    
    latest_result = max(result_files, key=lambda p: p.stat().st_mtime)
    
    print("\n" + "="*80)
    print("🎉 WALK-FORWARD OPTIMIZATION COMPLETE!")
    print("="*80)
    
    with open(latest_result, 'r') as f:
        results = json.load(f)
    
    overall = results['overall_metrics']
    config = results['config']
    
    print(f"\n⏱️ Execution Time: {results['execution_time_minutes']:.1f} minutes")
    print(f"📊 Periods Completed: {len(results['periods'])}")
    
    print(f"\n📈 OVERALL METRICS:")
    print(f"  Avg IS Sharpe: {overall['avg_is_sharpe']:.3f}")
    print(f"  Avg OOS Sharpe: {overall['avg_oos_sharpe']:.3f}")
    print(f"  Efficiency: {overall['efficiency']:.1f}%")
    print(f"  Avg IS Return: {overall['avg_is_return']:.2f}%")
    print(f"  Avg OOS Return: {overall['avg_oos_return']:.2f}%")
    print(f"  Parameter Stability: {overall['param_stability']:.3f}")
    print(f"  Consistency CV: {overall['consistency_cv']:.3f}")
    
    print(f"\n✅ PERPLEXITY BENCHMARKS:")
    
    # Efficiency
    efficiency = overall['efficiency']
    if 120 <= efficiency <= 160:
        print(f"  ✅ Efficiency {efficiency:.1f}% (target 120-160%)")
    else:
        print(f"  ⚠️ Efficiency {efficiency:.1f}% (target 120-160%)")
    
    # Parameter Stability
    param_stability = overall['param_stability']
    if 0.60 <= param_stability <= 0.95:
        print(f"  ✅ Param Stability {param_stability:.3f} (target 0.60-0.95)")
    else:
        print(f"  ⚠️ Param Stability {param_stability:.3f} (target 0.60-0.95)")
    
    # Consistency CV
    consistency_cv = overall['consistency_cv']
    if 0.15 <= consistency_cv <= 0.45:
        print(f"  ✅ Consistency CV {consistency_cv:.3f} (target 0.15-0.45)")
    else:
        print(f"  ⚠️ Consistency CV {consistency_cv:.3f} (target 0.15-0.45)")
    
    # Periods
    periods = len(results['periods'])
    if periods >= 10:
        print(f"  ✅ Periods {periods} (target 10+)")
    else:
        print(f"  ⚠️ Periods {periods} (target 10+)")
    
    # Period details
    print(f"\n📊 PERIOD BREAKDOWN:")
    profitable_periods = sum(1 for p in results['periods'] if p['oos_return'] > 0)
    print(f"  Profitable OOS periods: {profitable_periods}/{periods} ({profitable_periods/periods*100:.1f}%)")
    
    # Best/worst periods
    best_period = max(results['periods'], key=lambda p: p['oos_return'])
    worst_period = min(results['periods'], key=lambda p: p['oos_return'])
    
    print(f"\n  Best period: #{best_period['period']}")
    print(f"    Return: {best_period['oos_return']:.2f}%")
    print(f"    Params: EMA {best_period['best_params']['fast_ema']}/{best_period['best_params']['slow_ema']}")
    
    print(f"\n  Worst period: #{worst_period['period']}")
    print(f"    Return: {worst_period['oos_return']:.2f}%")
    print(f"    Params: EMA {worst_period['best_params']['fast_ema']}/{worst_period['best_params']['slow_ema']}")
    
    print(f"\n📁 Results saved to: {latest_result.name}")
    print("="*80)
    
    return True


def main():
    """Monitor WFO and show results when complete"""
    
    print("="*80)
    print("⏳ WAITING FOR WFO COMPLETION")
    print("="*80)
    print("Checking every 30 seconds...")
    print("Press Ctrl+C to stop monitoring")
    print()
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            completed, info = check_wfo_status()
            
            if completed:
                print(f"\n✅ WFO COMPLETED! (check #{check_count})")
                time.sleep(2)  # Wait for file to be written
                
                if show_results():
                    break
                else:
                    print("⏳ Waiting for results file to be written...")
            else:
                current_period, log_file = info
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if current_period > 0:
                    progress = (current_period / 22) * 100
                    remaining = 22 - current_period
                    
                    bar_length = 30
                    filled = int(bar_length * progress / 100)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    
                    print(f"[{timestamp}] Period {current_period}/22 [{bar}] {progress:.0f}% ({remaining} left)")
                else:
                    print(f"[{timestamp}] Initializing...")
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n\n⏸️ Monitoring stopped (WFO continues in background)")
        print("Run this script again to resume monitoring")


if __name__ == "__main__":
    main()

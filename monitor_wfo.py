"""
Monitor Walk-Forward Optimization Progress
"""

import sys
from pathlib import Path
from datetime import datetime
import time

def monitor_wfo():
    """Monitor WFO progress in real-time"""
    
    logs_dir = Path("logs")
    
    # Find latest WFO log
    wfo_logs = list(logs_dir.glob("wfo_full_run_*.log"))
    
    if not wfo_logs:
        print("❌ No WFO log files found")
        return
    
    latest_log = max(wfo_logs, key=lambda p: p.stat().st_mtime)
    
    print("="*80)
    print("📊 WALK-FORWARD OPTIMIZATION MONITOR")
    print("="*80)
    print(f"Log file: {latest_log.name}")
    print(f"Started: {datetime.fromtimestamp(latest_log.stat().st_mtime)}")
    print()
    
    # Read log
    with open(latest_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Extract key info
    current_period = None
    total_periods = 22
    periods_completed = []
    
    for line in lines:
        if "PERIOD" in line and "/" in line:
            # Extract period number
            parts = line.split("PERIOD")[1].split("/")
            if len(parts) >= 2:
                try:
                    period_num = int(parts[0].strip())
                    current_period = period_num
                except:
                    pass
        
        if "Progress:" in line:
            # Extract completion info
            if current_period and current_period not in periods_completed:
                periods_completed.append(current_period)
    
    # Calculate progress
    if current_period:
        progress_pct = (current_period / total_periods) * 100
        
        print(f"📈 Progress: {current_period}/{total_periods} periods ({progress_pct:.1f}%)")
        print(f"✅ Completed: {len(periods_completed)} periods")
        print(f"⏳ Remaining: {total_periods - current_period} periods")
        
        # ETA calculation
        elapsed_time = datetime.now() - datetime.fromtimestamp(latest_log.stat().st_mtime)
        elapsed_minutes = elapsed_time.total_seconds() / 60
        
        if current_period > 0:
            avg_time_per_period = elapsed_minutes / current_period
            remaining_time = avg_time_per_period * (total_periods - current_period)
            
            eta = datetime.now() + timedelta(minutes=remaining_time)
            
            print(f"\n⏱️ Timing:")
            print(f"  Elapsed: {elapsed_minutes:.1f} minutes ({elapsed_minutes/60:.1f} hours)")
            print(f"  Avg per period: {avg_time_per_period:.1f} minutes")
            print(f"  ETA: {eta.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Remaining: {remaining_time:.1f} minutes ({remaining_time/60:.1f} hours)")
        
        # Progress bar
        bar_length = 50
        filled = int(bar_length * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\n[{bar}] {progress_pct:.1f}%")
    
    # Show last 20 lines
    print(f"\n{'='*80}")
    print("📝 LAST 20 LOG LINES:")
    print(f"{'='*80}")
    
    for line in lines[-20:]:
        print(line.rstrip())
    
    print(f"\n{'='*80}")
    print("ℹ️ Run this script again to check progress")
    print(f"ℹ️ Or tail log: Get-Content {latest_log} -Tail 20 -Wait")
    print(f"{'='*80}")


if __name__ == "__main__":
    from datetime import timedelta
    monitor_wfo()

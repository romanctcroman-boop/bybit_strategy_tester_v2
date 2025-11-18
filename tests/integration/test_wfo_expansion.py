"""
Task 1.2: Expand Walk-Forward to 10-15 Cycles

Current: Only 2 profitable periods (insufficient)
Target: 10-15 reoptimization cycles (Perplexity recommendation)

Sprint 1, Week 1 (Oct 30 - Nov 5, 2025)
Estimate: 4 hours
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root (go up 2 levels from tests/integration/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit
from sqlalchemy import func
from loguru import logger
import pandas as pd
import numpy as np


def calculate_optimal_wfo_config(total_bars: int, target_cycles: int = 12):
    """
    Calculate optimal WFO configuration for available data
    
    Perplexity Recommendation:
    - Target: 10-15 reoptimization cycles
    - In-sample: ~30 days (enough for pattern detection)
    - Out-sample: ~7 days (realistic hold period)
    - Step: Same as out-sample (non-overlapping OOS)
    
    Formula:
    total_bars = in_sample + (step * (cycles - 1)) + out_sample
    
    Args:
        total_bars: Available bars in database
        target_cycles: Desired number of reoptimization cycles
    
    Returns:
        dict with in_sample, out_sample, step, actual_cycles, bars_used
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 CALCULATING OPTIMAL WFO CONFIGURATION")
    logger.info(f"{'='*80}")
    logger.info(f"Available bars: {total_bars:,}")
    logger.info(f"Target cycles: {target_cycles}")
    
    # Try different configurations
    configs = []
    
    # Config 1: Perplexity recommendation (8000 IS / 2000 OOS / 2000 step)
    in_sample_1 = 8000  # ~27 days (8000 * 5min / 60 / 24)
    out_sample_1 = 2000  # ~7 days
    step_1 = 2000
    bars_used_1 = in_sample_1 + (step_1 * (target_cycles - 1)) + out_sample_1
    actual_cycles_1 = ((total_bars - in_sample_1 - out_sample_1) // step_1) + 1
    
    configs.append({
        'name': 'Perplexity Recommendation',
        'in_sample': in_sample_1,
        'out_sample': out_sample_1,
        'step': step_1,
        'target_cycles': target_cycles,
        'actual_cycles': actual_cycles_1,
        'bars_used': bars_used_1,
        'bars_unused': total_bars - bars_used_1,
        'valid': bars_used_1 <= total_bars,
        'in_sample_days': in_sample_1 * 5 / 60 / 24,
        'out_sample_days': out_sample_1 * 5 / 60 / 24,
    })
    
    # Config 2: More aggressive (6000 IS / 2000 OOS / 1500 step)
    in_sample_2 = 6000  # ~21 days
    out_sample_2 = 2000  # ~7 days
    step_2 = 1500
    bars_used_2 = in_sample_2 + (step_2 * (target_cycles - 1)) + out_sample_2
    actual_cycles_2 = ((total_bars - in_sample_2 - out_sample_2) // step_2) + 1
    
    configs.append({
        'name': 'Aggressive (More Cycles)',
        'in_sample': in_sample_2,
        'out_sample': out_sample_2,
        'step': step_2,
        'target_cycles': target_cycles,
        'actual_cycles': actual_cycles_2,
        'bars_used': bars_used_2,
        'bars_unused': total_bars - bars_used_2,
        'valid': bars_used_2 <= total_bars,
        'in_sample_days': in_sample_2 * 5 / 60 / 24,
        'out_sample_days': out_sample_2 * 5 / 60 / 24,
    })
    
    # Config 3: Conservative (10000 IS / 3000 OOS / 3000 step)
    in_sample_3 = 10000  # ~35 days
    out_sample_3 = 3000  # ~10 days
    step_3 = 3000
    bars_used_3 = in_sample_3 + (step_3 * (target_cycles - 1)) + out_sample_3
    actual_cycles_3 = ((total_bars - in_sample_3 - out_sample_3) // step_3) + 1
    
    configs.append({
        'name': 'Conservative (More Data)',
        'in_sample': in_sample_3,
        'out_sample': out_sample_3,
        'step': step_3,
        'target_cycles': target_cycles,
        'actual_cycles': actual_cycles_3,
        'bars_used': bars_used_3,
        'bars_unused': total_bars - bars_used_3,
        'valid': bars_used_3 <= total_bars,
        'in_sample_days': in_sample_3 * 5 / 60 / 24,
        'out_sample_days': out_sample_3 * 5 / 60 / 24,
    })
    
    # Print comparison
    logger.info(f"\n{'='*80}")
    logger.info(f"📋 CONFIGURATION COMPARISON")
    logger.info(f"{'='*80}")
    
    for i, config in enumerate(configs, 1):
        logger.info(f"\n{i}. {config['name']}")
        logger.info(f"   In-sample: {config['in_sample']:,} bars (~{config['in_sample_days']:.1f} days)")
        logger.info(f"   Out-sample: {config['out_sample']:,} bars (~{config['out_sample_days']:.1f} days)")
        logger.info(f"   Step: {config['step']:,} bars")
        logger.info(f"   Target cycles: {config['target_cycles']}")
        logger.info(f"   Actual cycles: {config['actual_cycles']}")
        logger.info(f"   Bars used: {config['bars_used']:,} / {total_bars:,}")
        logger.info(f"   Bars unused: {config['bars_unused']:,}")
        logger.info(f"   Valid: {'✅ YES' if config['valid'] else '❌ NO'}")
    
    # Select best config (Perplexity recommendation if valid)
    selected = configs[0] if configs[0]['valid'] else None
    
    if not selected:
        logger.warning("Perplexity config invalid, trying alternatives...")
        for config in configs[1:]:
            if config['valid']:
                selected = config
                break
    
    if selected:
        logger.success(f"\n✅ SELECTED: {selected['name']}")
        logger.info(f"   {selected['actual_cycles']} cycles with {selected['bars_unused']:,} bars unused")
        return selected
    else:
        logger.error("❌ No valid configuration found!")
        return None


def validate_wfo_configuration(config: dict, total_bars: int):
    """
    Validate Walk-Forward Configuration (simulation, not actual run)
    
    This function validates the configuration WITHOUT running full optimization
    (which would take 4+ hours). It simulates the walk-forward periods and 
    estimates execution time.
    
    Args:
        config: Configuration dict from calculate_optimal_wfo_config
        total_bars: Total available bars
    
    Returns:
        dict with validation results
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🔬 VALIDATING WFO CONFIGURATION (Simulation)")
    logger.info(f"{'='*80}")
    
    in_sample = config['in_sample']
    out_sample = config['out_sample']
    step = config['step']
    
    # Simulate walk-forward periods
    periods = []
    start_idx = 0
    
    while start_idx + in_sample + out_sample <= total_bars:
        is_start = start_idx
        is_end = start_idx + in_sample
        oos_start = is_end
        oos_end = is_end + out_sample
        
        periods.append({
            'period': len(periods) + 1,
            'is_start': is_start,
            'is_end': is_end,
            'oos_start': oos_start,
            'oos_end': oos_end,
            'is_bars': in_sample,
            'oos_bars': out_sample,
        })
        
        start_idx += step
    
    logger.info(f"\n📊 SIMULATION RESULTS:")
    logger.info(f"   Total periods: {len(periods)}")
    logger.info(f"   First period: bars {periods[0]['is_start']}-{periods[0]['oos_end']}")
    logger.info(f"   Last period: bars {periods[-1]['is_start']}-{periods[-1]['oos_end']}")
    logger.info(f"   Coverage: {periods[-1]['oos_end']:,} / {total_bars:,} bars ({periods[-1]['oos_end']/total_bars*100:.1f}%)")
    
    # Estimate execution time
    # Assume: 1 period = 30 seconds (conservative)
    # With 25 parameter combinations (5x5 grid)
    param_combinations = 25
    seconds_per_period = 30
    estimated_duration = len(periods) * param_combinations * seconds_per_period / 60  # minutes
    
    logger.info(f"\n⏱️ ESTIMATED EXECUTION TIME:")
    logger.info(f"   Parameter combinations: {param_combinations}")
    logger.info(f"   Seconds per period: {seconds_per_period}")
    logger.info(f"   Total time: ~{estimated_duration:.0f} minutes (~{estimated_duration/60:.1f} hours)")
    
    # Validate against Perplexity benchmarks
    logger.info(f"\n✅ PERPLEXITY BENCHMARKS:")
    
    # Periods: 10+ is sufficient
    if len(periods) >= 10:
        logger.success(f"   ✅ Periods {len(periods)} (target 10+)")
        periods_valid = True
    else:
        logger.warning(f"   ⚠️ Periods {len(periods)} (target 10+)")
        periods_valid = False
    
    # In-sample duration: 20-40 days is good
    is_days = in_sample * 5 / 60 / 24
    if 20 <= is_days <= 40:
        logger.success(f"   ✅ In-sample {is_days:.1f} days (target 20-40)")
        is_valid = True
    else:
        logger.warning(f"   ⚠️ In-sample {is_days:.1f} days (target 20-40)")
        is_valid = False
    
    # Out-sample duration: 5-15 days is good
    oos_days = out_sample * 5 / 60 / 24
    if 5 <= oos_days <= 15:
        logger.success(f"   ✅ Out-sample {oos_days:.1f} days (target 5-15)")
        oos_valid = True
    else:
        logger.warning(f"   ⚠️ Out-sample {oos_days:.1f} days (target 5-15)")
        oos_valid = False
    
    # Step size: Should match out-sample for non-overlapping OOS
    if step == out_sample:
        logger.success(f"   ✅ Step = Out-sample (non-overlapping OOS)")
        step_valid = True
    else:
        logger.warning(f"   ⚠️ Step ≠ Out-sample (overlapping OOS)")
        step_valid = False
    
    # Return validation
    return {
        'config': config,
        'periods': periods,
        'period_count': len(periods),
        'estimated_duration_hours': estimated_duration / 60,
        'is_days': is_days,
        'oos_days': oos_days,
        'valid': periods_valid and is_valid and oos_valid and step_valid,
        'checks': {
            'periods': periods_valid,
            'in_sample': is_valid,
            'out_sample': oos_valid,
            'step': step_valid,
        }
    }


def main():
    """
    Main execution for Task 1.2: Expand Walk-Forward to 10-15 Cycles
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🚀 TASK 1.2: EXPAND WALK-FORWARD TO 10-15 CYCLES")
    logger.info(f"{'='*80}")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Sprint: Week 1 (Oct 30 - Nov 5, 2025)")
    logger.info(f"Estimate: 4 hours")
    
    # Step 1: Check available data
    db = SessionLocal()
    try:
        total_bars = db.query(func.count(BybitKlineAudit.id)).filter(
            BybitKlineAudit.symbol == 'BTCUSDT',
            BybitKlineAudit.interval == '5'
        ).scalar()
        
        logger.info(f"\nAvailable data: {total_bars:,} bars")
        
        if total_bars < 10000:
            logger.error(f"❌ Insufficient data ({total_bars:,} < 10,000 bars)")
            logger.info("   Need at least 10,000 bars for 10+ cycles")
            return False
        
    finally:
        db.close()
    
    # Step 2: Calculate optimal configuration
    config = calculate_optimal_wfo_config(total_bars, target_cycles=12)
    
    if not config:
        logger.error("❌ Could not find valid WFO configuration")
        return False
    
    # Step 3: Validate configuration (simulation only, not full run)
    validation_results = validate_wfo_configuration(config, total_bars)
    
    if not validation_results:
        logger.error("❌ WFO validation failed")
        return False
    
    # Step 4: Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 TASK 1.2 SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Configuration: {config['name']}")
    logger.info(f"Cycles: {validation_results['period_count']} (target 10-15)")
    logger.info(f"In-sample: {validation_results['is_days']:.1f} days (target 20-40)")
    logger.info(f"Out-sample: {validation_results['oos_days']:.1f} days (target 5-15)")
    logger.info(f"Estimated duration: ~{validation_results['estimated_duration_hours']:.1f} hours")
    
    logger.info(f"\n✅ VALIDATION CHECKS:")
    for check_name, passed in validation_results['checks'].items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"   {status} - {check_name}")
    
    if validation_results['valid']:
        logger.success(f"\n✅ TASK 1.2 COMPLETE - Configuration VALID!")
        logger.info("   Ready for full Walk-Forward Optimization run")
        logger.info("   Next: Task 1.3 (Out-of-sample validation)")
        logger.info("   Next: Task 1.4 (Parameter sensitivity)")
        return True
    else:
        logger.warning(f"\n⚠️ TASK 1.2 PARTIAL - Some checks failed")
        logger.info("   Adjust configuration and re-run")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

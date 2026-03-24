Verify TradingView parity for a backtest engine file or a specific metric.

Usage: /parity-check [file_or_description]

Examples:
  /parity-check                                          — check all recent engine changes
  /parity-check backend/backtesting/engines/fallback_engine_v4.py
  /parity-check backend/core/metrics_calculator.py
  /parity-check commission calculation
  /parity-check SL/TP logic

Steps:
1. If no file specified, look at recently modified engine/metrics files from git status context.

2. Read the target file(s). Focus on:
   - Commission calculation (must be: trade_value × 0.0007, NOT leveraged_value × 0.0007)
   - SL/TP trigger logic (bar magnifier path vs. heuristic path)
   - Entry/exit price resolution (open of next bar, not signal bar)
   - Position sizing (initial_capital × position_size, then × leverage)
   - PnL formula: (exit_price - entry_price) / entry_price × position_value - commission

3. Run the parity checklist:

**Commission parity (CRITICAL):**
- [ ] commission_value == 0.0007 everywhere in this file
- [ ] commission computed on margin (trade_value), not on leveraged_position_value
  Correct:   commission = trade_value × 0.0007
  Wrong:     commission = trade_value × leverage × 0.0007
- [ ] grep: `grep -n commission <file>` — every occurrence uses 0.0007

**Engine execution parity:**
- [ ] Entries execute at next bar open (not signal bar close)
- [ ] SL/TP checked intrabar when use_bar_magnifier=True
- [ ] close_rule=ALL closes all pyramided positions simultaneously
- [ ] direction filter applied BEFORE signal routing (not after)

**Metrics parity (if metrics_calculator.py touched):**
- [ ] max_drawdown reported in percent (17.29 = 17.29%), not decimal
- [ ] sharpe_ratio uses risk_free_rate from config (default 0.02)
- [ ] win_rate = winning_trades / total_trades × 100 (percent)
- [ ] profit_factor = gross_profit / gross_loss (returns inf if gross_loss == 0)
- [ ] All 166 metrics computed — none silently dropped

**Known TV divergence sources (not bugs — document if present):**
- RSI Wilder smoothing warmup (±4 trades vs TV due to 500-bar warmup limit)
- Bar magnifier heuristic O-HL path vs TV's exact tick replay
- Funding rate on linear vs spot price difference

4. Check for regressions against parity test suite:
   File: tests/backend/backtesting/test_strategy_builder_parity.py
   Command to suggest: pytest tests/backend/backtesting/test_strategy_builder_parity.py -v

5. Output the result:

```
## Parity Check: [file(s)]

### Commission ✅ PASS / ❌ FAIL
[findings]

### Execution Logic ✅ PASS / ❌ FAIL / ⚠️ REVIEW
[findings]

### Metrics ✅ PASS / ❌ FAIL
[findings]

### Known Acceptable Divergences
[list]

### Verdict: PARITY SAFE / PARITY RISK — [what to fix]
```

DO NOT:
- Change commission_value from 0.0007 to "fix" parity — it IS the correct value
- Suggest switching to a deprecated engine (V2/V3) to match old results
- Ignore warnings — every warning in the API response is a parity signal

Start a structured debug session for a bug or unexpected behaviour in Bybit Strategy Tester v2.

Usage: /debug [description of the problem]

Example: /debug Short trades not appearing when direction=short in strategy builder

Steps:
1. Ask the user to describe the symptom if not provided:
   - What did you expect?
   - What actually happened?
   - Where did you see this? (API response / frontend / logs / test failure)
   - Any error messages or stack traces?

2. Identify the likely layer (use the data flow as a guide):
   ```
   Frontend (strategy_builder.js)
     → API (routers/strategy_builder.py)
     → Adapter (strategy_builder_adapter.py) — port alias, signal routing
     → Engine (engine.py) — direction filter, SL/TP
     → Metrics (metrics_calculator.py)
   ```

3. For each layer, check the most common failure modes:
   - **No trades / wrong direction**: Check `warnings` in API response; check `[DIRECTION_MISMATCH]` in engine logs; check port aliases in adapter
   - **Wrong PnL**: Verify `commission_rate=0.0007`; check leverage multiplier
   - **Signal not delivered**: Check port alias mapping (`long↔bullish`, `short↔bearish`, `output↔value`, `result↔signal`)
   - **Frontend wire red/dashed**: Direction mismatch — source port conflicts with direction setting
   - **Test failure**: Read the full traceback; check fixtures in conftest.py

4. Read the relevant files to understand current state before proposing a fix

5. Propose a minimal targeted fix. Do NOT refactor unrelated code.

6. If the fix changes critical variables (`commission_rate`, `strategy_params`, `initial_capital`, port aliases), flag it explicitly.

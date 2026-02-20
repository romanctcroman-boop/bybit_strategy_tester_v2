Write tests for a specified function, module, or feature using the project's testing conventions.

Usage: /tdd [module or function to test]

Example: /tdd backend/backtesting/strategy_builder_adapter.py
Example: /tdd the new EMA cross strategy
Example: /tdd direction mismatch warning in engine

Steps:
1. Read the target file/function to understand its behaviour
2. Identify test categories needed:
   - Happy path (expected input → expected output)
   - Edge cases (empty data, None, zero signals, all-short signals with long direction)
   - Error cases (invalid params, missing keys)
   - TradingView parity (if backtest engine code)

3. Write tests following project conventions:
   - File: `tests/[category]/test_[module_name].py`
   - Class: `TestClassName`
   - Function: `test_[function]_[scenario]`
   - Use `sample_ohlcv`, `backtest_config` fixtures from conftest.py
   - Use `@pytest.mark.asyncio` for async functions
   - Mock Bybit API with `unittest.mock.AsyncMock` — never call real API
   - Use `@pytest.mark.parametrize` for multiple input variants

4. For AI agent tests, follow the pattern in `tests/ai_agents/test_divergence_block_ai_agents.py`:
   - Each test class covers one logical grouping
   - Use descriptive docstrings in Russian (matching project convention)

5. Show the test file content, then remind the user to run:
   ```bash
   pytest [test_file_path] -v
   pytest [test_file_path] --cov=[module_path] --cov-report=term-missing
   ```

Coverage targets:
- Engine/metrics code: 95%
- Services/strategies: 85%
- Everything else: 80%

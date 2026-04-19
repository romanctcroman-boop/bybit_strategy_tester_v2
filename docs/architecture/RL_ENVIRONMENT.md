# RL Trading Environment (Gymnasium)

**Файл:** `backend/ml/rl/trading_env.py`

## API

Совместим с Gymnasium (и legacy Gym):

```python
from backend.ml.rl.trading_env import TradingEnv, TradingConfig, register_trading_env

register_trading_env()
import gymnasium as gym
env = gym.make("TradingEnv-v1", df=ohlcv_df)
# или
env = TradingEnv(df=ohlcv_df, config=TradingConfig(), reward_function="sharpe")

obs, info = env.reset(seed=42)
done = False
while not done:
    action = agent.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    done = terminated or truncated
```

## Action Space

`Discrete(4)`: HOLD=0, BUY=1, SELL=2, CLOSE=3

## Reward Functions

| Имя | Описание |
|-----|----------|
| pnl | Изменение equity / initial_balance |
| log_return | log(equity / prev_equity) |
| sharpe | Скользящий Sharpe по последним 100 шагам |
| sortino | Скользящий Sortino (штраф только за просадки) |
| calmar | return / max_drawdown |
| drawdown_penalty | pnl − 2×max_drawdown |

## Конфигурация

- `initial_balance`, `max_position_size`, `commission_rate`, `slippage`
- `lookback_window` — размер окна OHLCV в observation
- `use_normalized_observations` — нормализация цен
- `include_position_info`, `include_pnl_info` — доп. признаки в observation

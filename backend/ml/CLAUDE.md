# backend/ml/ — Контекст модуля

> **Статус:** Optional — все ML зависимости опциональны, graceful fallback при ImportError.

## Структура

```
backend/ml/
├── regime_detection.py       (501 lines)  # Market regime detection
├── rl_trading_agent.py       (820 lines)  # DQN + PPO trading agents
├── ai_backtest_executor.py                # ML-driven backtest execution
├── ai_feature_engineer.py                 # Feature extraction
├── mlflow_adapter.py                      # MLflow experiment tracking
├── news_nlp_analyzer.py                   # News sentiment NLP
└── rl/
    ├── trading_env.py        (597 lines)  # Gymnasium RL environment (TradingEnv-v1)
    ├── rewards.py                          # Reward functions
    └── wrapper.py                          # Env wrappers

backend/rl/                               # Standalone RL (дублирует ml/rl/)
├── trading_env.py
└── rewards.py, wrapper.py
```

## Regime Detection

**3 алгоритма:**
- `KMeans` — быстрый, simple clustering
- `GaussianMixture` — probabilistic (опциональный: `sklearn`)
- `HiddenMarkovModel` — temporal transitions (опциональный: `hmmlearn`)

**6 режимов:**
```python
class MarketRegime(Enum):
    BULL_LOW_VOL  = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL  = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    SIDEWAYS      = "sideways"
    UNKNOWN       = "unknown"
```

**Использование:**
```python
detector = RegimeDetector(algorithm="kmeans")  # или "gmm", "hmm"
regime = detector.detect(ohlcv_df)
# → MarketRegime.BULL_LOW_VOL
```

## RL Trading Agent

**Алгоритмы:**
- **DQN** — Deep Q-Network, experience replay + target networks
- **PPO** — Proximal Policy Optimization, policy gradient с clipping

**Actions:** `HOLD(0)`, `BUY(1)`, `SELL(2)`, `CLOSE(3)`

**Reward functions:** `pnl`, `log_return`, `sharpe`, `sortino`, `calmar`, `drawdown_penalty`

## Trading Environment (Gymnasium)

```python
# gymnasium.make("TradingEnv-v1")

class TradingConfig:
    initial_balance = 10000.0
    commission_rate = 0.0007    # ⚠️ ОБЯЗАТЕЛЬНО совпадает с TradingView parity
    max_position_size = 1.0
    leverage = 1.0
    slippage = 0.0001
```

**Регистрация среды:**
```python
# ml/rl/trading_env.py
gymnasium.register(id="TradingEnv-v1", entry_point="backend.ml.rl.trading_env:TradingEnv")
```

## Опциональные зависимости

```python
SKLEARN_AVAILABLE   # sklearn — regime detection (GMM, KMeans)
HMM_AVAILABLE       # hmmlearn — HMM режимы
GYM_AVAILABLE       # gymnasium или gym — RL environment
RAY_AVAILABLE       # ray — distributed computing
MLFLOW_AVAILABLE    # mlflow — experiment tracking
```

**Паттерн импорта:**
```python
try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    # Fallback на KMeans-без-sklearn или UNKNOWN режим
```

## RegimeClassifierNode (в AI Pipeline)

Детерминированный классификатор в `trading_strategy_graph.py`:
- Использует ADX + ATR для 5-категорийной таксономии
- Запускается после `analyze_market`
- НЕ требует sklearn — полностью детерминированный

**5 категорий RegimeClassifierNode:**
`trending_bull`, `trending_bear`, `ranging`, `volatile`, `unknown`

## Residual issues (known, не баги)

- `ai_backtest_executor.py:170` — использует `commission_rate=0.001` (legacy ML path, не core)
- RSI Wilder smoothing: ±4 trades из-за 500-bar warmup limit vs TradingView
- ML зависимости НЕ входят в `requirements.txt` — устанавливать через `requirements-ml.txt`

## Тесты

```bash
pytest tests/backend/ -k "ml or regime or rl" -v
# ML тесты пропускают если зависимости недоступны (@pytest.mark.skipif)
```

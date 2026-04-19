# 🧱 P1-12: Strategy Builder Advanced Blocks — План

**Дата:** 2026-02-26
**Статус:** ⏳ В работе
**Оценка:** 3 дня (24 часа)

---

## 🎯 Цель

Расширить библиотеку блоков Strategy Builder:
- Machine Learning блоки (LSTM, ML predictions)
- Sentiment Analysis (Twitter, Reddit, News)
- Order Flow Imbalance
- Volume Profile
- Market Microstructure

---

## 🏗️ Архитектура

```
backend/backtesting/advanced_blocks/
├── __init__.py
├── ml_blocks.py            # LSTM, ML predictions
├── sentiment_blocks.py     # Sentiment analysis
├── order_flow.py           # Order flow imbalance
├── volume_profile.py       # Volume profile analysis
├── market_microstructure.py # Market microstructure
└── tests/
    ├── test_ml_blocks.py
    ├── test_sentiment.py
    ├── test_order_flow.py
    └── test_volume_profile.py
```

---

## 📝 План работ

### День 1: ML Blocks (8 часов)
- [ ] LSTM prediction block
- [ ] ML signal block
- [ ] Feature engineering blocks
- [ ] Model training block

### День 2: Sentiment & Order Flow (8 часов)
- [ ] Sentiment analysis block
- [ ] Order flow imbalance
- [ ] Volume profile blocks

### День 3: Integration (8 часов)
- [ ] Market microstructure blocks
- [ ] Интеграция в Strategy Builder UI
- [ ] Тесты
- [ ] Документация

---

## 🔧 Зависимости

### requirements-advanced.txt

```txt
# Machine Learning
torch>=2.0.0
scikit-learn>=1.3.0

# Sentiment
textblob>=0.17.0
vaderSentiment>=3.3.0

# Order Flow
numpy>=1.24.0
pandas>=2.0.0
```

---

## 📊 Ожидаемые результаты

### ML Blocks

**Блоки:**
- LSTM Prediction
- ML Signal (Random Forest, XGBoost)
- Feature Engineering
- Model Training

**API:**
- `POST /api/v1/ml/train`
- `POST /api/v1/ml/predict`

### Sentiment Blocks

**Блоки:**
- Twitter Sentiment
- Reddit Sentiment
- News Sentiment
- Composite Sentiment

### Order Flow Blocks

**Блоки:**
- Order Flow Imbalance
- Cumulative Delta
- Volume Imbalance
- Trade Flow

---

## ✅ Критерии приёмки

- [ ] ML блоки работают
- [ ] Sentiment analysis реализован
- [ ] Order flow блоки работают
- [ ] Volume profile работает
- [ ] Интеграция в Strategy Builder
- [ ] Тесты проходят (>80%)

---

*План создан: 2026-02-26*

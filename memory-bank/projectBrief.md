# Project Brief — Bybit Strategy Tester v2

## Что это
AI-powered платформа бэктестинга торговых стратегий для биржи Bybit.
Визуальный блочный конструктор стратегий (Strategy Builder) + мультиагентный AI-пайплайн.

## Цели
1. Воспроизводимые бэктесты с паритетом к TradingView (±0.1% net profit, 0 trade diff)
2. Блочный конструктор стратегий → без кода
3. Параметрическая оптимизация (Optuna, TPE/CMA-ES)
4. AI-помощники для генерации и анализа стратегий

## Ключевой инвариант
**commission_value = 0.0007 (0.07%)** — основа TradingView parity. НЕ МЕНЯТЬ.

## Точка входа
`python main.py server` → http://localhost:8000
API docs: http://localhost:8000/docs

## Репозиторий
- Рабочая ветка: `main`
- PR-таргет: `fresh-main`
- Рабочая директория: `D:\bybit_strategy_tester_v2`

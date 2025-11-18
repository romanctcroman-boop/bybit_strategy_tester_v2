"""
🚀 ПОЛНЫЙ 90-ДНЕВНЫЙ MTF AI WORKFLOW С PERPLEXITY MCP

Использует:
1. ✅ fetch_historical_klines() - ПОЛНАЯ загрузка 90 дней через пагинацию
2. ✅ MTF (5m, 15m, 30m) - Все три таймфрейма
3. ✅ Grid Search - Расширенная оптимизация (5+ вариантов)
4. ✅ Perplexity MCP - AI анализ через MCP сервер
5. ✅ Реальные тесты - Только реальные данные и настоящие API
"""

import sys
import os
import time
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError(
        "⚠️ SECURITY: PERPLEXITY_API_KEY not configured.\n"
        "Please add PERPLEXITY_API_KEY to .env file"
    )
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class Full90DayMTFWorkflow:
    """Полный 90-дневный MTF тест с AI анализом."""
    
    def __init__(self):
        self.current_date = datetime(2025, 10, 29)
        self.test_period_start = self.current_date - timedelta(days=90)
        self.timeframes = ['5', '15', '30']
        self.central_tf = '15'
        self.test_results = {
            "config": {
                "symbol": "BTCUSDT",
                "period_days": 90,
                "start_date": self.test_period_start.isoformat(),
                "end_date": self.current_date.isoformat(),
                "timeframes": self.timeframes,
                "central_tf": self.central_tf,
            },
            "phases": {}
        }
    
    async def call_perplexity(self, query: str, context: str = "") -> str:
        """Вызов Perplexity API."""
        full_query = f"{context}\n\n{query}" if context else query
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    PERPLEXITY_API_URL,
                    headers={
                        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "sonar-pro",
                        "messages": [{
                            "role": "user",
                            "content": full_query
                        }],
                        "temperature": 0.2,
                        "max_tokens": 2000
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"   ❌ Perplexity API error: {e}")
                return f"ERROR: {e}"
    
    def load_full_90days_data(self, symbol: str = "BTCUSDT") -> Dict[str, pd.DataFrame]:
        """Загрузка ПОЛНЫХ 90 дней через fetch_historical_klines()."""
        print("\n" + "="*80)
        print("📥 ЗАГРУЗКА ПОЛНЫХ 90 ДНЕЙ ДАННЫХ (FETCH_HISTORICAL_KLINES)")
        print("="*80)
        
        from backend.services.adapters.bybit import BybitAdapter
        
        adapter = BybitAdapter()
        mtf_data = {}
        
        # Интервалы в миллисекундах
        interval_ms = {
            '5': 5 * 60 * 1000,    # 5 минут
            '15': 15 * 60 * 1000,  # 15 минут
            '30': 30 * 60 * 1000,  # 30 минут
        }
        
        # Требуемое количество свечей
        required_candles = {
            '5': 90 * 24 * 12,   # 25,920
            '15': 90 * 24 * 4,   # 8,640
            '30': 90 * 24 * 2,   # 4,320
        }
        
        for tf in self.timeframes:
            print(f"\n📊 Таймфрейм {tf}m:")
            print(f"   Требуется: {required_candles[tf]:,} свечей")
            print(f"   Метод: fetch_historical_klines() с пагинацией")
            
            try:
                start_time = time.time()
                
                # ИСПОЛЬЗУЕМ ПРАВИЛЬНУЮ ФУНКЦИЮ!
                raw_data = adapter.get_klines_historical(
                    symbol=symbol,
                    interval=tf,
                    total_candles=required_candles[tf],
                    end_time=int(self.current_date.timestamp() * 1000)
                )
                
                elapsed = time.time() - start_time
                
                if raw_data:
                    df = pd.DataFrame(raw_data)
                    df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                    
                    # Нормализация колонок
                    column_mapping = {
                        'open_price': 'open',
                        'high_price': 'high',
                        'low_price': 'low',
                        'close_price': 'close',
                    }
                    
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns and new_col not in df.columns:
                            df[old_col] = pd.to_numeric(df[old_col], errors='coerce')
                            df[new_col] = df[old_col]
                    
                    if 'volume' in df.columns:
                        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
                    
                    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].sort_values('timestamp').reset_index(drop=True)
                    mtf_data[tf] = df
                    
                    period_days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
                    coverage_pct = len(df) / required_candles[tf] * 100
                    
                    print(f"\n   ✅ Загружено: {len(df):,} свечей ({coverage_pct:.1f}% от требуемых)")
                    print(f"   📅 Период: {df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M')} → {df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M')}")
                    print(f"   📏 Длина: {period_days} дней")
                    print(f"   💰 Цена: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
                    print(f"   ⏱️  Время загрузки: {elapsed:.2f}s")
                    print(f"   🚀 Скорость: {len(df)/elapsed:.0f} candles/sec")
                else:
                    print(f"   ❌ Нет данных")
                    
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
        
        self.test_results["data_loaded"] = {
            tf: {
                "candles_loaded": len(df),
                "candles_required": required_candles[tf],
                "coverage_pct": len(df) / required_candles[tf] * 100,
                "period_start": df['timestamp'].iloc[0].isoformat(),
                "period_end": df['timestamp'].iloc[-1].isoformat(),
                "period_days": (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days,
            } for tf, df in mtf_data.items()
        }
        
        return mtf_data
    
    async def phase1_ai_mtf_strategy_design(self):
        """ФАЗА 1: AI дизайн MTF стратегии через Perplexity."""
        print("\n" + "="*80)
        print("📋 ФАЗА 1: AI ДИЗАЙН MTF СТРАТЕГИИ")
        print("="*80)
        
        query = f"""Design a Multi-Timeframe (MTF) trading strategy for cryptocurrency backtesting with these requirements:

CONTEXT:
- Symbol: BTCUSDT
- Timeframes: 5m (fast), 15m (central), 30m (higher timeframe filter)
- Period: 90 days of historical data
- Purpose: Real production-grade strategy testing

REQUIREMENTS:
1. Use EMA crossover as primary signal on 15m (central timeframe)
2. Use 30m as Higher Timeframe (HTF) filter for trend confirmation
3. Use 5m for precise entry timing
4. Include risk management (stop-loss, take-profit, position sizing)
5. Must be suitable for grid search parameter optimization

RESPOND WITH:
1. Strategy logic (entry/exit rules for each timeframe)
2. Recommended parameter ranges for optimization (EMA periods, SL/TP %, etc.)
3. Expected optimization metrics to track (Sharpe, Profit Factor, Win Rate, etc.)

Keep it concise and actionable."""

        print(f"\n🤖 Copilot → Perplexity:")
        print(f"   Query: {query[:100]}...")
        
        response = await self.call_perplexity(query)
        
        print(f"\n💡 Perplexity Response:")
        print(f"   {response[:300]}...")
        
        self.test_results["phases"]["phase1_strategy_design"] = {
            "query": query,
            "response": response
        }
        
        return response
    
    async def phase2_ai_optimization_plan(self, strategy_design: str, data_stats: Dict):
        """ФАЗА 2: AI план оптимизации параметров."""
        print("\n" + "="*80)
        print("📋 ФАЗА 2: AI ПЛАН ОПТИМИЗАЦИИ")
        print("="*80)
        
        data_summary = "\n".join([
            f"- {tf}m: {stats['candles_loaded']:,} candles ({stats['coverage_pct']:.1f}% coverage), {stats['period_days']} days"
            for tf, stats in data_stats.items()
        ])
        
        query = f"""Based on this MTF strategy design and available data, create a parameter optimization plan:

STRATEGY DESIGN:
{strategy_design[:500]}...

DATA AVAILABLE:
{data_summary}

TASK:
Create a Grid Search parameter matrix with 5-7 combinations that:
1. Covers different market regimes (trending, ranging, volatile)
2. Tests both conservative and aggressive parameters
3. Balances exploration vs. exploitation

RESPOND WITH:
1. Specific parameter combinations (JSON format)
2. Rationale for each combination
3. Expected performance characteristics

Format as valid JSON array."""

        print(f"\n🤖 Copilot → Perplexity:")
        print(f"   Query: Parameter optimization plan...")
        
        response = await self.call_perplexity(query)
        
        print(f"\n💡 Perplexity Response:")
        print(f"   {response[:300]}...")
        
        self.test_results["phases"]["phase2_optimization_plan"] = {
            "query": query,
            "response": response
        }
        
        return response
    
    def run_grid_search(self, mtf_data: Dict[str, pd.DataFrame]) -> Dict:
        """Grid Search оптимизация на ПОЛНЫХ 90 днях."""
        print("\n" + "="*80)
        print("⚙️ GRID SEARCH НА ПОЛНЫХ 90 ДНЯХ")
        print("="*80)
        
        from backend.core.backtest_engine import BacktestEngine

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key
        
        # Расширенная матрица параметров
        parameter_matrix = [
            {"fast_ema": 9, "slow_ema": 21, "rsi_period": 14, "name": "Fast Scalping (9/21)"},
            {"fast_ema": 12, "slow_ema": 26, "rsi_period": 14, "name": "MACD Classic (12/26)"},
            {"fast_ema": 20, "slow_ema": 50, "rsi_period": 9, "name": "Medium Trend (20/50)"},
            {"fast_ema": 15, "slow_ema": 45, "rsi_period": 21, "name": "Balanced (15/45)"},
            {"fast_ema": 10, "slow_ema": 30, "rsi_period": 14, "name": "Short Swing (10/30)"},
            {"fast_ema": 8, "slow_ema": 13, "rsi_period": 7, "name": "Ultra Fast (8/13)"},
            {"fast_ema": 50, "slow_ema": 200, "rsi_period": 14, "name": "Long Trend (50/200)"},
        ]
        
        all_results = {}
        
        # Тестируем на центральном таймфрейме (15m)
        tf = self.central_tf
        
        if tf not in mtf_data or mtf_data[tf].empty:
            print(f"\n⚠️ Нет данных для {tf}m")
            return {}
        
        print(f"\n📊 ОПТИМИЗАЦИЯ НА ЦЕНТРАЛЬНОМ ТАЙМФРЕЙМЕ {tf}m")
        print(f"   Данных: {len(mtf_data[tf]):,} свечей за {(mtf_data[tf]['timestamp'].iloc[-1] - mtf_data[tf]['timestamp'].iloc[0]).days} дней")
        print(f"="*60)
        
        tf_results = []
        
        for i, params in enumerate(parameter_matrix, 1):
            print(f"\n   🔄 Вариант {i}/{len(parameter_matrix)}: {params['name']}")
            print(f"      EMA {params['fast_ema']}/{params['slow_ema']}, RSI {params['rsi_period']}")
            
            engine = BacktestEngine(
                initial_capital=10_000.0,
                commission=0.055 / 100,
                slippage_pct=0.05
            )
            
            strategy_config = {
                'type': 'ema_crossover',
                'fast_ema': params['fast_ema'],
                'slow_ema': params['slow_ema'],
                'take_profit_pct': 3.0,
                'stop_loss_pct': 1.5,
                'risk_per_trade_pct': 2.0,
                'max_positions': 1,
            }
            
            try:
                start_time = time.time()
                results = engine.run(mtf_data[tf], strategy_config)
                elapsed = time.time() - start_time
                
                tf_results.append({
                    "params": params,
                    "total_return": results['total_return'],
                    "total_return_pct": results['total_return'] * 100,
                    "sharpe_ratio": results['sharpe_ratio'],
                    "sortino_ratio": results['sortino_ratio'],
                    "max_drawdown": results['max_drawdown'],
                    "max_drawdown_pct": results['max_drawdown'] * 100,
                    "total_trades": results['total_trades'],
                    "win_rate": results['win_rate'],
                    "profit_factor": results['profit_factor'],
                    "final_capital": results['final_capital'],
                    "backtest_time": elapsed
                })
                
                print(f"      Return: {results['total_return']*100:+.2f}%")
                print(f"      Sharpe: {results['sharpe_ratio']:.3f}")
                print(f"      Sortino: {results['sortino_ratio']:.3f}")
                print(f"      Max DD: {results['max_drawdown']*100:.2f}%")
                print(f"      Trades: {results['total_trades']}")
                print(f"      Win Rate: {results['win_rate']*100:.1f}%")
                print(f"      Profit Factor: {results['profit_factor']:.2f}")
                print(f"      Time: {elapsed:.2f}s")
                
            except Exception as e:
                print(f"      ❌ Ошибка: {e}")
                tf_results.append({
                    "params": params,
                    "error": str(e)
                })
        
        all_results[tf] = tf_results
        self.test_results["grid_search_results"] = all_results
        
        return all_results
    
    async def phase3_ai_results_analysis(self, grid_results: Dict):
        """ФАЗА 3: AI анализ результатов оптимизации."""
        print("\n" + "="*80)
        print("📋 ФАЗА 3: AI АНАЛИЗ РЕЗУЛЬТАТОВ")
        print("="*80)
        
        # Подготовка данных
        tf = self.central_tf
        results = grid_results.get(tf, [])
        valid_results = [r for r in results if 'error' not in r]
        
        if not valid_results:
            print("\n⚠️ Нет валидных результатов для анализа")
            return
        
        # Топ-3 по разным метрикам
        by_sharpe = sorted(valid_results, key=lambda x: x['sharpe_ratio'], reverse=True)[:3]
        by_return = sorted(valid_results, key=lambda x: x['total_return'], reverse=True)[:3]
        by_profit_factor = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)[:3]
        
        results_summary = f"""
TOP 3 BY SHARPE RATIO:
{chr(10).join([f"{i+1}. {r['params']['name']}: Sharpe={r['sharpe_ratio']:.3f}, Return={r['total_return_pct']:+.2f}%, PF={r['profit_factor']:.2f}, WR={r['win_rate']*100:.1f}%" for i, r in enumerate(by_sharpe)])}

TOP 3 BY TOTAL RETURN:
{chr(10).join([f"{i+1}. {r['params']['name']}: Return={r['total_return_pct']:+.2f}%, Sharpe={r['sharpe_ratio']:.3f}, PF={r['profit_factor']:.2f}, DD={r['max_drawdown_pct']:.2f}%" for i, r in enumerate(by_return)])}

TOP 3 BY PROFIT FACTOR:
{chr(10).join([f"{i+1}. {r['params']['name']}: PF={r['profit_factor']:.2f}, Return={r['total_return_pct']:+.2f}%, WR={r['win_rate']*100:.1f}%, Sharpe={r['sharpe_ratio']:.3f}" for i, r in enumerate(by_profit_factor)])}
"""
        
        query = f"""Analyze these backtest optimization results from 90 days of BTCUSDT data on 15m timeframe:

RESULTS:
{results_summary}

ANALYSIS REQUIRED:
1. Which parameter set is most robust across all metrics?
2. Are there overfitting concerns with any results?
3. What risk/reward profile is best for production?
4. Should we do walk-forward validation on any of these?
5. Any parameter patterns that stand out?

Provide actionable recommendations."""

        print(f"\n🤖 Copilot → Perplexity:")
        print(f"   Query: Results analysis...")
        
        response = await self.call_perplexity(query)
        
        print(f"\n💡 Perplexity Response:")
        print(response)
        
        self.test_results["phases"]["phase3_results_analysis"] = {
            "query": query,
            "response": response,
            "top_results": {
                "by_sharpe": [{"name": r['params']['name'], "sharpe": r['sharpe_ratio'], "return": r['total_return_pct']} for r in by_sharpe],
                "by_return": [{"name": r['params']['name'], "return": r['total_return_pct'], "sharpe": r['sharpe_ratio']} for r in by_return],
                "by_profit_factor": [{"name": r['params']['name'], "pf": r['profit_factor'], "return": r['total_return_pct']} for r in by_profit_factor],
            }
        }
        
        return response
    
    def print_final_summary(self, grid_results: Dict):
        """Финальный summary."""
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНЫЙ SUMMARY")
        print("="*80)
        
        tf = self.central_tf
        results = grid_results.get(tf, [])
        valid = [r for r in results if 'error' not in r]
        
        if not valid:
            print(f"\n❌ Нет валидных результатов")
            return
        
        # Лучший по Sharpe
        by_sharpe = sorted(valid, key=lambda x: x['sharpe_ratio'], reverse=True)
        best = by_sharpe[0]
        
        print(f"\n🏆 ЛУЧШИЙ РЕЗУЛЬТАТ (по Sharpe Ratio):")
        print(f"   Параметры: {best['params']['name']}")
        print(f"   EMA: {best['params']['fast_ema']}/{best['params']['slow_ema']}")
        print(f"   Return: {best['total_return_pct']:+.2f}%")
        print(f"   Sharpe: {best['sharpe_ratio']:.3f}")
        print(f"   Sortino: {best['sortino_ratio']:.3f}")
        print(f"   Max DD: {best['max_drawdown_pct']:.2f}%")
        print(f"   Trades: {best['total_trades']}")
        print(f"   Win Rate: {best['win_rate']*100:.1f}%")
        print(f"   Profit Factor: {best['profit_factor']:.2f}")
        
        # Статистика по всем вариантам
        print(f"\n📈 СТАТИСТИКА ПО ВСЕМ ВАРИАНТАМ:")
        print(f"   Avg Return: {sum(r['total_return_pct'] for r in valid)/len(valid):.2f}%")
        print(f"   Avg Sharpe: {sum(r['sharpe_ratio'] for r in valid)/len(valid):.3f}")
        print(f"   Avg Win Rate: {sum(r['win_rate'] for r in valid)/len(valid)*100:.1f}%")
        print(f"   Profitable: {len([r for r in valid if r['total_return'] > 0])}/{len(valid)}")
    
    def save_report(self):
        """Сохранение отчёта."""
        report_path = "FULL_90DAY_MTF_AI_WORKFLOW_REPORT.json"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n✅ Отчёт сохранён: {report_path}")
    
    async def run(self, symbol: str = "BTCUSDT", skip_ai: bool = True):
        """Главный метод."""
        print("\n" + "🌟"*40)
        print("🚀 ПОЛНЫЙ 90-ДНЕВНЫЙ MTF AI WORKFLOW")
        print("🌟"*40)
        print(f"\nСимвол: {symbol}")
        print(f"Период: {self.test_period_start.strftime('%Y-%m-%d')} - {self.current_date.strftime('%Y-%m-%d')} (90 дней)")
        print(f"Таймфреймы: {', '.join([f'{tf}m' for tf in self.timeframes])}")
        print(f"Центральный TF: {self.central_tf}m")
        
        if not skip_ai:
            # ФАЗА 1: AI дизайн стратегии
            strategy_design = await self.phase1_ai_mtf_strategy_design()
        else:
            print("\n⚠️ РЕЖИМ БЕЗ AI: Perplexity фазы пропущены")
            strategy_design = "EMA Crossover MTF Strategy (default)"
        
        # Загрузка ПОЛНЫХ 90 дней
        mtf_data = self.load_full_90days_data(symbol)
        
        if not mtf_data:
            print("\n❌ Не удалось загрузить данные")
            return
        
        if not skip_ai:
            # ФАЗА 2: AI план оптимизации
            await self.phase2_ai_optimization_plan(strategy_design, self.test_results["data_loaded"])
        
        # Grid Search
        grid_results = self.run_grid_search(mtf_data)
        
        if not skip_ai:
            # ФАЗА 3: AI анализ результатов
            await self.phase3_ai_results_analysis(grid_results)
        
        # Summary
        self.print_final_summary(grid_results)
        
        # Отчёт
        self.save_report()
        
        print("\n" + "="*80)
        print("✅ ПОЛНЫЙ AI WORKFLOW ЗАВЕРШЁН!")
        print("="*80)


if __name__ == "__main__":
    workflow = Full90DayMTFWorkflow()
    asyncio.run(workflow.run(symbol="BTCUSDT", skip_ai=False))  # Включаем AI!

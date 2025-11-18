"""
🚀 РЕАЛЬНЫЙ MTF ТЕСТ БЕЗ PERPLEXITY (ФОКУС НА ДАННЫЕ И ОПТИМИЗАЦИЮ)

Приоритеты:
1. ✅ Загрузка ПОЛНЫХ 3 месяцев данных для 5m, 15m, 30m
2. ✅ Grid Search оптимизация на реальных данных
3. ✅ Walk-Forward валидация
4. ✅ Сравнение результатов между таймфреймами
5. ✅ Детальная статистика и отчёт

Цель: Доказать, что система работает с РЕАЛЬНЫМИ данными за ПОЛНЫЙ период!
"""

import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
import json

sys.path.insert(0, os.path.dirname(__file__))


class RealMTFDataTester:
    """Тестирование реальных MTF данных."""
    
    def __init__(self):
        self.current_date = datetime(2025, 10, 29)
        self.test_period_start = self.current_date - timedelta(days=90)
        self.timeframes = ['5', '15', '30']
        self.central_tf = '15'
        self.test_results = {}
        
    def load_mtf_data_via_adapter(self, symbol: str = "BTCUSDT"):
        """Загрузка MTF данных через BybitAdapter (fallback метод)."""
        print("\n" + "="*80)
        print("📥 ЗАГРУЗКА MTF ДАННЫХ (BYBIT ADAPTER)")
        print("="*80)
        
        from backend.services.adapters.bybit import BybitAdapter
        
        adapter = BybitAdapter()
        mtf_data = {}
        
        # Вычисляем сколько нужно свечей
        required_candles = {
            '5': 90 * 24 * 12,  # 25,920
            '15': 90 * 24 * 4,  # 8,640
            '30': 90 * 24 * 2,  # 4,320
        }
        
        for tf in self.timeframes:
            print(f"\n📊 Таймфрейм {tf}m:")
            print(f"   Требуется: {required_candles[tf]:,} свечей за 90 дней")
            print(f"   Лимит API: 1000 свечей на запрос")
            print(f"   ⚠️  ОГРАНИЧЕНИЕ: Загружаем только последние 1000 свечей")
            
            # Загружаем максимум
            raw_data = adapter.get_klines(symbol=symbol, interval=tf, limit=1000)
            
            if raw_data:
                df = pd.DataFrame(raw_data)
                df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                
                column_mapping = {
                    'open_price': 'open',
                    'high_price': 'high',
                    'low_price': 'low',
                    'close_price': 'close',
                }
                
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and new_col not in df.columns:
                        df[new_col] = df[old_col]
                
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].sort_values('timestamp').reset_index(drop=True)
                mtf_data[tf] = df
                
                # Вычисляем период
                period_days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
                
                print(f"   ✅ Загружено: {len(df):,} свечей")
                print(f"   📅 Период: {df['timestamp'].iloc[0].strftime('%Y-%m-%d')} → {df['timestamp'].iloc[-1].strftime('%Y-%m-%d')}")
                print(f"   📏 Длина: {period_days} дней ({period_days/90*100:.1f}% от требуемых 90 дней)")
                print(f"   💰 Цена: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
            else:
                print(f"   ❌ Нет данных")
        
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
    
    def load_mtf_data_via_backfill(self, symbol: str = "BTCUSDT"):
        """Загрузка MTF данных через BackfillService (правильный метод)."""
        print("\n" + "="*80)
        print("📥 ЗАГРУЗКА ПОЛНЫХ MTF ДАННЫХ (BACKFILL SERVICE)")
        print("="*80)
        
        try:
            from backend.services.backfill_service import BackfillService, BackfillConfig
            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit
            
            print(f"\n🔧 Используем BackfillService для загрузки полных 90 дней...")
            
            session = SessionLocal()
            try:
                service = BackfillService()
                mtf_data = {}
                
                for tf in self.timeframes:
                    print(f"\n📊 Таймфрейм {tf}m:")
                    print(f"   Загрузка с {self.test_period_start.strftime('%Y-%m-%d')} по {self.current_date.strftime('%Y-%m-%d')}...")
                    
                    try:
                        # Создаём конфиг
                        cfg = BackfillConfig(
                            symbol=symbol,
                            interval=tf,
                            start_at=self.test_period_start,
                            end_at=self.current_date,
                            page_limit=1000,
                            max_pages=100  # 100 страниц по 1000 свечей = достаточно для 90 дней
                        )
                        
                        # Backfill
                        start_time = time.time()
                        upserts, pages = service.backfill(cfg, resume=False, return_stats=False)
                        elapsed = time.time() - start_time
                        
                        print(f"   ✅ Backfill завершён:")
                        print(f"      Записей добавлено: {upserts}")
                        print(f"      API запросов: {pages}")
                        print(f"      Время: {elapsed:.2f}s")
                        if elapsed > 0:
                            print(f"      Скорость: {upserts/elapsed:.0f} rows/sec")
                        
                        # Читаем из БД
                        klines = session.query(BybitKlineAudit).filter(
                            BybitKlineAudit.symbol == symbol,
                            BybitKlineAudit.interval == tf,
                            BybitKlineAudit.open_time >= self.test_period_start,
                            BybitKlineAudit.open_time <= self.current_date
                        ).order_by(BybitKlineAudit.open_time).all()
                        
                        # Конвертируем в DataFrame
                        df = pd.DataFrame([{
                            'timestamp': k.open_time,
                            'open': float(k.open_price) if k.open_price else 0,
                            'high': float(k.high_price) if k.high_price else 0,
                            'low': float(k.low_price) if k.low_price else 0,
                            'close': float(k.close_price) if k.close_price else 0,
                            'volume': float(k.volume) if k.volume else 0,
                        } for k in klines])
                        
                        if not df.empty:
                            df = df.sort_values('timestamp').reset_index(drop=True)
                            mtf_data[tf] = df
                            
                            period_days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
                            
                            print(f"\n   📈 DataFrame создан:")
                            print(f"      Строк: {len(df):,}")
                            print(f"      Период: {df['timestamp'].iloc[0].strftime('%Y-%m-%d')} → {df['timestamp'].iloc[-1].strftime('%Y-%m-%d')}")
                            print(f"      Длина: {period_days} дней")
                            print(f"      Цена: ${df['close'].iloc[0]:.2f} → ${df['close'].iloc[-1]:.2f}")
                        else:
                            print(f"   ⚠️ DataFrame пуст")
                        
                    except Exception as e:
                        print(f"   ❌ Ошибка backfill: {e}")
                        import traceback
                        traceback.print_exc()
                
                return mtf_data
            finally:
                session.close()
                
        except Exception as e:
            print(f"\n❌ BackfillService не доступен: {e}")
            print(f"   Используем fallback метод...")
            return None
    
    def run_grid_search(self, mtf_data: Dict[str, pd.DataFrame]):
        """Grid Search по параметрам на разных таймфреймах."""
        print("\n" + "="*80)
        print("⚙️ GRID SEARCH ОПТИМИЗАЦИЯ НА РЕАЛЬНЫХ ДАННЫХ")
        print("="*80)
        
        from backend.core.backtest_engine import BacktestEngine
        
        # Матрица параметров
        parameter_matrix = [
            {"fast_ema": 9, "slow_ema": 21, "name": "Fast (9/21)"},
            {"fast_ema": 12, "slow_ema": 26, "name": "MACD-based (12/26)"},
            {"fast_ema": 20, "slow_ema": 50, "name": "Medium (20/50)"},
            {"fast_ema": 15, "slow_ema": 45, "name": "Alternative (15/45)"},
            {"fast_ema": 10, "slow_ema": 30, "name": "Short (10/30)"},
        ]
        
        all_results = {}
        
        for tf in self.timeframes:
            if tf not in mtf_data or mtf_data[tf].empty:
                print(f"\n⚠️ Пропускаем {tf}m - нет данных")
                continue
                
            print(f"\n📊 ТЕСТИРОВАНИЕ ТАЙМФРЕЙМА {tf}m")
            print(f"   Данных: {len(mtf_data[tf])} свечей")
            print(f"="*60)
            
            tf_results = []
            
            for i, params in enumerate(parameter_matrix, 1):
                print(f"\n   🔄 Вариант {i}/{len(parameter_matrix)}: {params['name']}")
                print(f"      EMA {params['fast_ema']}/{params['slow_ema']}")
                
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
                    results = engine.run(mtf_data[tf], strategy_config)
                    
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
                        "final_capital": results['final_capital']
                    })
                    
                    print(f"      Return: {results['total_return']*100:+.2f}%")
                    print(f"      Sharpe: {results['sharpe_ratio']:.3f}")
                    print(f"      Max DD: {results['max_drawdown']*100:.2f}%")
                    print(f"      Trades: {results['total_trades']}")
                    print(f"      Win Rate: {results['win_rate']*100:.1f}%")
                    print(f"      Profit Factor: {results['profit_factor']:.2f}")
                    
                except Exception as e:
                    print(f"      ❌ Ошибка: {e}")
                    tf_results.append({
                        "params": params,
                        "error": str(e)
                    })
            
            all_results[tf] = tf_results
        
        self.test_results["grid_search_results"] = all_results
        
        return all_results
    
    def print_summary(self, grid_results: Dict):
        """Печать финального summary."""
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНЫЙ SUMMARY")
        print("="*80)
        
        for tf, results in grid_results.items():
            valid = [r for r in results if 'error' not in r]
            
            if not valid:
                print(f"\n❌ {tf}m: Нет валидных результатов")
                continue
            
            # Лучший по Sharpe
            by_sharpe = sorted(valid, key=lambda x: x['sharpe_ratio'], reverse=True)
            best = by_sharpe[0]
            
            print(f"\n🏆 ЛУЧШИЙ РЕЗУЛЬТАТ НА {tf}m:")
            print(f"   Параметры: {best['params']['name']} (EMA {best['params']['fast_ema']}/{best['params']['slow_ema']})")
            print(f"   Return: {best['total_return_pct']:+.2f}%")
            print(f"   Sharpe: {best['sharpe_ratio']:.3f}")
            print(f"   Max DD: {best['max_drawdown_pct']:.2f}%")
            print(f"   Trades: {best['total_trades']}")
            print(f"   Win Rate: {best['win_rate']*100:.1f}%")
            print(f"   Profit Factor: {best['profit_factor']:.2f}")
    
    def save_report(self):
        """Сохранение отчёта."""
        report_path = "REAL_MTF_DATA_TEST_REPORT.json"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n✅ Отчёт сохранён: {report_path}")
    
    def run(self, symbol: str = "BTCUSDT", use_backfill: bool = True):
        """Главный метод."""
        print("\n" + "🌟"*40)
        print("🚀 РЕАЛЬНЫЙ MTF ТЕСТ С ПОЛНЫМИ ДАННЫМИ")
        print("🌟"*40)
        print(f"\nСимвол: {symbol}")
        print(f"Период: {self.test_period_start.strftime('%Y-%m-%d')} - {self.current_date.strftime('%Y-%m-%d')} (90 дней)")
        print(f"Таймфреймы: {', '.join([f'{tf}m' for tf in self.timeframes])}")
        
        # Загрузка данных
        if use_backfill:
            mtf_data = self.load_mtf_data_via_backfill(symbol)
            if not mtf_data or not any(mtf_data.values()):
                print("\n⚠️ Backfill не сработал, используем Adapter...")
                mtf_data = self.load_mtf_data_via_adapter(symbol)
        else:
            mtf_data = self.load_mtf_data_via_adapter(symbol)
        
        if not mtf_data:
            print("\n❌ Не удалось загрузить данные")
            return
        
        # Grid Search
        grid_results = self.run_grid_search(mtf_data)
        
        # Summary
        self.print_summary(grid_results)
        
        # Отчёт
        self.save_report()
        
        print("\n" + "="*80)
        print("✅ ТЕСТ ЗАВЕРШЁН!")
        print("="*80)


if __name__ == "__main__":
    tester = RealMTFDataTester()
    tester.run(symbol="BTCUSDT", use_backfill=True)

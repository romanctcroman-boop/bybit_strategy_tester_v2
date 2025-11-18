"""
Report Generator - CSV Export (ТЗ 4)

Генерация отчетов в форматах CSV согласно ТЗ раздел 4:
- List-of-trades.csv (4.1)
- Performance.csv (4.2)
- Risk-performance-ratios.csv (4.3)
- Trades-analysis.csv (4.4)

Все форматы точно соответствуют структуре из ТЗ с разделением All/Long/Short.
"""

import io
import csv
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger


class ReportGenerator:
    """
    Генератор CSV отчетов согласно ТЗ раздел 4
    
    Принимает результаты BacktestEngine и генерирует 4 типа CSV файлов:
    1. List-of-trades.csv - детальный лог всех сделок
    2. Performance.csv - основные показатели эффективности
    3. Risk-performance-ratios.csv - метрики риска
    4. Trades-analysis.csv - статистический анализ сделок
    """
    
    def __init__(self, backtest_results: Dict[str, Any], initial_capital: float = 10000.0):
        """
        Args:
            backtest_results: Результаты BacktestEngine.run()
            initial_capital: Начальный капитал
        """
        self.results = backtest_results
        self.initial_capital = initial_capital
        self.trades = backtest_results.get('trades', [])
        
        # Разделяем сделки по направлениям
        self.all_trades = [t for t in self.trades if t.get('exit_price')]
        self.long_trades = [t for t in self.all_trades if t.get('side') == 'long']
        self.short_trades = [t for t in self.all_trades if t.get('side') == 'short']
        
        logger.info(f"ReportGenerator initialized: {len(self.all_trades)} trades total")
    
    # ========================================================================
    # 4.1 LIST-OF-TRADES.CSV
    # ========================================================================
    
    def generate_list_of_trades_csv(self) -> str:
        """
        Генерирует List-of-trades.csv (ТЗ 4.1)
        
        Формат:
        Trade #, Type, Date/Time, Signal, Price USDT, Position size (qty),
        Position size (value), Net P&L USDT, Net P&L %, Run-up USDT, Run-up %,
        Drawdown USDT, Drawdown %, Cumulative P&L USDT, Cumulative P&L %
        
        Returns:
            CSV строка
        """
        logger.info("Generating List-of-trades.csv")
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow([
            'Trade #',
            'Type',
            'Date/Time',
            'Signal',
            'Price USDT',
            'Position size (qty)',
            'Position size (value)',
            'Net P&L USDT',
            'Net P&L %',
            'Run-up USDT',
            'Run-up %',
            'Drawdown USDT',
            'Drawdown %',
            'Cumulative P&L USDT',
            'Cumulative P&L %'
        ])
        
        cumulative_pnl = 0.0
        
        for i, trade in enumerate(self.all_trades, start=1):
            side = trade.get('side', 'long')
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            qty = trade.get('qty', 0)
            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            
            # Рассчитываем run-up и drawdown (если есть)
            runup = trade.get('max_profit', 0)
            runup_pct = (runup / (entry_price * qty) * 100) if entry_price * qty > 0 else 0
            drawdown = trade.get('max_loss', 0)
            drawdown_pct = (drawdown / (entry_price * qty) * 100) if entry_price * qty > 0 else 0
            
            cumulative_pnl += pnl
            cumulative_pnl_pct = (cumulative_pnl / self.initial_capital) * 100
            
            position_value = entry_price * qty
            
            # Entry запись
            entry_time = trade.get('entry_time', datetime.now())
            entry_signal = trade.get('entry_signal', 'buy' if side == 'long' else 'sell')
            
            writer.writerow([
                i,
                f'Entry {side}',
                entry_time.strftime('%Y-%m-%d %H:%M') if isinstance(entry_time, datetime) else entry_time,
                entry_signal,
                f'{entry_price:.3f}',
                f'{qty:.3f}',
                f'{position_value:.6f}',
                f'{pnl:.2f}',
                f'{pnl_pct:.2f}',
                f'{runup:.2f}',
                f'{runup_pct:.2f}',
                f'{drawdown:.2f}',
                f'{drawdown_pct:.2f}',
                f'{cumulative_pnl:.2f}',
                f'{cumulative_pnl_pct:.2f}'
            ])
            
            # Exit запись
            exit_time = trade.get('exit_time', datetime.now())
            exit_signal = trade.get('exit_signal', 'Long Trail' if side == 'long' else 'Short Trail')
            
            writer.writerow([
                i,
                f'Exit {side}',
                exit_time.strftime('%Y-%m-%d %H:%M') if isinstance(exit_time, datetime) else exit_time,
                exit_signal,
                f'{exit_price:.3f}',
                f'{qty:.3f}',
                f'{position_value:.6f}',
                f'{pnl:.2f}',
                f'{pnl_pct:.2f}',
                f'{runup:.2f}',
                f'{runup_pct:.2f}',
                f'{drawdown:.2f}',
                f'{drawdown_pct:.2f}',
                f'{cumulative_pnl:.2f}',
                f'{cumulative_pnl_pct:.2f}'
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"List-of-trades.csv generated: {len(self.all_trades)} trades")
        return csv_content
    
    # ========================================================================
    # 4.2 PERFORMANCE.CSV
    # ========================================================================
    
    def generate_performance_csv(self) -> str:
        """
        Генерирует Performance.csv (ТЗ 4.2)
        
        Формат (All/Long/Short columns):
        - Open P&L
        - Net profit (USDT и %)
        - Gross profit / Gross loss
        - Commission paid
        - Buy & hold return
        - Max equity run-up
        - Max equity drawdown
        - Max contracts held
        
        Returns:
            CSV строка
        """
        logger.info("Generating Performance.csv")
        
        # Рассчитываем метрики для All/Long/Short
        all_metrics = self._calculate_performance_metrics(self.all_trades)
        long_metrics = self._calculate_performance_metrics(self.long_trades)
        short_metrics = self._calculate_performance_metrics(self.short_trades)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow([
            '',
            'All USDT', 'All %',
            'Long USDT', 'Long %',
            'Short USDT', 'Short %'
        ])
        
        # Open P&L (для открытых позиций - пока 0)
        writer.writerow([
            'Open P&L',
            '0.00', '0.00',
            '', '',
            '', ''
        ])
        
        # Net profit
        writer.writerow([
            'Net profit',
            f"{all_metrics['net_profit']:.2f}",
            f"{all_metrics['net_profit_pct']:.2f}",
            f"{long_metrics['net_profit']:.2f}",
            f"{long_metrics['net_profit_pct']:.2f}",
            f"{short_metrics['net_profit']:.2f}",
            f"{short_metrics['net_profit_pct']:.2f}"
        ])
        
        # Gross profit
        writer.writerow([
            'Gross profit',
            f"{all_metrics['gross_profit']:.2f}",
            f"{all_metrics['gross_profit_pct']:.2f}",
            f"{long_metrics['gross_profit']:.2f}",
            f"{long_metrics['gross_profit_pct']:.2f}",
            f"{short_metrics['gross_profit']:.2f}",
            f"{short_metrics['gross_profit_pct']:.2f}"
        ])
        
        # Gross loss
        writer.writerow([
            'Gross loss',
            f"{all_metrics['gross_loss']:.2f}",
            f"{all_metrics['gross_loss_pct']:.2f}",
            f"{long_metrics['gross_loss']:.2f}",
            f"{long_metrics['gross_loss_pct']:.2f}",
            f"{short_metrics['gross_loss']:.2f}",
            f"{short_metrics['gross_loss_pct']:.2f}"
        ])
        
        # Commission paid
        writer.writerow([
            'Commission paid',
            f"{all_metrics['commission']:.2f}",
            '',
            f"{long_metrics['commission']:.2f}",
            '',
            f"{short_metrics['commission']:.2f}",
            ''
        ])
        
        # Buy & hold return
        metrics = self.results.get('metrics', {})
        buy_hold_return = metrics.get('buy_hold_return', 0)
        buy_hold_pct = metrics.get('buy_hold_return_pct', 0)
        writer.writerow([
            'Buy & hold return',
            f"{buy_hold_return:.2f}",
            f"{buy_hold_pct:.2f}",
            '', '',
            '', ''
        ])
        
        # Max equity run-up
        writer.writerow([
            'Max equity run-up',
            f"{all_metrics['max_runup']:.2f}",
            f"{all_metrics['max_runup_pct']:.2f}",
            '', '',
            '', ''
        ])
        
        # Max equity drawdown
        writer.writerow([
            'Max equity drawdown',
            f"{all_metrics['max_drawdown']:.2f}",
            f"{all_metrics['max_drawdown_pct']:.2f}",
            '', '',
            '', ''
        ])
        
        # Max contracts held
        max_qty = max([t.get('qty', 0) for t in self.all_trades], default=0)
        max_long = max([t.get('qty', 0) for t in self.long_trades], default=0)
        max_short = max([t.get('qty', 0) for t in self.short_trades], default=0)
        
        writer.writerow([
            'Max contracts held',
            f"{max_qty:.0f}",
            '',
            f"{max_long:.0f}",
            '',
            f"{max_short:.0f}",
            ''
        ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info("Performance.csv generated")
        return csv_content
    
    # ========================================================================
    # 4.3 RISK-PERFORMANCE-RATIOS.CSV
    # ========================================================================
    
    def generate_risk_ratios_csv(self) -> str:
        """
        Генерирует Risk-performance-ratios.csv (ТЗ 4.3)
        
        Формат:
        - Sharpe ratio
        - Sortino ratio
        - Profit factor
        - Margin calls
        
        Returns:
            CSV строка
        """
        logger.info("Generating Risk-performance-ratios.csv")
        
        all_risk = self._calculate_risk_metrics(self.all_trades)
        long_risk = self._calculate_risk_metrics(self.long_trades)
        short_risk = self._calculate_risk_metrics(self.short_trades)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow([
            '',
            'All USDT', 'All %',
            'Long USDT', 'Long %',
            'Short USDT', 'Short %'
        ])
        
        # Sharpe ratio
        writer.writerow([
            'Sharpe ratio',
            f"{all_risk['sharpe']:.2f}",
            '',
            '', '',
            '', ''
        ])
        
        # Sortino ratio
        writer.writerow([
            'Sortino ratio',
            f"{all_risk['sortino']:.2f}",
            '',
            '', '',
            '', ''
        ])
        
        # Profit factor
        writer.writerow([
            'Profit factor',
            f"{all_risk['profit_factor']:.3f}",
            '',
            f"{long_risk['profit_factor']:.3f}",
            '',
            '', ''
        ])
        
        # Margin calls
        writer.writerow([
            'Margin calls',
            '0',
            '',
            '0',
            '',
            '0',
            ''
        ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info("Risk-performance-ratios.csv generated")
        return csv_content
    
    # ========================================================================
    # 4.4 TRADES-ANALYSIS.CSV
    # ========================================================================
    
    def generate_trades_analysis_csv(self) -> str:
        """
        Генерирует Trades-analysis.csv (ТЗ 4.4)
        
        Формат:
        - Total trades
        - Winning/Losing trades
        - Percent profitable
        - Avg P&L
        - Avg winning/losing trade
        - Ratio avg win / avg loss
        - Largest winning/losing trade
        - Avg # bars in trades
        
        Returns:
            CSV строка
        """
        logger.info("Generating Trades-analysis.csv")
        
        all_analysis = self._calculate_trade_analysis(self.all_trades)
        long_analysis = self._calculate_trade_analysis(self.long_trades)
        short_analysis = self._calculate_trade_analysis(self.short_trades)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow([
            '',
            'All USDT', 'All %',
            'Long USDT', 'Long %',
            'Short USDT', 'Short %'
        ])
        
        # Total trades
        writer.writerow([
            'Total trades',
            str(all_analysis['total']),
            '',
            str(long_analysis['total']),
            '',
            str(short_analysis['total']),
            ''
        ])
        
        # Winning trades
        writer.writerow([
            'Winning trades',
            str(all_analysis['winning']),
            '',
            str(long_analysis['winning']),
            '',
            str(short_analysis['winning']),
            ''
        ])
        
        # Losing trades
        writer.writerow([
            'Losing trades',
            str(all_analysis['losing']),
            '',
            str(long_analysis['losing']),
            '',
            str(short_analysis['losing']),
            ''
        ])
        
        # Percent profitable
        writer.writerow([
            'Percent profitable',
            '',
            f"{all_analysis['win_rate']:.2f}",
            '',
            f"{long_analysis['win_rate']:.2f}",
            '',
            f"{short_analysis['win_rate']:.2f}"
        ])
        
        # Avg P&L
        writer.writerow([
            'Avg P&L',
            f"{all_analysis['avg_pnl']:.2f}",
            f"{all_analysis['avg_pnl_pct']:.2f}",
            f"{long_analysis['avg_pnl']:.2f}",
            f"{long_analysis['avg_pnl_pct']:.2f}",
            f"{short_analysis['avg_pnl']:.2f}",
            f"{short_analysis['avg_pnl_pct']:.2f}"
        ])
        
        # Avg winning trade
        writer.writerow([
            'Avg winning trade',
            f"{all_analysis['avg_win']:.2f}",
            f"{all_analysis['avg_win_pct']:.2f}",
            f"{long_analysis['avg_win']:.2f}",
            f"{long_analysis['avg_win_pct']:.2f}",
            f"{short_analysis['avg_win']:.2f}",
            f"{short_analysis['avg_win_pct']:.2f}"
        ])
        
        # Avg losing trade
        writer.writerow([
            'Avg losing trade',
            f"{all_analysis['avg_loss']:.2f}",
            f"{all_analysis['avg_loss_pct']:.2f}",
            f"{long_analysis['avg_loss']:.2f}",
            f"{long_analysis['avg_loss_pct']:.2f}",
            f"{short_analysis['avg_loss']:.2f}",
            f"{short_analysis['avg_loss_pct']:.2f}"
        ])
        
        # Ratio avg win / avg loss
        writer.writerow([
            'Ratio avg win / avg loss',
            f"{all_analysis['win_loss_ratio']:.2f}",
            '',
            f"{long_analysis['win_loss_ratio']:.2f}",
            '',
            f"{short_analysis['win_loss_ratio']:.2f}",
            ''
        ])
        
        # Largest winning trade
        writer.writerow([
            'Largest winning trade',
            f"{all_analysis['max_win']:.2f}",
            f"{all_analysis['max_win_pct']:.2f}",
            f"{long_analysis['max_win']:.2f}",
            f"{long_analysis['max_win_pct']:.2f}",
            f"{short_analysis['max_win']:.2f}",
            f"{short_analysis['max_win_pct']:.2f}"
        ])
        
        # Largest losing trade
        writer.writerow([
            'Largest losing trade',
            f"{all_analysis['max_loss']:.2f}",
            f"{all_analysis['max_loss_pct']:.2f}",
            f"{long_analysis['max_loss']:.2f}",
            f"{long_analysis['max_loss_pct']:.2f}",
            f"{short_analysis['max_loss']:.2f}",
            f"{short_analysis['max_loss_pct']:.2f}"
        ])
        
        # Avg # bars in trades
        writer.writerow([
            'Avg # bars in trades',
            f"{all_analysis['avg_bars']:.1f}",
            '',
            f"{long_analysis['avg_bars']:.1f}",
            '',
            f"{short_analysis['avg_bars']:.1f}",
            ''
        ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info("Trades-analysis.csv generated")
        return csv_content
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _calculate_performance_metrics(self, trades: List[Dict]) -> Dict[str, float]:
        """Рассчитывает метрики Performance для списка сделок"""
        if not trades:
            return {
                'net_profit': 0, 'net_profit_pct': 0,
                'gross_profit': 0, 'gross_profit_pct': 0,
                'gross_loss': 0, 'gross_loss_pct': 0,
                'commission': 0,
                'max_runup': 0, 'max_runup_pct': 0,
                'max_drawdown': 0, 'max_drawdown_pct': 0
            }
        
        pnls = [t.get('pnl', 0) for t in trades]
        net_profit = sum(pnls)
        net_profit_pct = (net_profit / self.initial_capital) * 100
        
        gross_profit = sum([p for p in pnls if p > 0])
        gross_profit_pct = (gross_profit / self.initial_capital) * 100
        
        gross_loss = abs(sum([p for p in pnls if p < 0]))
        gross_loss_pct = (gross_loss / self.initial_capital) * 100
        
        commission = sum([t.get('commission', 0) for t in trades])
        
        # Рассчитываем equity curve для max runup/drawdown
        equity = self.initial_capital
        equity_curve = [equity]
        for pnl in pnls:
            equity += pnl
            equity_curve.append(equity)
        
        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = running_max - equity_array
        max_dd = drawdown.max()
        max_dd_pct = (max_dd / self.initial_capital) * 100
        
        runup = equity_array - self.initial_capital
        max_runup = runup.max()
        max_runup_pct = (max_runup / self.initial_capital) * 100
        
        return {
            'net_profit': net_profit,
            'net_profit_pct': net_profit_pct,
            'gross_profit': gross_profit,
            'gross_profit_pct': gross_profit_pct,
            'gross_loss': gross_loss,
            'gross_loss_pct': gross_loss_pct,
            'commission': commission,
            'max_runup': max_runup,
            'max_runup_pct': max_runup_pct,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct
        }
    
    def _calculate_risk_metrics(self, trades: List[Dict]) -> Dict[str, float]:
        """Рассчитывает метрики Risk для списка сделок"""
        if not trades:
            return {
                'sharpe': 0,
                'sortino': 0,
                'profit_factor': 0
            }
        
        pnls = [t.get('pnl', 0) for t in trades]
        
        # Sharpe ratio (аннуализированный)
        returns = np.array(pnls) / self.initial_capital
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe = (mean_return * np.sqrt(252)) / (std_return + 1e-9)
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 1e-9
        sortino = (mean_return * np.sqrt(252)) / (downside_std + 1e-9)
        
        # Profit factor
        gross_profit = sum([p for p in pnls if p > 0])
        gross_loss = abs(sum([p for p in pnls if p < 0]))
        profit_factor = gross_profit / (gross_loss + 1e-9)
        
        return {
            'sharpe': sharpe,
            'sortino': sortino,
            'profit_factor': profit_factor
        }
    
    def _calculate_trade_analysis(self, trades: List[Dict]) -> Dict[str, Any]:
        """Рассчитывает метрики Trade Analysis для списка сделок"""
        if not trades:
            return {
                'total': 0, 'winning': 0, 'losing': 0, 'win_rate': 0,
                'avg_pnl': 0, 'avg_pnl_pct': 0,
                'avg_win': 0, 'avg_win_pct': 0,
                'avg_loss': 0, 'avg_loss_pct': 0,
                'win_loss_ratio': 0,
                'max_win': 0, 'max_win_pct': 0,
                'max_loss': 0, 'max_loss_pct': 0,
                'avg_bars': 0
            }
        
        pnls = [t.get('pnl', 0) for t in trades]
        pnl_pcts = [t.get('pnl_pct', 0) for t in trades]
        
        total = len(trades)
        winning = len([p for p in pnls if p > 0])
        losing = len([p for p in pnls if p < 0])
        win_rate = (winning / total * 100) if total > 0 else 0
        
        avg_pnl = np.mean(pnls)
        avg_pnl_pct = np.mean(pnl_pcts)
        
        wins = [p for p in pnls if p > 0]
        win_pcts = [pnl_pcts[i] for i, p in enumerate(pnls) if p > 0]
        avg_win = np.mean(wins) if wins else 0
        avg_win_pct = np.mean(win_pcts) if win_pcts else 0
        
        losses = [p for p in pnls if p < 0]
        loss_pcts = [pnl_pcts[i] for i, p in enumerate(pnls) if p < 0]
        avg_loss = np.mean(losses) if losses else 0
        avg_loss_pct = np.mean(loss_pcts) if loss_pcts else 0
        
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        max_win = max(pnls) if pnls else 0
        max_win_pct = max(pnl_pcts) if pnl_pcts else 0
        
        max_loss = min(pnls) if pnls else 0
        max_loss_pct = min(pnl_pcts) if pnl_pcts else 0
        
        # Avg bars (если есть данные)
        bars = [t.get('bars_held', 0) for t in trades]
        avg_bars = np.mean(bars) if bars else 0
        
        return {
            'total': total,
            'winning': winning,
            'losing': losing,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'avg_pnl_pct': avg_pnl_pct,
            'avg_win': avg_win,
            'avg_win_pct': avg_win_pct,
            'avg_loss': avg_loss,
            'avg_loss_pct': avg_loss_pct,
            'win_loss_ratio': win_loss_ratio,
            'max_win': max_win,
            'max_win_pct': max_win_pct,
            'max_loss': max_loss,
            'max_loss_pct': max_loss_pct,
            'avg_bars': avg_bars
        }
    
    # ========================================================================
    # CONVENIENCE METHOD
    # ========================================================================
    
    def generate_all_reports(self) -> Dict[str, str]:
        """
        Генерирует все 4 CSV отчета
        
        Returns:
            Dict с ключами: list_of_trades, performance, risk_ratios, trades_analysis
        """
        logger.info("Generating all CSV reports")
        
        return {
            'list_of_trades': self.generate_list_of_trades_csv(),
            'performance': self.generate_performance_csv(),
            'risk_ratios': self.generate_risk_ratios_csv(),
            'trades_analysis': self.generate_trades_analysis_csv()
        }

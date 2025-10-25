"""
Tests for Report Generator - CSV Export (ТЗ 4)
"""

import pytest
from datetime import datetime, timedelta
import csv
import io
from backend.services.report_generator import ReportGenerator


@pytest.fixture
def sample_backtest_results():
    """Sample backtest results with realistic trades"""
    start_time = datetime(2024, 1, 1, 0, 0)
    
    trades = [
        # Trade 1: Long winning trade
        {
            'side': 'long',
            'entry_time': start_time,
            'entry_price': 40000.0,
            'entry_signal': 'buy',
            'exit_time': start_time + timedelta(hours=12),
            'exit_price': 41000.0,
            'exit_signal': 'Long Trail',
            'qty': 0.1,
            'pnl': 100.0,
            'pnl_pct': 2.5,
            'commission': 2.0,
            'max_profit': 120.0,
            'max_loss': -10.0,
            'bars_held': 24
        },
        # Trade 2: Long losing trade
        {
            'side': 'long',
            'entry_time': start_time + timedelta(days=1),
            'entry_price': 41000.0,
            'entry_signal': 'buy',
            'exit_time': start_time + timedelta(days=1, hours=6),
            'exit_price': 40500.0,
            'exit_signal': 'Stop Loss',
            'qty': 0.1,
            'pnl': -50.0,
            'pnl_pct': -1.22,
            'commission': 2.0,
            'max_profit': 20.0,
            'max_loss': -60.0,
            'bars_held': 12
        },
        # Trade 3: Short winning trade
        {
            'side': 'short',
            'entry_time': start_time + timedelta(days=2),
            'entry_price': 40500.0,
            'entry_signal': 'sell',
            'exit_time': start_time + timedelta(days=2, hours=18),
            'exit_price': 39500.0,
            'exit_signal': 'Take Profit',
            'qty': 0.1,
            'pnl': 100.0,
            'pnl_pct': 2.47,
            'commission': 2.0,
            'max_profit': 150.0,
            'max_loss': -5.0,
            'bars_held': 36
        }
    ]
    
    return {
        'trades': trades,
        'buy_hold_return': 500.0,
        'buy_hold_return_pct': 5.0
    }


class TestReportGenerator:
    """Test suite for ReportGenerator"""
    
    def test_initialization(self, sample_backtest_results):
        """Test ReportGenerator initialization"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        
        assert gen.initial_capital == 10000.0
        assert len(gen.all_trades) == 3
        assert len(gen.long_trades) == 2
        assert len(gen.short_trades) == 1
    
    def test_generate_list_of_trades(self, sample_backtest_results):
        """Test List-of-trades.csv generation"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        csv_content = gen.generate_list_of_trades_csv()
        
        # Parse CSV
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Verify header
        assert rows[0][0] == 'Trade #'
        assert 'Net P&L USDT' in rows[0]
        assert 'Cumulative P&L USDT' in rows[0]
        
        # Verify we have Entry + Exit for each trade (3 trades * 2 = 6 rows + header)
        assert len(rows) == 7
        
        # Verify first trade entry
        entry_row = rows[1]
        assert entry_row[0] == '1'  # Trade #
        assert 'Entry long' in entry_row[1]  # Type
        assert '40000.000' in entry_row[4]  # Price
        
        # Verify first trade exit
        exit_row = rows[2]
        assert exit_row[0] == '1'  # Same trade #
        assert 'Exit long' in exit_row[1]  # Type
        assert '41000.000' in exit_row[4]  # Exit price
        assert '100.00' in exit_row[7]  # Net P&L
    
    def test_generate_performance(self, sample_backtest_results):
        """Test Performance.csv generation"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        csv_content = gen.generate_performance_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Verify header structure (All/Long/Short columns)
        assert 'All USDT' in rows[0]
        assert 'Long USDT' in rows[0]
        assert 'Short USDT' in rows[0]
        
        # Find Net profit row
        net_profit_row = None
        for row in rows:
            if row[0] == 'Net profit':
                net_profit_row = row
                break
        
        assert net_profit_row is not None
        # Net profit = 100 - 50 + 100 = 150
        assert '150.00' in net_profit_row[1]  # All USDT
        assert '1.50' in net_profit_row[2]  # All % (150/10000 * 100)
        
        # Find Gross profit row
        gross_profit_row = None
        for row in rows:
            if row[0] == 'Gross profit':
                gross_profit_row = row
                break
        
        assert gross_profit_row is not None
        # Gross profit = 100 + 100 = 200
        assert '200.00' in gross_profit_row[1]
    
    def test_generate_risk_ratios(self, sample_backtest_results):
        """Test Risk-performance-ratios.csv generation"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        csv_content = gen.generate_risk_ratios_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Verify header
        assert 'All USDT' in rows[0]
        
        # Find Sharpe ratio row
        sharpe_row = None
        for row in rows:
            if row[0] == 'Sharpe ratio':
                sharpe_row = row
                break
        
        assert sharpe_row is not None
        # Sharpe should be a number
        assert sharpe_row[1] != ''
        
        # Find Profit factor row
        pf_row = None
        for row in rows:
            if row[0] == 'Profit factor':
                pf_row = row
                break
        
        assert pf_row is not None
        # Profit factor = 200 / 50 = 4.0
        assert '4.000' in pf_row[1]
    
    def test_generate_trades_analysis(self, sample_backtest_results):
        """Test Trades-analysis.csv generation"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        csv_content = gen.generate_trades_analysis_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Find Total trades row
        total_row = None
        for row in rows:
            if row[0] == 'Total trades':
                total_row = row
                break
        
        assert total_row is not None
        assert total_row[1] == '3'  # All
        assert total_row[3] == '2'  # Long
        assert total_row[5] == '1'  # Short
        
        # Find Winning trades row
        winning_row = None
        for row in rows:
            if row[0] == 'Winning trades':
                winning_row = row
                break
        
        assert winning_row is not None
        assert winning_row[1] == '2'  # 2 winning trades total
        
        # Find Percent profitable row
        win_rate_row = None
        for row in rows:
            if row[0] == 'Percent profitable':
                win_rate_row = row
                break
        
        assert win_rate_row is not None
        # Win rate = 2/3 = 66.67%
        assert '66.67' in win_rate_row[2]
    
    def test_generate_all_reports(self, sample_backtest_results):
        """Test generate_all_reports convenience method"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        reports = gen.generate_all_reports()
        
        assert 'list_of_trades' in reports
        assert 'performance' in reports
        assert 'risk_ratios' in reports
        assert 'trades_analysis' in reports
        
        # Verify all are non-empty strings
        for name, content in reports.items():
            assert isinstance(content, str)
            assert len(content) > 0
    
    def test_empty_trades_handling(self):
        """Test handling of empty trades list"""
        empty_results = {'trades': []}
        gen = ReportGenerator(empty_results, initial_capital=10000.0)
        
        # Should not crash
        csv_content = gen.generate_performance_csv()
        assert len(csv_content) > 0
        
        csv_content = gen.generate_trades_analysis_csv()
        assert len(csv_content) > 0
    
    def test_long_only_trades(self, sample_backtest_results):
        """Test with only long trades"""
        # Remove short trades
        long_only_results = sample_backtest_results.copy()
        long_only_results['trades'] = [t for t in sample_backtest_results['trades'] if t['side'] == 'long']
        
        gen = ReportGenerator(long_only_results, initial_capital=10000.0)
        
        assert len(gen.all_trades) == 2
        assert len(gen.long_trades) == 2
        assert len(gen.short_trades) == 0
        
        # Should still generate all reports
        reports = gen.generate_all_reports()
        assert len(reports) == 4
    
    def test_cumulative_pnl_calculation(self, sample_backtest_results):
        """Test cumulative P&L is correctly calculated"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        csv_content = gen.generate_list_of_trades_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Check cumulative P&L progression
        # Trade 1 exit: +100
        trade1_exit = rows[2]
        assert '100.00' in trade1_exit[13]  # Cumulative P&L
        
        # Trade 2 exit: +100 - 50 = +50
        trade2_exit = rows[4]
        assert '50.00' in trade2_exit[13]  # Cumulative P&L
        
        # Trade 3 exit: +50 + 100 = +150
        trade3_exit = rows[6]
        assert '150.00' in trade3_exit[13]  # Cumulative P&L
    
    def test_performance_metrics_accuracy(self, sample_backtest_results):
        """Test accuracy of performance metrics calculations"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        
        all_metrics = gen._calculate_performance_metrics(gen.all_trades)
        
        # Net profit: 100 - 50 + 100 = 150
        assert all_metrics['net_profit'] == pytest.approx(150.0, abs=0.01)
        
        # Gross profit: 100 + 100 = 200
        assert all_metrics['gross_profit'] == pytest.approx(200.0, abs=0.01)
        
        # Gross loss: 50
        assert all_metrics['gross_loss'] == pytest.approx(50.0, abs=0.01)
        
        # Commission: 2 * 3 = 6
        assert all_metrics['commission'] == pytest.approx(6.0, abs=0.01)
    
    def test_risk_metrics_accuracy(self, sample_backtest_results):
        """Test accuracy of risk metrics calculations"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        
        risk_metrics = gen._calculate_risk_metrics(gen.all_trades)
        
        # Profit factor: 200 / 50 = 4.0
        assert risk_metrics['profit_factor'] == pytest.approx(4.0, abs=0.01)
        
        # Sharpe and Sortino should be positive
        assert risk_metrics['sharpe'] > 0
        assert risk_metrics['sortino'] > 0
    
    def test_trade_analysis_accuracy(self, sample_backtest_results):
        """Test accuracy of trade analysis calculations"""
        gen = ReportGenerator(sample_backtest_results, initial_capital=10000.0)
        
        analysis = gen._calculate_trade_analysis(gen.all_trades)
        
        # Total: 3 trades
        assert analysis['total'] == 3
        
        # Winning: 2, Losing: 1
        assert analysis['winning'] == 2
        assert analysis['losing'] == 1
        
        # Win rate: 2/3 = 66.67%
        assert analysis['win_rate'] == pytest.approx(66.67, abs=0.01)
        
        # Avg win: (100 + 100) / 2 = 100
        assert analysis['avg_win'] == pytest.approx(100.0, abs=0.01)
        
        # Avg loss: -50
        assert analysis['avg_loss'] == pytest.approx(-50.0, abs=0.01)
        
        # Win/Loss ratio: 100 / 50 = 2.0
        assert analysis['win_loss_ratio'] == pytest.approx(2.0, abs=0.01)


class TestCSVFormatCompliance:
    """Test CSV format compliance with ТЗ section 4"""
    
    def test_list_of_trades_format(self, sample_backtest_results):
        """Verify List-of-trades.csv matches ТЗ 4.1 format"""
        gen = ReportGenerator(sample_backtest_results)
        csv_content = gen.generate_list_of_trades_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        header = rows[0]
        
        # ТЗ 4.1 required columns
        required_columns = [
            'Trade #', 'Type', 'Date/Time', 'Signal', 'Price USDT',
            'Position size (qty)', 'Position size (value)',
            'Net P&L USDT', 'Net P&L %',
            'Run-up USDT', 'Run-up %',
            'Drawdown USDT', 'Drawdown %',
            'Cumulative P&L USDT', 'Cumulative P&L %'
        ]
        
        for col in required_columns:
            assert col in header, f"Missing required column: {col}"
    
    def test_performance_format(self, sample_backtest_results):
        """Verify Performance.csv matches ТЗ 4.2 format"""
        gen = ReportGenerator(sample_backtest_results)
        csv_content = gen.generate_performance_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        header = rows[0]
        
        # ТЗ 4.2 required columns (All/Long/Short with USDT/%)
        assert 'All USDT' in header
        assert 'All %' in header
        assert 'Long USDT' in header
        assert 'Long %' in header
        assert 'Short USDT' in header
        assert 'Short %' in header
        
        # ТЗ 4.2 required rows
        row_labels = [row[0] for row in rows[1:]]
        required_rows = [
            'Open P&L', 'Net profit', 'Gross profit', 'Gross loss',
            'Commission paid', 'Buy & hold return',
            'Max equity run-up', 'Max equity drawdown', 'Max contracts held'
        ]
        
        for label in required_rows:
            assert label in row_labels, f"Missing required row: {label}"
    
    def test_risk_ratios_format(self, sample_backtest_results):
        """Verify Risk-performance-ratios.csv matches ТЗ 4.3 format"""
        gen = ReportGenerator(sample_backtest_results)
        csv_content = gen.generate_risk_ratios_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        row_labels = [row[0] for row in rows[1:]]
        required_rows = ['Sharpe ratio', 'Sortino ratio', 'Profit factor', 'Margin calls']
        
        for label in required_rows:
            assert label in row_labels, f"Missing required row: {label}"
    
    def test_trades_analysis_format(self, sample_backtest_results):
        """Verify Trades-analysis.csv matches ТЗ 4.4 format"""
        gen = ReportGenerator(sample_backtest_results)
        csv_content = gen.generate_trades_analysis_csv()
        
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        row_labels = [row[0] for row in rows[1:]]
        required_rows = [
            'Total trades', 'Winning trades', 'Losing trades',
            'Percent profitable', 'Avg P&L',
            'Avg winning trade', 'Avg losing trade',
            'Ratio avg win / avg loss',
            'Largest winning trade', 'Largest losing trade',
            'Avg # bars in trades'
        ]
        
        for label in required_rows:
            assert label in row_labels, f"Missing required row: {label}"

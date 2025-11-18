"""
Test that backtest_tasks transforms BacktestEngine results to Frontend format correctly.
"""

import pytest
from backend.tasks.backtest_tasks import _transform_results_for_frontend


def test_transform_results_basic():
    """Test basic transformation of BacktestEngine results to Frontend format."""
    
    # Mock BacktestEngine output
    engine_results = {
        'final_capital': 10500.0,
        'total_return': 0.05,  # 5% as decimal
        'total_trades': 10,
        'winning_trades': 6,
        'losing_trades': 4,
        'win_rate': 60.0,
        'sharpe_ratio': 1.5,
        'sortino_ratio': 2.0,
        'max_drawdown': 0.03,  # 3% as decimal
        'profit_factor': 1.8,
        'metrics': {
            'net_profit': 500.0,
            'net_profit_pct': 5.0,
            'gross_profit': 800.0,
            'gross_loss': 300.0,
            'total_commission': 15.0,
            'max_drawdown_abs': 300.0,
            'max_drawdown_pct': 3.0,
            'max_runup_abs': 600.0,
            'max_runup_pct': 6.0,
            'buy_hold_return': 200.0,
        },
        'trades': [
            {
                'entry_time': '2024-01-01T10:00:00',
                'exit_time': '2024-01-01T11:00:00',
                'entry_price': 100.0,
                'exit_price': 105.0,
                'quantity': 1.0,
                'side': 'LONG',
                'pnl': 50.0,
                'pnl_pct': 5.0,
                'commission': 1.5,
                'run_up': 60.0,
                'run_up_pct': 6.0,
                'drawdown': -10.0,
                'drawdown_pct': -1.0,
                'bars_held': 4,
                'exit_reason': 'take_profit',
            },
            {
                'entry_time': '2024-01-01T12:00:00',
                'exit_time': '2024-01-01T13:00:00',
                'entry_price': 105.0,
                'exit_price': 103.0,
                'quantity': 1.0,
                'side': 'SHORT',
                'pnl': -20.0,
                'pnl_pct': -2.0,
                'commission': 1.5,
                'run_up': 5.0,
                'run_up_pct': 0.5,
                'drawdown': -25.0,
                'drawdown_pct': -2.5,
                'bars_held': 3,
                'exit_reason': 'stop_loss',
            },
        ],
        'equity_curve': [
            {'timestamp': '2024-01-01T10:00:00', 'equity': 10000.0},
            {'timestamp': '2024-01-01T11:00:00', 'equity': 10050.0},
            {'timestamp': '2024-01-01T12:00:00', 'equity': 10050.0},
            {'timestamp': '2024-01-01T13:00:00', 'equity': 10030.0},
        ],
    }
    
    initial_capital = 10000.0
    
    # Transform
    result = _transform_results_for_frontend(engine_results, initial_capital)
    
    # Assert structure
    assert 'overview' in result
    assert 'by_side' in result
    assert 'dynamics' in result
    assert 'risk' in result
    assert 'equity' in result
    assert 'pnl_bars' in result
    
    # Check overview
    overview = result['overview']
    assert overview['net_pnl'] == 500.0
    assert overview['net_pct'] == 5.0
    assert overview['total_trades'] == 10
    assert overview['wins'] == 6
    assert overview['losses'] == 4
    assert overview['max_drawdown_abs'] == 300.0
    assert overview['max_drawdown_pct'] == 3.0
    assert overview['profit_factor'] == 1.8
    
    # Check by_side structure
    assert 'all' in result['by_side']
    assert 'long' in result['by_side']
    assert 'short' in result['by_side']
    
    # Check by_side.all
    all_stats = result['by_side']['all']
    assert all_stats['total_trades'] == 2  # 2 trades in mock data
    assert all_stats['wins'] == 1
    assert all_stats['losses'] == 1
    assert all_stats['win_rate'] == 50.0
    assert all_stats['avg_pl'] == 15.0  # (50 - 20) / 2
    
    # Check by_side.long
    long_stats = result['by_side']['long']
    assert long_stats['total_trades'] == 1
    assert long_stats['wins'] == 1
    assert long_stats['losses'] == 0
    assert long_stats['win_rate'] == 100.0
    assert long_stats['avg_pl'] == 50.0
    
    # Check by_side.short
    short_stats = result['by_side']['short']
    assert short_stats['total_trades'] == 1
    assert short_stats['wins'] == 0
    assert short_stats['losses'] == 1
    assert short_stats['win_rate'] == 0.0
    assert short_stats['avg_pl'] == -20.0
    
    # Check dynamics.all
    all_dynamics = result['dynamics']['all']
    assert all_dynamics['net_abs'] == 30.0  # 50 - 20
    assert all_dynamics['net_pct'] == 0.3  # 30 / 10000 * 100
    assert all_dynamics['gross_profit_abs'] == 50.0
    assert all_dynamics['gross_loss_abs'] == 20.0
    assert all_dynamics['fees_abs'] == 3.0  # 1.5 + 1.5
    assert all_dynamics['max_runup_abs'] == 60.0
    assert all_dynamics['max_drawdown_abs'] == 25.0  # abs(min(-10, -25))
    assert all_dynamics['buyhold_abs'] == 200.0
    
    # Check risk
    risk = result['risk']
    assert risk['sharpe'] == 1.5
    assert risk['sortino'] == 2.0
    assert risk['profit_factor'] == 1.8
    
    # Check equity
    equity = result['equity']
    assert len(equity) == 4
    assert equity[0]['time'] == '2024-01-01T10:00:00'
    assert equity[0]['equity'] == 10000.0
    assert equity[3]['time'] == '2024-01-01T13:00:00'
    assert equity[3]['equity'] == 10030.0
    
    # Check pnl_bars
    pnl_bars = result['pnl_bars']
    assert len(pnl_bars) == 4
    assert pnl_bars[0]['pnl'] == 0.0  # 10000 - 10000
    assert pnl_bars[1]['pnl'] == 50.0  # 10050 - 10000
    assert pnl_bars[3]['pnl'] == 30.0  # 10030 - 10000


def test_transform_results_empty():
    """Test transformation with no trades."""
    
    engine_results = {
        'final_capital': 10000.0,
        'total_return': 0.0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0.0,
        'sharpe_ratio': 0.0,
        'sortino_ratio': 0.0,
        'max_drawdown': 0.0,
        'profit_factor': 0.0,
        'metrics': {},
        'trades': [],
        'equity_curve': [],
    }
    
    result = _transform_results_for_frontend(engine_results, 10000.0)
    
    # Should have all sections with zero values
    assert result['overview']['total_trades'] == 0
    assert result['by_side']['all']['total_trades'] == 0
    assert result['by_side']['long']['total_trades'] == 0
    assert result['by_side']['short']['total_trades'] == 0
    assert result['dynamics']['all']['net_abs'] == 0.0
    assert result['equity'] == []
    assert result['pnl_bars'] == []


def test_transform_results_only_long_trades():
    """Test transformation with only LONG trades."""
    
    engine_results = {
        'final_capital': 10100.0,
        'total_return': 0.01,
        'total_trades': 2,
        'winning_trades': 2,
        'losing_trades': 0,
        'win_rate': 100.0,
        'sharpe_ratio': 2.0,
        'sortino_ratio': 3.0,
        'max_drawdown': 0.0,
        'profit_factor': 999.0,
        'metrics': {
            'net_profit': 100.0,
            'net_profit_pct': 1.0,
            'gross_profit': 100.0,
            'gross_loss': 0.0,
        },
        'trades': [
            {
                'side': 'LONG',
                'pnl': 50.0,
                'pnl_pct': 0.5,
                'commission': 1.0,
                'run_up': 60.0,
                'run_up_pct': 0.6,
                'drawdown': 0.0,
                'drawdown_pct': 0.0,
                'bars_held': 5,
                'entry_time': '2024-01-01T10:00:00',
                'exit_time': '2024-01-01T11:00:00',
                'entry_price': 100.0,
                'exit_price': 105.0,
                'quantity': 1.0,
            },
            {
                'side': 'LONG',
                'pnl': 50.0,
                'pnl_pct': 0.5,
                'commission': 1.0,
                'run_up': 60.0,
                'run_up_pct': 0.6,
                'drawdown': 0.0,
                'drawdown_pct': 0.0,
                'bars_held': 5,
                'entry_time': '2024-01-02T10:00:00',
                'exit_time': '2024-01-02T11:00:00',
                'entry_price': 105.0,
                'exit_price': 110.0,
                'quantity': 1.0,
            },
        ],
        'equity_curve': [],
    }
    
    result = _transform_results_for_frontend(engine_results, 10000.0)
    
    # All trades should be in 'all' and 'long', none in 'short'
    assert result['by_side']['all']['total_trades'] == 2
    assert result['by_side']['long']['total_trades'] == 2
    assert result['by_side']['short']['total_trades'] == 0
    
    assert result['by_side']['long']['wins'] == 2
    assert result['by_side']['long']['win_rate'] == 100.0
    
    assert result['dynamics']['long']['net_abs'] == 100.0
    assert result['dynamics']['short']['net_abs'] == 0.0


def test_transform_results_only_short_trades():
    """Test transformation with only SHORT trades."""
    
    engine_results = {
        'final_capital': 10100.0,
        'total_return': 0.01,
        'total_trades': 1,
        'winning_trades': 1,
        'losing_trades': 0,
        'win_rate': 100.0,
        'sharpe_ratio': 2.0,
        'sortino_ratio': 3.0,
        'max_drawdown': 0.0,
        'profit_factor': 999.0,
        'metrics': {
            'net_profit': 100.0,
            'net_profit_pct': 1.0,
        },
        'trades': [
            {
                'side': 'SHORT',
                'pnl': 100.0,
                'pnl_pct': 1.0,
                'commission': 2.0,
                'run_up': 120.0,
                'run_up_pct': 1.2,
                'drawdown': -10.0,
                'drawdown_pct': -0.1,
                'bars_held': 10,
                'entry_time': '2024-01-01T10:00:00',
                'exit_time': '2024-01-01T11:00:00',
                'entry_price': 100.0,
                'exit_price': 95.0,
                'quantity': 1.0,
            },
        ],
        'equity_curve': [],
    }
    
    result = _transform_results_for_frontend(engine_results, 10000.0)
    
    # All trades should be in 'all' and 'short', none in 'long'
    assert result['by_side']['all']['total_trades'] == 1
    assert result['by_side']['long']['total_trades'] == 0
    assert result['by_side']['short']['total_trades'] == 1
    
    assert result['by_side']['short']['wins'] == 1
    assert result['by_side']['short']['win_rate'] == 100.0
    
    assert result['dynamics']['short']['net_abs'] == 100.0
    assert result['dynamics']['long']['net_abs'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

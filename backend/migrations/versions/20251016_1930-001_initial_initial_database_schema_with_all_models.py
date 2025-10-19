"""Initial database schema with all models

Revision ID: 001_initial
Revises: 
Create Date: 2025-10-16 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create strategies table
    op.create_table('strategies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy_type', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_strategies_active', 'strategies', ['is_active'], unique=False)
    op.create_index('idx_strategies_name', 'strategies', ['name'], unique=False)
    op.create_index('idx_strategies_type', 'strategies', ['strategy_type'], unique=False)
    op.create_index(op.f('ix_strategies_id'), 'strategies', ['id'], unique=False)

    # Create backtests table
    op.create_table('backtests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('initial_capital', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('leverage', sa.Integer(), nullable=True),
        sa.Column('commission', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('final_capital', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('total_return', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('losing_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('sortino_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('calmar_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('max_drawdown_duration', sa.Integer(), nullable=True),
        sa.Column('profit_factor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('avg_trade_return', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('avg_win', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('avg_loss', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('largest_win', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('largest_loss', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('avg_trade_duration', sa.Integer(), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('results', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('commission >= 0 AND commission < 1', name='valid_commission'),
        sa.CheckConstraint('initial_capital > 0', name='positive_capital'),
        sa.CheckConstraint('leverage >= 1 AND leverage <= 100', name='valid_leverage'),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_backtests_created_at', 'backtests', ['created_at'], unique=False)
    op.create_index('idx_backtests_performance', 'backtests', ['sharpe_ratio', 'total_return'], unique=False)
    op.create_index('idx_backtests_status', 'backtests', ['status'], unique=False)
    op.create_index('idx_backtests_strategy_id', 'backtests', ['strategy_id'], unique=False)
    op.create_index('idx_backtests_symbol', 'backtests', ['symbol'], unique=False)
    op.create_index(op.f('ix_backtests_id'), 'backtests', ['id'], unique=False)

    # Create trades table
    op.create_table('trades',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('backtest_id', sa.Integer(), nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('exit_price', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('position_size', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('pnl', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('pnl_pct', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('commission', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('exit_reason', sa.String(length=50), nullable=True),
        sa.Column('meta', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("side IN ('LONG', 'SHORT')", name='valid_side'),
        sa.CheckConstraint('position_size > 0', name='positive_position_size'),
        sa.CheckConstraint('quantity > 0', name='positive_quantity'),
        sa.ForeignKeyConstraint(['backtest_id'], ['backtests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trades_backtest_id', 'trades', ['backtest_id'], unique=False)
    op.create_index('idx_trades_entry_time', 'trades', ['entry_time'], unique=False)
    op.create_index('idx_trades_exit_reason', 'trades', ['exit_reason'], unique=False)
    op.create_index('idx_trades_side', 'trades', ['side'], unique=False)
    op.create_index(op.f('ix_trades_id'), 'trades', ['id'], unique=False)

    # Create optimizations table
    op.create_table('optimizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('optimization_type', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('param_ranges', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('metric', sa.String(length=50), nullable=True),
        sa.Column('initial_capital', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('total_combinations', sa.Integer(), nullable=True),
        sa.Column('completed_combinations', sa.Integer(), nullable=True),
        sa.Column('best_params', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('best_score', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('results', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_optimizations_created_at', 'optimizations', ['created_at'], unique=False)
    op.create_index('idx_optimizations_metric', 'optimizations', ['metric', 'best_score'], unique=False)
    op.create_index('idx_optimizations_status', 'optimizations', ['status'], unique=False)
    op.create_index('idx_optimizations_strategy_id', 'optimizations', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_optimizations_id'), 'optimizations', ['id'], unique=False)

    # Create optimization_results table
    op.create_table('optimization_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('optimization_id', sa.Integer(), nullable=False),
        sa.Column('params', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('total_return', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('sortino_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('profit_factor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('win_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('score', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('metrics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['optimization_id'], ['optimizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_optimization_results_optimization_id', 'optimization_results', ['optimization_id'], unique=False)
    op.create_index('idx_optimization_results_score', 'optimization_results', ['score'], unique=False)
    op.create_index(op.f('ix_optimization_results_id'), 'optimization_results', ['id'], unique=False)

    # Create market_data table
    op.create_table('market_data',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('high', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('low', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('close', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('volume', sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column('quote_volume', sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column('trades_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_market_data_symbol_timeframe', 'market_data', ['symbol', 'timeframe'], unique=False)
    op.create_index('idx_market_data_timestamp', 'market_data', ['timestamp'], unique=False)
    op.create_index('idx_market_data_unique', 'market_data', ['symbol', 'timeframe', 'timestamp'], unique=True)
    op.create_index(op.f('ix_market_data_id'), 'market_data', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('market_data')
    op.drop_table('optimization_results')
    op.drop_table('optimizations')
    op.drop_table('trades')
    op.drop_table('backtests')
    op.drop_table('strategies')

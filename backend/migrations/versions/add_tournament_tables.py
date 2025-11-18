"""
Alembic migration: Add tournament tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_tournament_tables'
down_revision = 'add_reasoning_traces'  # Previous migration
branch_labels = None
depends_on = None


def upgrade():
    """Create tournament tables"""
    
    # Create tournaments table
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.String(length=100), nullable=False),
        sa.Column('tournament_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 
                                    name='tournamentstatusenum'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_participants', sa.Integer(), nullable=True),
        sa.Column('successful_backtests', sa.Integer(), nullable=True),
        sa.Column('failed_backtests', sa.Integer(), nullable=True),
        sa.Column('winner_id', sa.String(length=100), nullable=True),
        sa.Column('winner_name', sa.String(length=255), nullable=True),
        sa.Column('winner_score', sa.Float(), nullable=True),
        sa.Column('scoring_weights', sa.JSON(), nullable=True),
        sa.Column('max_workers', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='Tournament competitions between trading strategies'
    )
    
    # Indexes for tournaments
    op.create_index('ix_tournaments_tournament_id', 'tournaments', ['tournament_id'], unique=True)
    op.create_index('ix_tournaments_status', 'tournaments', ['status'])
    op.create_index('ix_tournaments_started_at', 'tournaments', ['started_at'])
    
    # Create tournament_participants table
    op.create_table(
        'tournament_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.String(length=100), nullable=False),
        sa.Column('strategy_name', sa.String(length=255), nullable=False),
        sa.Column('strategy_code', sa.Text(), nullable=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('sortino_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('profit_factor', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('losing_trades', sa.Integer(), nullable=True),
        sa.Column('avg_win', sa.Float(), nullable=True),
        sa.Column('avg_loss', sa.Float(), nullable=True),
        sa.Column('volatility', sa.Float(), nullable=True),
        sa.Column('var_95', sa.Float(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('backtest_duration', sa.Float(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Tournament participants with backtest results'
    )
    
    # Indexes for tournament_participants
    op.create_index('ix_tournament_participants_tournament_id', 'tournament_participants', ['tournament_id'])
    op.create_index('ix_tournament_participants_strategy_id', 'tournament_participants', ['strategy_id'])
    op.create_index('ix_tournament_participants_rank', 'tournament_participants', ['rank'])
    op.create_index('ix_tournament_participants_final_score', 'tournament_participants', ['final_score'])
    
    # Create tournament_history table
    op.create_table(
        'tournament_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.String(length=100), nullable=False),
        sa.Column('strategy_name', sa.String(length=255), nullable=False),
        sa.Column('total_tournaments', sa.Integer(), nullable=True),
        sa.Column('total_wins', sa.Integer(), nullable=True),
        sa.Column('total_top3', sa.Integer(), nullable=True),
        sa.Column('total_top10', sa.Integer(), nullable=True),
        sa.Column('avg_score', sa.Float(), nullable=True),
        sa.Column('avg_rank', sa.Float(), nullable=True),
        sa.Column('best_score', sa.Float(), nullable=True),
        sa.Column('worst_score', sa.Float(), nullable=True),
        sa.Column('avg_return', sa.Float(), nullable=True),
        sa.Column('avg_sharpe', sa.Float(), nullable=True),
        sa.Column('avg_win_rate', sa.Float(), nullable=True),
        sa.Column('recent_scores', sa.JSON(), nullable=True),
        sa.Column('recent_ranks', sa.JSON(), nullable=True),
        sa.Column('first_tournament_at', sa.DateTime(), nullable=True),
        sa.Column('last_tournament_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='Aggregated tournament history per strategy'
    )
    
    # Indexes for tournament_history
    op.create_index('ix_tournament_history_strategy_id', 'tournament_history', ['strategy_id'], unique=True)
    op.create_index('ix_tournament_history_avg_score', 'tournament_history', ['avg_score'])
    op.create_index('ix_tournament_history_total_wins', 'tournament_history', ['total_wins'])


def downgrade():
    """Drop tournament tables"""
    
    # Drop indexes
    op.drop_index('ix_tournament_history_total_wins', 'tournament_history')
    op.drop_index('ix_tournament_history_avg_score', 'tournament_history')
    op.drop_index('ix_tournament_history_strategy_id', 'tournament_history')
    
    op.drop_index('ix_tournament_participants_final_score', 'tournament_participants')
    op.drop_index('ix_tournament_participants_rank', 'tournament_participants')
    op.drop_index('ix_tournament_participants_strategy_id', 'tournament_participants')
    op.drop_index('ix_tournament_participants_tournament_id', 'tournament_participants')
    
    op.drop_index('ix_tournaments_started_at', 'tournaments')
    op.drop_index('ix_tournaments_status', 'tournaments')
    op.drop_index('ix_tournaments_tournament_id', 'tournaments')
    
    # Drop tables
    op.drop_table('tournament_history')
    op.drop_table('tournament_participants')
    op.drop_table('tournaments')
    
    # Drop enum
    op.execute('DROP TYPE IF EXISTS tournamentstatusenum')

"""
Alembic migration: Add reasoning traces tables for Knowledge Base

Revision ID: add_reasoning_traces
Revises: convert_timestamps_to_timestamptz
Create Date: 2025-11-01 14:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_reasoning_traces'
down_revision = '1a2b3c4d5e6f_convert_timestamps_to_timestamptz'  # Previous migration
branch_labels = None
depends_on = None


def upgrade():
    """Add reasoning traces tables"""
    
    # reasoning_traces table
    op.create_table(
        'reasoning_traces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('parent_request_id', sa.String(length=36), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('agent', sa.String(length=20), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('execution_time', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for reasoning_traces
    op.create_index('ix_reasoning_traces_request_id', 'reasoning_traces', ['request_id'], unique=True)
    op.create_index('ix_reasoning_traces_parent_request_id', 'reasoning_traces', ['parent_request_id'])
    op.create_index('ix_reasoning_traces_task_type', 'reasoning_traces', ['task_type'])
    op.create_index('ix_reasoning_traces_agent', 'reasoning_traces', ['agent'])
    op.create_index('ix_reasoning_traces_created_at', 'reasoning_traces', ['created_at'])
    
    # chain_of_thought table
    op.create_table(
        'chain_of_thought',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(length=100), nullable=False),
        sa.Column('thought', sa.Text(), nullable=False),
        sa.Column('decision', sa.String(length=200), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trace_id'], ['reasoning_traces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Index for chain_of_thought
    op.create_index('ix_chain_of_thought_trace_id', 'chain_of_thought', ['trace_id'])
    
    # strategy_evolution table
    op.create_table(
        'strategy_evolution',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('parent_version', sa.Integer(), nullable=True),
        sa.Column('changes_description', sa.Text(), nullable=True),
        sa.Column('changes_diff', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('reasoning_trace_id', sa.Integer(), nullable=True),
        sa.Column('performance_before', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('performance_after', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('performance_delta', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reasoning_trace_id'], ['reasoning_traces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for strategy_evolution
    op.create_index('ix_strategy_evolution_strategy_id', 'strategy_evolution', ['strategy_id'])
    op.create_index('ix_strategy_evolution_created_at', 'strategy_evolution', ['created_at'])
    
    # reasoning_knowledge_base table
    op.create_table(
        'reasoning_knowledge_base',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pattern_type', sa.String(length=50), nullable=False),
        sa.Column('task_category', sa.String(length=50), nullable=False),
        sa.Column('pattern_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('example_trace_id', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_performance_improvement', sa.Float(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['example_trace_id'], ['reasoning_traces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for reasoning_knowledge_base
    op.create_index('ix_reasoning_knowledge_base_pattern_type', 'reasoning_knowledge_base', ['pattern_type'])
    op.create_index('ix_reasoning_knowledge_base_task_category', 'reasoning_knowledge_base', ['task_category'])
    op.create_index('ix_reasoning_knowledge_base_created_at', 'reasoning_knowledge_base', ['created_at'])


def downgrade():
    """Drop reasoning traces tables"""
    op.drop_table('reasoning_knowledge_base')
    op.drop_table('strategy_evolution')
    op.drop_table('chain_of_thought')
    op.drop_table('reasoning_traces')

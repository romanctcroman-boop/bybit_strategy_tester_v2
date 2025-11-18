"""Add reasoning trace tables for Knowledge Base

Revision ID: add_reasoning_kb_001
Revises: 
Create Date: 2025-11-01 00:00:00.000000

Description:
    Creates tables for storing AI reasoning chains, chain-of-thought steps,
    and strategy evolution tracking. Part of Quick Win #1 (Knowledge Base).

Tables:
    - reasoning_traces: Main reasoning trace records
    - chain_of_thought: Step-by-step reasoning process
    - strategy_evolution: Strategy version history and evolution

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_reasoning_kb_001'
down_revision = None  # Update this with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """
    Create reasoning trace tables for Knowledge Base.
    """
    
    # =========================================================================
    # Table 1: reasoning_traces
    # =========================================================================
    op.create_table(
        'reasoning_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('agent_model', sa.String(length=100), nullable=True),
        sa.Column('task_type', sa.String(length=100), nullable=False),
        sa.Column('input_prompt', sa.Text(), nullable=False),
        sa.Column('reasoning_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('final_conclusion', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('tokens_input', sa.Integer(), nullable=True),
        sa.Column('tokens_output', sa.Integer(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=True, default=True),
        sa.Column('context_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, default='completed'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='AI reasoning traces for explainability and audit'
    )
    
    # Indexes for reasoning_traces
    op.create_index('ix_reasoning_traces_session_id', 'reasoning_traces', ['session_id'])
    op.create_index('ix_reasoning_traces_request_id', 'reasoning_traces', ['request_id'])
    op.create_index('ix_reasoning_traces_agent_type', 'reasoning_traces', ['agent_type'])
    op.create_index('ix_reasoning_traces_task_type', 'reasoning_traces', ['task_type'])
    op.create_index('ix_reasoning_traces_status', 'reasoning_traces', ['status'])
    op.create_index('ix_reasoning_traces_created_at', 'reasoning_traces', ['created_at'])
    op.create_index('ix_reasoning_traces_session_agent', 'reasoning_traces', ['session_id', 'agent_type'])
    op.create_index('ix_reasoning_traces_task_status', 'reasoning_traces', ['task_type', 'status'])
    op.create_index(
        'ix_reasoning_traces_created_at_desc', 
        'reasoning_traces', 
        [sa.text('created_at DESC')]
    )
    
    # =========================================================================
    # Table 2: chain_of_thought
    # =========================================================================
    op.create_table(
        'chain_of_thought',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reasoning_trace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('thought_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intermediate_conclusion', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=True),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['reasoning_trace_id'], 
            ['reasoning_traces.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        comment='Step-by-step reasoning process for detailed analysis'
    )
    
    # Indexes for chain_of_thought
    op.create_index('ix_chain_of_thought_reasoning_trace_id', 'chain_of_thought', ['reasoning_trace_id'])
    op.create_index('ix_chain_of_thought_trace_step', 'chain_of_thought', ['reasoning_trace_id', 'step_number'])
    
    # =========================================================================
    # Table 3: strategy_evolution
    # =========================================================================
    op.create_table(
        'strategy_evolution',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('strategy_id', sa.String(length=100), nullable=False),
        sa.Column('strategy_name', sa.String(length=200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('parent_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('strategy_code', sa.Text(), nullable=True),
        sa.Column('strategy_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('changes_description', sa.Text(), nullable=False),
        sa.Column('reasoning_trace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performance_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('performance_delta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('experiment_id', sa.String(length=100), nullable=True),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_production', sa.Boolean(), nullable=True, default=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['parent_version_id'], 
            ['strategy_evolution.id'],
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['reasoning_trace_id'], 
            ['reasoning_traces.id'],
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        comment='Track strategy evolution and performance improvements'
    )
    
    # Indexes for strategy_evolution
    op.create_index('ix_strategy_evolution_strategy_id', 'strategy_evolution', ['strategy_id'])
    op.create_index('ix_strategy_evolution_parent_version_id', 'strategy_evolution', ['parent_version_id'])
    op.create_index('ix_strategy_evolution_reasoning_trace_id', 'strategy_evolution', ['reasoning_trace_id'])
    op.create_index('ix_strategy_evolution_experiment_id', 'strategy_evolution', ['experiment_id'])
    op.create_index('ix_strategy_evolution_is_active', 'strategy_evolution', ['is_active'])
    op.create_index('ix_strategy_evolution_is_production', 'strategy_evolution', ['is_production'])
    op.create_index('ix_strategy_evolution_created_at', 'strategy_evolution', ['created_at'])
    op.create_index('ix_strategy_evolution_id_version', 'strategy_evolution', ['strategy_id', 'version'])
    op.create_index('ix_strategy_evolution_active', 'strategy_evolution', ['is_active', 'is_production'])
    
    print("✅ Knowledge Base tables created successfully!")


def downgrade():
    """
    Drop reasoning trace tables.
    WARNING: This will delete all reasoning trace data!
    """
    
    # Drop tables in reverse order (due to foreign keys)
    op.drop_table('strategy_evolution')
    op.drop_table('chain_of_thought')
    op.drop_table('reasoning_traces')
    
    print("⚠️ Knowledge Base tables dropped!")

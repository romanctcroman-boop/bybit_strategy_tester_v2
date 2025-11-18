"""Add Saga Pattern tables (checkpoints and audit logs)

Revision ID: add_saga_tables
Revises: add_reasoning_traces
Create Date: 2025-11-05 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_saga_tables'
down_revision = 'add_reasoning_traces'
branch_labels = None
depends_on = None


def upgrade():
    """Add Saga Pattern tables"""
    
    # saga_checkpoints table
    op.create_table(
        'saga_checkpoints',
        sa.Column('saga_id', sa.String(length=255), nullable=False, comment='Unique saga identifier (UUID)'),
        sa.Column('state', sa.String(length=50), nullable=False, comment='Current saga state (IDLE, RUNNING, COMPENSATING, COMPLETED, FAILED, ABORTED)'),
        sa.Column('current_step_index', sa.Integer(), nullable=False, server_default='0', comment='Index of current step (0-based)'),
        sa.Column('completed_steps', sa.JSON(), nullable=False, server_default='[]', comment='List of successfully completed step names'),
        sa.Column('compensated_steps', sa.JSON(), nullable=False, server_default='[]', comment='List of compensated step names (reverse order)'),
        sa.Column('context', sa.JSON(), nullable=False, server_default='{}', comment='Saga context data (propagated through steps)'),
        sa.Column('error', sa.Text(), nullable=True, comment='Error message if saga failed'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, comment='Saga execution start time'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='Last checkpoint update time'),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='0', comment='Total number of steps in saga'),
        sa.Column('retries', sa.Integer(), nullable=False, server_default='0', comment='Number of retry attempts'),
        sa.PrimaryKeyConstraint('saga_id'),
        comment='Persistent storage for saga execution state (enables recovery after crashes)'
    )
    
    # Indexes for saga_checkpoints
    op.create_index('ix_saga_checkpoints_saga_id', 'saga_checkpoints', ['saga_id'])
    op.create_index('ix_saga_checkpoints_state', 'saga_checkpoints', ['state'])
    op.create_index('ix_saga_checkpoints_updated_at', 'saga_checkpoints', ['updated_at'])
    
    # saga_audit_logs table
    op.create_table(
        'saga_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('saga_id', sa.String(length=255), nullable=False, comment='Saga identifier (links to saga_checkpoints)'),
        sa.Column('event_type', sa.String(length=50), nullable=False, comment='Event type (saga_start, step_start, step_complete, step_failed, step_retry, compensation_start, compensation_complete, saga_complete, saga_failed)'),
        sa.Column('step_name', sa.String(length=255), nullable=True, comment='Step name (null for saga-level events)'),
        sa.Column('step_index', sa.Integer(), nullable=True, comment='Step index (0-based, null for saga-level events)'),
        sa.Column('event_data', sa.JSON(), nullable=True, comment='Event-specific data (varies by event_type)'),
        sa.Column('context_snapshot', sa.JSON(), nullable=True, comment='Saga context at time of event (for forensic analysis)'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message (for failed events)'),
        sa.Column('error_stack_trace', sa.Text(), nullable=True, comment='Stack trace (for debugging)'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, comment='Event timestamp (UTC)'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Event duration in milliseconds (for step_complete events)'),
        sa.Column('user_id', sa.String(length=255), nullable=True, comment='User who initiated saga (for audit trail)'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='IP address of originating request (IPv4/IPv6)'),
        sa.Column('saga_state_before', sa.String(length=50), nullable=True, comment='Saga state before event'),
        sa.Column('saga_state_after', sa.String(length=50), nullable=True, comment='Saga state after event'),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0', comment='Retry attempt number (for step_retry events)'),
        sa.PrimaryKeyConstraint('id'),
        comment='Immutable audit trail for saga events (compliance-ready, append-only)'
    )
    
    # Indexes for saga_audit_logs
    op.create_index('ix_saga_audit_logs_saga_id', 'saga_audit_logs', ['saga_id'])
    op.create_index('ix_saga_audit_logs_event_type', 'saga_audit_logs', ['event_type'])
    op.create_index('ix_saga_audit_logs_step_name', 'saga_audit_logs', ['step_name'])
    op.create_index('ix_saga_audit_logs_timestamp', 'saga_audit_logs', ['timestamp'])
    op.create_index('ix_saga_audit_logs_user_id', 'saga_audit_logs', ['user_id'])
    
    # Composite indexes for common queries
    op.create_index('ix_saga_audit_saga_timestamp', 'saga_audit_logs', ['saga_id', 'timestamp'])
    op.create_index('ix_saga_audit_event_timestamp', 'saga_audit_logs', ['event_type', 'timestamp'])
    op.create_index('ix_saga_audit_user_timestamp', 'saga_audit_logs', ['user_id', 'timestamp'])


def downgrade():
    """Remove Saga Pattern tables"""
    
    # Drop indexes
    op.drop_index('ix_saga_audit_user_timestamp', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_event_timestamp', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_saga_timestamp', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_logs_user_id', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_logs_timestamp', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_logs_step_name', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_logs_event_type', 'saga_audit_logs')
    op.drop_index('ix_saga_audit_logs_saga_id', 'saga_audit_logs')
    
    op.drop_index('ix_saga_checkpoints_updated_at', 'saga_checkpoints')
    op.drop_index('ix_saga_checkpoints_state', 'saga_checkpoints')
    op.drop_index('ix_saga_checkpoints_saga_id', 'saga_checkpoints')
    
    # Drop tables
    op.drop_table('saga_audit_logs')
    op.drop_table('saga_checkpoints')

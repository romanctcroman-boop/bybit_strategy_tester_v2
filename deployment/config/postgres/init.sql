-- ==============================================================================
-- PostgreSQL Initialization Script
-- ==============================================================================
-- This script runs once when the PostgreSQL container is first created.
-- It sets up the initial database structure and permissions.
-- ==============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create application user with limited privileges
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bybit_app') THEN
        CREATE ROLE bybit_app WITH LOGIN PASSWORD 'app_password_change_me';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT CONNECT ON DATABASE bybit_prod TO bybit_app;
GRANT USAGE ON SCHEMA public TO bybit_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bybit_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bybit_app;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bybit_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO bybit_app;

-- Create read-only user for reporting
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bybit_readonly') THEN
        CREATE ROLE bybit_readonly WITH LOGIN PASSWORD 'readonly_password_change_me';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE bybit_prod TO bybit_readonly;
GRANT USAGE ON SCHEMA public TO bybit_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bybit_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO bybit_readonly;

-- Performance tuning for PostgreSQL
-- These settings are for a server with ~4GB RAM

-- Memory settings (adjust based on available RAM)
-- shared_buffers = 1GB
-- effective_cache_size = 3GB
-- maintenance_work_mem = 256MB
-- work_mem = 16MB

-- Logging settings
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1 second
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;

-- Checkpoint settings
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '64MB';

-- Connection settings
ALTER SYSTEM SET max_connections = 200;

-- Vacuum settings
ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.1;
ALTER SYSTEM SET autovacuum_analyze_scale_factor = 0.05;

SELECT pg_reload_conf();

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully!';
END
$$;

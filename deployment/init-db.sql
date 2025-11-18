-- Database initialization script for Docker Compose
-- This script runs when PostgreSQL container starts for the first time

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create additional schemas if needed
-- CREATE SCHEMA IF NOT EXISTS analytics;
-- CREATE SCHEMA IF NOT EXISTS monitoring;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE mcp_db TO mcp_user;

-- Set default timezone
SET timezone = 'UTC';

-- Log initialization
DO $$ 
BEGIN
    RAISE NOTICE '✅ Database initialized successfully';
    RAISE NOTICE '📊 Database: mcp_db';
    RAISE NOTICE '👤 User: mcp_user';
    RAISE NOTICE '🕐 Timezone: UTC';
END $$;

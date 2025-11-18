/**
 * PM2 Ecosystem Configuration
 * 
 * Production-ready process management for automation system
 * 
 * Setup:
 * 1. npm install pm2 -g
 * 2. pm2 start ecosystem.config.js
 * 3. pm2 save
 * 4. pm2 startup (autostart on boot)
 * 
 * Management:
 * - pm2 status          # Check process status
 * - pm2 logs           # View logs
 * - pm2 restart all    # Restart all processes
 * - pm2 stop all       # Stop all processes
 * - pm2 delete all     # Remove all processes
 */

module.exports = {
  apps: [
    {
      name: 'test-watcher',
      script: 'D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe',
      args: ['D:\\bybit_strategy_tester_v2\\automation\\task1_test_watcher\\test_watcher.py'],
      cwd: 'D:\\bybit_strategy_tester_v2',
      interpreter: 'none',
      
      // Auto-restart configuration
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 5000,
      
      // Memory management
      max_memory_restart: '512M',
      
      // Logging
      error_file: './logs/pm2_test_watcher_error.log',
      out_file: './logs/pm2_test_watcher_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      
      // Environment
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      
      // Monitoring
      watch: false,
      ignore_watch: ['node_modules', 'logs', '.git'],
      
      // Advanced
      kill_timeout: 5000,
      listen_timeout: 3000,
      shutdown_with_message: false
    },
    
    {
      name: 'audit-agent',
      script: 'D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe',
      args: ['D:\\bybit_strategy_tester_v2\\automation\\task3_audit_agent\\audit_agent.py'],
      cwd: 'D:\\bybit_strategy_tester_v2',
      interpreter: 'none',
      
      // Auto-restart configuration
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 5000,
      
      // Memory management
      max_memory_restart: '512M',
      
      // Logging
      error_file: './logs/pm2_audit_agent_error.log',
      out_file: './logs/pm2_audit_agent_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      
      // Environment
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      
      // Monitoring
      watch: false,
      ignore_watch: ['node_modules', 'logs', '.git'],
      
      // Advanced
      kill_timeout: 5000,
      listen_timeout: 3000,
      shutdown_with_message: false,
      
      // Schedule: restart once per day at 3 AM (optional)
      cron_restart: '0 3 * * *'
    },
    
    {
      name: 'health-check',
      script: 'D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe',
      args: ['D:\\bybit_strategy_tester_v2\\health_check.py', '--json'],
      cwd: 'D:\\bybit_strategy_tester_v2',
      interpreter: 'none',
      
      // Run every 5 minutes via cron
      cron_restart: '*/5 * * * *',
      autorestart: false,
      max_restarts: 3,
      
      // Logging
      error_file: './logs/pm2_health_check_error.log',
      out_file: './logs/pm2_health_check_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      
      // Environment
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      
      // Monitoring
      watch: false,
      kill_timeout: 3000,
      listen_timeout: 2000
    }
  ]
};

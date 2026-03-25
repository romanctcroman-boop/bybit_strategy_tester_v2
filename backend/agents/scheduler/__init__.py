"""
Agent Task Scheduler — Periodic & Cron-like Job Scheduling.

Provides autonomous scheduling for:
- Periodic backtesting (e.g. every hour)
- Nightly strategy evolution runs
- Market data refresh
- System health checks
- Custom agent tasks

Uses asyncio-based scheduling (no external dependency on APScheduler).

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""

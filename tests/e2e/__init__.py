"""
E2E Integration Tests

End-to-end integration tests for the complete system workflow.

Tests cover:
- Strategy creation → Backtest → Results verification
- Optimization workflows
- Template-based strategy creation
- CSV export functionality
- Error handling and edge cases

These tests require:
- Running PostgreSQL database
- Running Redis instance
- Proper environment variables configured
- Network access to Bybit API (for data fetching)

Run with: pytest tests/e2e/ -v
Run slow tests: pytest tests/e2e/ -v -m slow
"""

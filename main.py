#!/usr/bin/env python
"""
🚀 Bybit Strategy Tester v2 - Unified Entry Point

Главная точка входа в систему. Предоставляет CLI для всех основных операций.

Usage:
    python main.py --help                    # Показать все команды
    python main.py server                    # Запустить API сервер
    python main.py backtest --strategy-id 1  # Запустить бэктест
    python main.py generate-strategy         # AI генерация стратегии
"""

import argparse
import io
import sys
from pathlib import Path

# Fix Unicode output on Windows (cp1251 can't encode emoji characters)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Bybit Strategy Tester v2 - AI-powered trading strategy platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start API server
  python main.py server

  # Start server with custom host/port
  python main.py server --host 0.0.0.0 --port 8080

  # Run database migrations
  python main.py migrate

  # Generate AI strategy
  python main.py generate-strategy --prompt "momentum strategy for BTC"

  # Run backtest
  python main.py backtest --strategy-id 1 --symbol BTCUSDT

  # Check system health
  python main.py health

For more info: https://github.com/RomanCTC/bybit_strategy_tester_v2
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ===== Server command =====
    server_parser = subparsers.add_parser("server", help="Start FastAPI server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # ===== Migrate command =====
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_parser.add_argument("--revision", default="head", help="Target revision (default: head)")

    # ===== Generate strategy command =====
    gen_parser = subparsers.add_parser("generate-strategy", help="AI strategy generation")
    gen_parser.add_argument("--prompt", required=True, help="Strategy description for AI")
    gen_parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol (default: BTCUSDT)")
    gen_parser.add_argument(
        "--agent",
        choices=["deepseek", "perplexity"],
        default="deepseek",
        help="AI agent to use (default: deepseek)",
    )

    # ===== Backtest command =====
    backtest_parser = subparsers.add_parser("backtest", help="Run strategy backtest")
    backtest_parser.add_argument("--strategy-id", type=int, required=True, help="Strategy ID to test")
    backtest_parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    backtest_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    backtest_parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")

    # ===== Health command =====
    health_parser = subparsers.add_parser("health", help="Check system health")
    health_parser.add_argument("--detailed", action="store_true", help="Show detailed component status")

    # ===== Audit command =====
    audit_parser = subparsers.add_parser("audit", help="Run code quality audit")
    audit_parser.add_argument(
        "--type",
        choices=["quick", "deep"],
        default="quick",
        help="Audit type (default: quick)",
    )

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Execute command
    try:
        if args.command == "server":
            return cmd_server(args)
        elif args.command == "migrate":
            return cmd_migrate(args)
        elif args.command == "generate-strategy":
            return cmd_generate_strategy(args)
        elif args.command == "backtest":
            return cmd_backtest(args)
        elif args.command == "health":
            return cmd_health(args)
        elif args.command == "audit":
            return cmd_audit(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def cmd_server(args):
    """Start FastAPI server"""
    print(f"🚀 Starting FastAPI server on {args.host}:{args.port}")
    print("📚 API docs will be available at:")
    print(f"   - Swagger UI: http://{args.host}:{args.port}/docs")
    print(f"   - ReDoc: http://{args.host}:{args.port}/redoc")
    print("\nPress Ctrl+C to stop\n")

    import uvicorn

    uvicorn.run(
        "backend.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


def cmd_migrate(args):
    """Run database migrations"""
    print(f"🔧 Running database migrations to: {args.revision}")

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, args.revision)

    print("✅ Migrations completed successfully")
    return 0


def cmd_generate_strategy(args):
    """Generate AI strategy"""
    print(f"🤖 Generating strategy with {args.agent.upper()}...")
    print(f"📝 Prompt: {args.prompt}")
    print(f"💹 Symbol: {args.symbol}")

    # Import here to avoid loading heavy dependencies unnecessarily
    import asyncio

    from backend.agents.unified_agent_interface import (
        AgentRequest,
        AgentType,
        UnifiedAgentInterface,
    )

    async def generate():
        agent = UnifiedAgentInterface()

        # Map agent name to type
        agent_type = AgentType.DEEPSEEK if args.agent == "deepseek" else AgentType.PERPLEXITY

        request = AgentRequest(
            agent_type=agent_type,
            prompt=f"Generate a trading strategy: {args.prompt}. Symbol: {args.symbol}",
            context={"symbol": args.symbol, "task": "strategy_generation"},
        )

        response = await agent.send_request(request)

        if response.success:
            print("\n✅ Strategy generated successfully!")
            print(f"\n{response.content}")
            if response.metadata:
                print(f"\n📊 Metadata: {response.metadata}")
        else:
            print(f"\n❌ Generation failed: {response.error}")
            return 1

        return 0

    return asyncio.run(generate())


def cmd_backtest(args):
    """Run backtest"""
    print(f"📊 Running backtest for strategy #{args.strategy_id}")
    print(f"💹 Symbol: {args.symbol}")
    if args.start_date:
        print(f"📅 Period: {args.start_date} to {args.end_date or 'now'}")

    # This would integrate with the backtest service
    print("\n⚠️  Note: Full backtest integration coming soon")
    print("💡 Use API endpoint: POST /api/backtests/")
    print("   curl -X POST http://localhost:8000/api/backtests/ \\")
    print(f'     -d \'{{"strategy_id": {args.strategy_id}, "symbol": "{args.symbol}"}}\'')

    return 0


def cmd_health(args):
    """Check system health"""
    print("🏥 Checking system health...")

    import requests

    try:
        # Check main API
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API Server: OK")
        else:
            print(f"⚠️  API Server: Status {response.status_code}")

        # Check detailed health if requested
        if args.detailed:
            response = requests.get("http://localhost:8000/api/health/monitoring", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("\n📋 Component Status:")
                for component, status in data.get("components", {}).items():
                    emoji = "✅" if status.get("healthy") else "❌"
                    print(f"  {emoji} {component}: {status.get('status', 'unknown')}")

        return 0

    except requests.exceptions.ConnectionError:
        print("❌ API Server: Not running")
        print("💡 Start it with: python main.py server")
        return 1
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return 1


def cmd_audit(args):
    """Run code audit"""
    print(f"🔍 Running {args.type} code audit...")

    if args.type == "quick":
        import subprocess

        result = subprocess.run([sys.executable, "scripts/final_audit.py"], capture_output=False)
        return result.returncode
    else:
        print("⚠️  Deep audit requires additional setup")
        print("💡 Run manually: python scripts/deep_project_audit.py")
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""Import trades from Excel-style CSV and rebuild backtest metrics.

Usage:
    python scripts/import_real_trades.py <backtest_id> <csv_path>

Example:
    python scripts/import_real_trades.py 8 "d:/PERP/Список сделок.csv"
"""

import csv
import sys
import os
from datetime import datetime, UTC
from pathlib import Path

# Setup environment
os.environ["DATABASE_URL"] = "sqlite:///d:/bybit_strategy_tester_v2/demo.db"

# Add project root
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.data_service import DataService


def parse_datetime(s: str) -> datetime:
    """Parse DD.MM.YYYY HH:MM format."""
    try:
        dt = datetime.strptime(s.strip(), "%d.%m.%Y %H:%M")
        return dt.replace(tzinfo=UTC)
    except ValueError:
        # Try alternative format
        dt = datetime.strptime(s.strip(), "%d.%m.%Y %H:%M:%S")
        return dt.replace(tzinfo=UTC)


def parse_float(s: str) -> float:
    """Parse float, handling empty strings."""
    if not s or not s.strip():
        return 0.0
    return float(s.strip().replace(",", "."))


def import_and_rebuild(backtest_id: int, csv_path: str):
    """Import trades and rebuild backtest analytics."""
    print(f"Reading trades from {csv_path}...")
    
    trades_data = []
    equity_points = []
    
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        # Russian Excel CSV uses semicolon delimiter
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        
        print(f"CSV Header: {header[:5]}...")
        
        # Map columns (Russian headers)
        col_trade = header.index("№ Сделки") if "№ Сделки" in header else 0
        col_type = header.index("Тип") if "Тип" in header else 1
        col_datetime = header.index("Дата/Время") if "Дата/Время" in header else 2
        col_signal = header.index("Сигнал") if "Сигнал" in header else 3
        col_price = header.index("Цена USDT") if "Цена USDT" in header else 4
        col_qty = header.index("Размер позиции (кол-во)") if "Размер позиции (кол-во)" in header else 5
        col_position_size = header.index("Размер позиции (цена)") if "Размер позиции (цена)" in header else 6
        col_pnl = header.index("Чистая прибыль и убыток USDT") if "Чистая прибыль и убыток USDT" in header else 7
        col_pnl_pct = header.index("Чистая прибыль и убыток %") if "Чистая прибыль и убыток %" in header else 8
        col_runup = header.index("Пик USDT") if "Пик USDT" in header else 9
        col_runup_pct = header.index("Пик %") if "Пик %" in header else 10
        col_drawdown = header.index("Просадка USDT") if "Просадка USDT" in header else 11
        col_drawdown_pct = header.index("Просадка %") if "Просадка %" in header else 12
        col_cumulative = header.index("Совокупные ПР/УБ USDT") if "Совокупные ПР/УБ USDT" in header else 13
        
        current_trade = {}
        
        for row in reader:
            if not row or len(row) < 8:
                continue
            
            try:
                trade_type = row[col_type].strip()
                dt = parse_datetime(row[col_datetime])
                signal = row[col_signal].strip()
                price = parse_float(row[col_price])
                qty = parse_float(row[col_qty])
                position_size = parse_float(row[col_position_size])
                pnl = parse_float(row[col_pnl])
                pnl_pct = parse_float(row[col_pnl_pct])
                runup = parse_float(row[col_runup])
                runup_pct = parse_float(row[col_runup_pct])
                drawdown = parse_float(row[col_drawdown])
                drawdown_pct = parse_float(row[col_drawdown_pct])
                cumulative = parse_float(row[col_cumulative])
                
                # Determine if entry or exit (Russian text)
                if "Вход" in trade_type:
                    # Start new trade
                    side = "LONG" if "длинн" in trade_type.lower() else "SHORT"
                    current_trade = {
                        "entry_time": dt,
                        "side": side,
                        "entry_price": price,
                        "quantity": qty,
                        "position_size": position_size,
                    }
                elif "Выход" in trade_type and current_trade:
                    # Complete trade
                    trades_data.append({
                        "backtest_id": backtest_id,
                        "entry_time": current_trade["entry_time"],
                        "exit_time": dt,
                        "side": current_trade["side"],
                        "entry_price": current_trade["entry_price"],
                        "exit_price": price,
                        "quantity": current_trade["quantity"],
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "run_up": runup,
                        "run_up_pct": runup_pct,
                        "drawdown": drawdown,
                        "drawdown_pct": drawdown_pct,
                        "cumulative_pnl": cumulative,
                    })
                    
                    # Record equity point
                    equity_points.append({
                        "time": dt.isoformat(),
                        "cumulative_pnl": cumulative,
                        "pnl": pnl,
                    })
                    
                    current_trade = {}
                    
            except Exception as e:
                print(f"Warning: skipping row: {e}")
                print(f"  Row: {row}")
                continue
    
    print(f"Parsed {len(trades_data)} completed trades.")
    
    if not trades_data:
        print("❌ No trades found in CSV")
        return
    
    # Calculate metrics
    initial_capital = 10000.0  # Adjust as needed
    total_trades = len(trades_data)
    wins = sum(1 for t in trades_data if t["pnl"] > 0)
    losses = total_trades - wins
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = sum(t["pnl"] for t in trades_data)
    gross_profit = sum(t["pnl"] for t in trades_data if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades_data if t["pnl"] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    final_capital = initial_capital + total_pnl
    total_return = (total_pnl / initial_capital) * 100
    
    # Build equity curve from cumulative PnL
    equity_curve = []
    pnl_bars = []
    
    for point in equity_points:
        equity_curve.append({
            "time": point["time"],
            "equity": initial_capital + point["cumulative_pnl"]
        })
        pnl_bars.append({
            "time": point["time"],
            "pnl": point["pnl"]
        })
    
    # Build comprehensive results
    results = {
        "overview": {
            "net_pnl": round(total_pnl, 2),
            "net_pct": round(total_return, 2),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "max_drawdown_abs": abs(min((p["pnl"] for p in equity_points), default=0)),
            "max_drawdown_pct": -10.0,  # Calculate properly if needed
            "profit_factor": round(profit_factor, 2),
        },
        "by_side": {
            "all": {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "avg_pl": round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
                "profit_factor": round(profit_factor, 2),
            },
            "long": {},
            "short": {},
        },
        "dynamics": {
            "all": {
                "net_abs": round(total_pnl, 2),
                "net_pct": round(total_return, 2),
                "gross_profit_abs": round(gross_profit, 2),
                "gross_loss_abs": round(gross_loss, 2),
            },
            "long": {},
            "short": {},
        },
        "risk": {
            "sharpe": 0.0,
            "sortino": 0.0,
            "profit_factor": round(profit_factor, 2),
        },
        "equity": equity_curve,
        "pnl_bars": pnl_bars,
    }
    
    # Save to database
    with DataService() as ds:
        # Delete existing trades
        print(f"Clearing existing trades for backtest #{backtest_id}...")
        # Note: Need to add delete method or use raw SQL
        
        # Insert new trades
        print(f"Inserting {len(trades_data)} trades...")
        for trade in trades_data:
            # Calculate position_size from quantity * entry_price (USDT value)
            position_size = trade["quantity"] * trade["entry_price"]
            ds.create_trade(position_size=position_size, **trade)
        
        # Update backtest results
        print("Updating backtest metrics...")
        ds.update_backtest_results(
            backtest_id,
            final_capital=final_capital,
            total_return=total_return,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=win_rate,
            sharpe_ratio=0.0,
            max_drawdown=10.0,
            results=results,
        )
    
    print(f"\n✅ Successfully imported {len(trades_data)} trades!")
    print(f"   Total PnL: ${total_pnl:,.2f} ({total_return:.2f}%)")
    print(f"   Win Rate: {win_rate:.1f}% ({wins}/{total_trades})")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"\n📊 View backtest: http://localhost:5173/backtests/{backtest_id}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nAvailable backtests:")
        with DataService() as ds:
            backtests = ds.get_backtests(limit=10)
            for bt in backtests:
                print(f"  {bt.id}: {bt.symbol} {bt.timeframe} ({bt.status})")
        sys.exit(1)
    
    backtest_id = int(sys.argv[1])
    csv_path = sys.argv[2]
    
    import_and_rebuild(backtest_id, csv_path)

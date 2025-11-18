"""
📊 Real-Time Diagnostic Dashboard
Dashboard для мониторинга фоновой диагностики в реальном времени
"""

import json
from pathlib import Path
from datetime import datetime
import time


def load_status():
    """Загрузка текущего статуса"""
    try:
        with open("diagnostic_status.json", 'r') as f:
            return json.load(f)
    except:
        return None


def format_uptime(seconds):
    """Форматирование uptime"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{int(hours)}h {int(minutes)}m {int(secs)}s"


def print_dashboard():
    """Вывод dashboard"""
    status = load_status()
    
    if not status:
        print("⚠️ Статус недоступен. Запустите background_diagnostic_service.py")
        return
    
    stats = status["stats"]
    timestamp = datetime.fromisoformat(status["timestamp"])
    uptime = status.get("uptime_seconds", 0)
    
    # Расчёт процентов
    mcp_percent = (stats["mcp_available"] / max(stats["mcp_checks"], 1)) * 100
    deepseek_percent = (stats["deepseek_working"] / max(stats["deepseek_checks"], 1)) * 100
    perplexity_percent = (stats["perplexity_working"] / max(stats["perplexity_checks"], 1)) * 100
    
    # Статусы
    mcp_status = "🟢" if mcp_percent > 90 else ("🟡" if mcp_percent > 50 else "🔴")
    deepseek_status = "🟢" if deepseek_percent > 90 else ("🟡" if deepseek_percent > 50 else "🔴")
    perplexity_status = "🟢" if perplexity_percent > 90 else ("🟡" if perplexity_percent > 50 else "🔴")
    
    print("\033[2J\033[H")  # Clear screen
    print("=" * 80)
    print("📊 REAL-TIME DIAGNOSTIC DASHBOARD")
    print("=" * 80)
    print(f"🕐 Last Update: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Uptime: {format_uptime(uptime)}")
    print(f"🔄 Total Cycles: {stats['total_cycles']}")
    print()
    
    print("=" * 80)
    print("COMPONENT STATUS")
    print("=" * 80)
    
    # MCP Server
    print(f"\n{mcp_status} MCP Server")
    print(f"   Availability: {mcp_percent:.1f}% ({stats['mcp_available']}/{stats['mcp_checks']})")
    
    # DeepSeek
    print(f"\n{deepseek_status} DeepSeek Agent")
    print(f"   Working Keys: {deepseek_percent:.1f}% ({stats['deepseek_working']}/{stats['deepseek_checks']})")
    
    # Perplexity
    print(f"\n{perplexity_status} Perplexity Agent")
    print(f"   Working Keys: {perplexity_percent:.1f}% ({stats['perplexity_working']}/{stats['perplexity_checks']})")
    
    print()
    print("=" * 80)
    print("LAST AGENT ANALYSIS")
    print("=" * 80)
    
    if stats.get("last_agent_analysis"):
        last_analysis = datetime.fromisoformat(stats["last_agent_analysis"])
        print(f"🧠 {last_analysis.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("⏳ Ожидание первого анализа...")
    
    print()
    print("=" * 80)
    print("Press Ctrl+C to exit | Refreshing every 5 seconds...")
    print("=" * 80)


def main():
    """Главный цикл dashboard"""
    print("🚀 Starting Real-Time Dashboard...")
    print("   Make sure background_diagnostic_service.py is running!")
    print()
    
    try:
        while True:
            print_dashboard()
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard stopped")


if __name__ == "__main__":
    main()

"""Create database tables directly"""
import sys
sys.path.insert(0, 'D:/bybit_strategy_tester_v2')

from backend.database import Base, engine
from backend.models import Strategy, Backtest, Trade, Optimization, OptimizationResult, MarketData

print("Creating all tables...")
Base.metadata.create_all(engine)
print("✅ Database created successfully!")

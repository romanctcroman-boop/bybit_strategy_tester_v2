"""
Quick test to check database tables
"""
import sys
sys.path.insert(0, 'D:/bybit_strategy_tester_v2')

from backend.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()

print("="*70)
print("  DATABASE TABLES")
print("="*70)
print()
print(f"Database: {engine.url}")
print()
print("Tables created:")
for table in tables:
    print(f"  ✅ {table}")
    
    # Get columns
    columns = inspector.get_columns(table)
    print(f"     Columns: {len(columns)}")
    
    # Get indexes
    indexes = inspector.get_indexes(table)
    print(f"     Indexes: {len(indexes)}")
    print()

print(f"Total: {len(tables)} tables")
print("="*70)

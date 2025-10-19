# ============================================================================
# Database Setup without PostgreSQL connection
# ============================================================================
# 
# Creates database models and migrations without connecting to PostgreSQL
# Useful when PostgreSQL is installed but password is unknown
#
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Database Setup - Offline Mode" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$backendDir = "D:\bybit_strategy_tester_v2\backend"

Write-Host "Step 1: Generating SQL migration script..." -ForegroundColor Yellow
Write-Host ""

Set-Location $backendDir

# Generate SQL from models without connecting to database
$env:DATABASE_URL = "sqlite:///./temp.db"  # Use SQLite temporarily

try {
    # Create a Python script to generate SQL
    $pythonScript = @"
import sys
sys.path.insert(0, 'D:/bybit_strategy_tester_v2')

from backend.database import Base, engine
from backend.models import Strategy, Backtest, Trade, Optimization, OptimizationResult, MarketData

# Generate CREATE TABLE statements
print('-- ============================================================================')
print('-- Database Schema for Bybit Strategy Tester')
print('-- Generated from SQLAlchemy models')
print('-- ============================================================================')
print('')

# Get all metadata
from sqlalchemy.schema import CreateTable, CreateIndex

for table in Base.metadata.sorted_tables:
    print(f'-- Table: {table.name}')
    print(str(CreateTable(table).compile(engine)))
    print('')
    
    # Indexes
    for index in table.indexes:
        print(str(CreateIndex(index).compile(engine)))
    print('')

print('-- ============================================================================')
print('-- End of schema')
print('-- ============================================================================')
"@

    $tempPyFile = "$env:TEMP\generate_schema.py"
    $pythonScript | Out-File -FilePath $tempPyFile -Encoding UTF8
    
    $outputSql = "$backendDir\database_schema_generated.sql"
    
    python $tempPyFile > $outputSql 2>&1
    
    if (Test-Path $outputSql) {
        Write-Host "   SQL schema generated: $outputSql" -ForegroundColor Green
        Write-Host ""
        
        # Show first 50 lines
        Write-Host "Preview of generated schema:" -ForegroundColor Cyan
        Get-Content $outputSql -Head 50 | Write-Host -ForegroundColor Gray
        Write-Host "..." -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host "   ERROR: Could not generate schema" -ForegroundColor Red
    }
    
    Remove-Item $tempPyFile -Force
    
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Next Steps" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Since PostgreSQL password is not set correctly, you can:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Option 1: Reset PostgreSQL password manually" -ForegroundColor Cyan
Write-Host "   1. Open pgAdmin 4" -ForegroundColor White
Write-Host "   2. Connect with your current password" -ForegroundColor White
Write-Host "   3. Right-click 'postgres' user -> Properties" -ForegroundColor White
Write-Host "   4. Set password to: postgres" -ForegroundColor White
Write-Host ""
Write-Host "Option 2: Continue without PostgreSQL for now" -ForegroundColor Cyan
Write-Host "   1. We can use SQLite for development" -ForegroundColor White
Write-Host "   2. Switch to PostgreSQL later when password is fixed" -ForegroundColor White
Write-Host ""
Write-Host "Option 3: Use the generated SQL schema" -ForegroundColor Cyan
Write-Host "   1. Open database_schema_generated.sql" -ForegroundColor White
Write-Host "   2. Execute it manually in pgAdmin or psql" -ForegroundColor White
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green

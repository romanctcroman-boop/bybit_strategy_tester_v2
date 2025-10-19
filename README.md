# Bybit Strategy Tester v2.0

Production-Ready Trading Strategy Backtesting Platform

## Status
IN DEVELOPMENT - October 16, 2025

## Technology Stack (100% FREE)
- Backend: FastAPI + PostgreSQL + TimescaleDB
- Frontend: Electron + React + TypeScript
- Charts: TradingView Lightweight Charts

## Quick Start

### Backend Setup
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

### Frontend Setup
cd frontend
npm install

### Run Development
# Terminal 1: Backend
uvicorn backend.main:app --reload

# Terminal 2: Frontend
npm run electron:dev

## Documentation
See docs/ folder for complete specifications

## License
MIT - Free for commercial use

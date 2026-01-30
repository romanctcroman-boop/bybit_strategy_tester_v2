from __future__ import annotations

import json
import pathlib
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def main() -> None:
  sys.path.insert(0, str(pathlib.Path(".").resolve()))

  from backend.api.routers.strategy_builder import router as strategy_builder_router
  from backend.database import Base, get_db

  db_url = "sqlite:///:memory:"
  engine = create_engine(
      db_url,
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
  )
  TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

  def override_get_db():
      db = TestingSessionLocal()
      try:
          yield db
      finally:
          db.close()

  app = FastAPI()
  app.include_router(strategy_builder_router, prefix="/api/v1")
  app.dependency_overrides[get_db] = override_get_db
  Base.metadata.create_all(bind=engine)

  client = TestClient(app)

  data = {
      "name": "Codegen Strategy",
      "description": "Strategy for code generation tests",
      "timeframe": "1h",
      "symbol": "BTCUSDT",
      "market_type": "linear",
      "direction": "both",
      "initial_capital": 10000.0,
      "blocks": [
          {
              "id": "block_price",
              "type": "price",
              "category": "input",
              "name": "Price",
              "icon": "currency-dollar",
              "x": 100,
              "y": 100,
              "params": {},
          },
          {
              "id": "block_rsi",
              "type": "rsi",
              "category": "indicator",
              "name": "RSI",
              "icon": "graph-up",
              "x": 300,
              "y": 100,
              "params": {"period": 14, "overbought": 70, "oversold": 30},
          },
          {
              "id": "block_buy",
              "type": "buy",
              "category": "action",
              "name": "Buy",
              "icon": "arrow-up-circle",
              "x": 500,
              "y": 80,
              "params": {},
          },
      ],
      "connections": [
          {
              "id": "conn_price_rsi",
              "source": {"blockId": "block_price", "portId": "value"},
              "target": {"blockId": "block_rsi", "portId": "source"},
              "type": "data",
          },
          {
              "id": "conn_rsi_buy",
              "source": {"blockId": "block_rsi", "portId": "signal"},
              "target": {"blockId": "block_buy", "portId": "trigger"},
              "type": "data",
          },
      ],
  }

  create_resp = client.post("/api/v1/strategy-builder/strategies", json=data)
  print("CREATE", create_resp.status_code, create_resp.json())
  sid = create_resp.json()["id"]

  resp = client.post(
      f"/api/v1/strategy-builder/strategies/{sid}/generate-code",
      json={
          "template": "backtest",
          "include_comments": True,
          "include_logging": True,
          "async_mode": False,
      },
  )
  print("GEN", resp.status_code)
  print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
  main()


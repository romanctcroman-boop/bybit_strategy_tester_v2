"""Find Strategy_RSI_L/S_9 in the database and show its params."""

import sys

sys.path.insert(0, ".")
import asyncio

from loguru import logger

logger.remove()
from sqlalchemy import text

from backend.database import get_db


def main():
    session = next(get_db())
    rows = session.execute(
        text("SELECT id, name, symbol, timeframe, parameters, builder_graph FROM strategies WHERE id = :id"),
        {"id": "dd2969a2-bbba-410e-b190-be1e8cc50b21"},
    ).fetchall()
    for r in rows:
        print("ID:", r[0])
        print("Name:", r[1])
        print("Symbol:", r[2], "TF:", r[3])
        print("Params:", r[4])
        print("Graph (first 2000 chars):", str(r[5])[:2000] if r[5] else None)


main()

from __future__ import annotations

"""
Archival Service

Archives old candles from bybit_kline_audit into Parquet files partitioned by
symbol/interval/date (UTC). Provides restore to DB. Idempotent by virtue of
UNIQUE(symbol, open_time) on the destination table.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, List

import os
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session
import pyarrow as pa
import pyarrow.parquet as pq

from backend.database import SessionLocal, Base, engine
from backend.models.bybit_kline_audit import BybitKlineAudit


def ms_to_date(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d')


@dataclass
class ArchiveConfig:
    output_dir: str
    before_ms: Optional[int] = None  # archive rows with open_time <= before_ms
    symbol: Optional[str] = None
    interval: Optional[str] = None
    batch_size: int = 5000


class ArchivalService:
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or os.environ.get('ARCHIVE_DIR', 'archives')).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _iter_rows(self, s: Session, cfg: ArchiveConfig):
        q = s.query(BybitKlineAudit)
        if cfg.symbol:
            q = q.filter(BybitKlineAudit.symbol == cfg.symbol)
        if cfg.before_ms is not None:
            q = q.filter(BybitKlineAudit.open_time <= cfg.before_ms)
        # No strict interval column in audit; interval is a backfill param, skip filter here
        q = q.order_by(BybitKlineAudit.symbol.asc(), BybitKlineAudit.open_time.asc())
        offset = 0
        while True:
            chunk = q.limit(cfg.batch_size).offset(offset).all()
            if not chunk:
                break
            yield chunk
            offset += len(chunk)

    def _write_parquet_partition(self, symbol: str, interval: str, date_str: str, rows: List[BybitKlineAudit]):
        part_dir = self.output_dir / f"symbol={symbol}" / f"interval={interval}" / f"date={date_str}"
        part_dir.mkdir(parents=True, exist_ok=True)
        # One file per write to keep simple; compaction can merge later
        file_path = part_dir / f"klines_{rows[0].open_time}_{rows[-1].open_time}.parquet"
        data = {
            'symbol': [r.symbol for r in rows],
            'open_time': [r.open_time for r in rows],
            'open_time_dt': [r.open_time_dt for r in rows],
            'open_price': [r.open_price for r in rows],
            'high_price': [r.high_price for r in rows],
            'low_price': [r.low_price for r in rows],
            'close_price': [r.close_price for r in rows],
            'volume': [r.volume for r in rows],
            'turnover': [r.turnover for r in rows],
            'raw': [r.raw for r in rows],
        }
        table = pa.Table.from_pydict(data)
        pq.write_table(table, file_path)
        return str(file_path)

    def archive(self, cfg: ArchiveConfig, *, interval_for_partition: str = "1") -> int:
        """Archive rows to Parquet partitions. Returns number of rows written.

        interval_for_partition is used only for partition path, since audit table
        doesn't store interval; callers should pass the interval for which they
        archive.
        """
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass
        total = 0
        s = SessionLocal()
        try:
            for chunk in self._iter_rows(s, cfg):
                # group rows by (symbol, date)
                groups = {}
                for r in chunk:
                    date_str = ms_to_date(r.open_time)
                    key = (r.symbol, date_str)
                    groups.setdefault(key, []).append(r)
                # write each group
                for (symbol, date_str), rows in groups.items():
                    rows.sort(key=lambda r: r.open_time)
                    self._write_parquet_partition(symbol, interval_for_partition, date_str, rows)
                    total += len(rows)
        finally:
            s.close()
        return total

    def restore_from_dir(self, dir_path: Optional[str] = None) -> int:
        """Load all parquet files under output_dir (or dir_path) back into DB.
        Idempotent due to UNIQUE(symbol, open_time).
        """
        base_dir = Path(dir_path or self.output_dir)
        count = 0
        for p in base_dir.rglob('*.parquet'):
            # Read single file explicitly to avoid dataset engine attempting to merge
            # files with differing dictionary encodings
            table = pq.ParquetFile(p).read()
            batch = table.to_pydict()
            rows = []
            for i in range(len(batch['open_time'])):
                rows.append({
                    'open_time': int(batch['open_time'][i]),
                    'open_time_dt': batch.get('open_time_dt', [None])[i],
                    'open_price': batch.get('open_price', [None])[i],
                    'high_price': batch.get('high_price', [None])[i],
                    'low_price': batch.get('low_price', [None])[i],
                    'close_price': batch.get('close_price', [None])[i],
                    'volume': batch.get('volume', [None])[i],
                    'turnover': batch.get('turnover', [None])[i],
                    'raw': batch.get('raw', [None])[i],
                })
            # persist via adapter helper to reuse upsert logic
            from backend.services.adapters.bybit import BybitAdapter
            adapter = BybitAdapter()
            symbol = None
            if 'symbol' in batch and len(batch['symbol']):
                symbol = batch['symbol'][0]
            if not symbol:
                # try infer from path
                try:
                    for part in p.parts:
                        if part.startswith('symbol='):
                            symbol = part.split('=',1)[1]
                            break
                except Exception:
                    symbol = 'UNKNOWN'
            adapter._persist_klines_to_db(symbol, rows)
            count += len(rows)
        return count

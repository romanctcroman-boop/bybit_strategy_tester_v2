# -*- coding: utf-8 -*-
"""Загрузчик данных с Bybit"""
import pandas as pd
from pybit.unified_trading import HTTP


class BybitDataLoader:
    def __init__(self, testnet=True):
        self.session = HTTP(testnet=testnet)

    def get_klines(self, symbol, interval, limit=200):
        """Получение исторических данных"""
        try:
            result = self.session.get_kline(
                category="linear", symbol=symbol, interval=interval, limit=limit
            )

            if result["retCode"] == 0:
                df = pd.DataFrame(result["result"]["list"])
                df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)

                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
                df = df.sort_values("timestamp").reset_index(drop=True)

                return df
            else:
                print(f"Ошибка API: {result}")
                return None

        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return None

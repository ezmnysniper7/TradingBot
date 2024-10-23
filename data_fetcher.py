# data_fetcher.py
import pandas as pd
import time
from binance.client import Client

client = Client()

def get_historical_data(symbols, interval, start_ts, end_ts):
    data_dict = {}
    for symbol in symbols:
        data = []
        limit = 1000  # Maximum records per request
        current_start_ts = start_ts
        while True:
            klines = client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                startTime=current_start_ts,
                endTime=end_ts,
            )
            if not klines:
                break
            data.extend(klines)
            current_start_ts = klines[-1][6] + 1  # klines[-1][6] is the close time
            if current_start_ts >= end_ts:
                break
            time.sleep(0.1)  # Sleep to avoid rate limits

        if data:
            df = pd.DataFrame(
                data,
                columns=[
                    "Date",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                    "Close_time",
                    "Quote_asset_volume",
                    "Number_of_trades",
                    "Taker_buy_base_asset_volume",
                    "Taker_buy_quote_asset_volume",
                    "Ignore",
                ],
            )
            df["Date"] = pd.to_datetime(df["Date"], unit="ms")
            df.set_index("Date", inplace=True)
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df = df.astype(float)
            data_dict[symbol] = df
        else:
            print(f"No data fetched for {symbol}.")
    return data_dict

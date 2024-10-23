import backtrader as bt
import pandas as pd
from binance.client import Client
import datetime
import time  # Import time module for sleep function

client = Client()  # No API keys needed for public data


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



class TestStrategy(bt.Strategy):
    params = (
        ("short_window", 10),
        ("long_window", 20),
        ("atr_period", 14),
    )

    def __init__(self):
        self.symbols = [data._name for data in self.datas]
        self.indicators = {}
        for data in self.datas:
            symbol = data._name
            self.indicators[symbol] = {}
            self.indicators[symbol]['ema_short'] = bt.indicators.EMA(data.close, period=self.params.short_window)
            self.indicators[symbol]['ema_long'] = bt.indicators.EMA(data.close, period=self.params.long_window)
            self.indicators[symbol]['macd'] = bt.indicators.MACD(data.close)
            self.indicators[symbol]['adx'] = bt.indicators.ADX(data)
            self.indicators[symbol]['rsi'] = bt.indicators.RSI(data.close)
            self.indicators[symbol]['atr'] = bt.indicators.ATR(data, period=self.params.atr_period)
            self.indicators[symbol]['bollinger'] = bt.indicators.BollingerBands(data.close)
            self.indicators[symbol]['buy_price'] = None
            self.indicators[symbol]['stop_loss_price'] = None

    def next(self):
        for data in self.datas:
            symbol = data._name
            pos = self.getposition(data).size
            price = data.close[0]
            ind = self.indicators[symbol]
            ema_short = ind['ema_short'][0]
            ema_long = ind['ema_long'][0]
            macd_line = ind['macd'].macd[0]
            macd_signal = ind['macd'].signal[0]
            adx = ind['adx'][0]
            rsi = ind['rsi'][0]
            atr = ind['atr'][0]
            bollinger_mid = ind['bollinger'].mid[0]
            bollinger_top = ind['bollinger'].top[0]
            bollinger_bot = ind['bollinger'].bot[0]
            current_date = data.datetime.datetime(0)

            # Print indicator values
            print(
                f"Symbol: {symbol}, Date: {current_date}, "
                f"EMA Long: {ema_long:.2f}, MACD: {macd_line:.2f}, ADX: {adx:.2f}, RSI: {rsi:.2f}"
            )

            if pos == 0:
                # Entry Criteria
                if (
                    ema_short > ema_long and
                    macd_line > macd_signal and
                    adx > 25 and
                    40 < rsi < 60 and
                    price > bollinger_mid
                ):
                    # Risk management: position sizing based on ATR
                    risk_per_trade = 0.05  # Risk 1% of portfolio
                    cash = self.broker.get_cash()
                    if atr > 0:
                        stop_loss_price = price - atr * 2
                        position_size = (cash * risk_per_trade) / (atr * 2)
                        if position_size > 0:
                            self.buy(data=data, size=position_size)
                            ind['buy_price'] = price
                            ind['stop_loss_price'] = stop_loss_price
                            print(f"Buy order executed for {symbol} on {current_date}")
                        else:
                            print(f"Position size is zero or negative for {symbol} on {current_date}, trade not executed.")
                    else:
                        print(f"ATR is zero or negative for {symbol} on {current_date}, trade not executed.")
            else:
                # Exit Criteria
                stop_loss_price = ind.get('stop_loss_price', None)
                if stop_loss_price and price <= stop_loss_price:
                    self.close(data=data)
                    print(f"Position closed for {symbol} on {current_date} due to stop-loss")
                elif (
                    ema_short < ema_long and
                    macd_line < macd_signal and
                    adx < 25 and
                    price < bollinger_mid
                ):
                    self.close(data=data)
                    print(f"Sell order executed for {symbol} on {current_date}")


if __name__ == "__main__":
    # Convert date strings to timestamps in milliseconds
    start_str = "2024-01-01"
    end_str = "2024-03-01"  # Adjust the end date for a shorter timeframe

    start_ts = int(datetime.datetime.strptime(start_str, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.datetime.strptime(end_str, "%Y-%m-%d").timestamp() * 1000)
    
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    # Fetch historical data and save to CSV
    historical_data = get_historical_data(
        symbols=symbols,
        interval=Client.KLINE_INTERVAL_1MINUTE,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if historical_data:
        # Save each DataFrame to a CSV (optional)
        for symbol, df in historical_data.items():
            df.to_csv(f"{symbol}_historical.csv")

        # Create Cerebro engine
        cerebro = bt.Cerebro()

        # Set initial cash
        cerebro.broker.setcash(10000.0)

        # Set commission
        cerebro.broker.setcommission(commission=0.001)

        # Add data feeds to Cerebro
        for symbol, df in historical_data.items():
            data = bt.feeds.PandasData(dataname=df, name=symbol)
            cerebro.adddata(data)

        # Add strategy to Cerebro
        cerebro.addstrategy(TestStrategy)

        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

        # Run backtest
        print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
        results = cerebro.run()
        print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

        # Extract and print analyzers
        strat = results[0]
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        print(f"Sharpe Ratio: {sharpe.get('sharperatio', None)}")
        print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")

        # Plot results
        cerebro.plot()
    else:
        print("Historical data could not be fetched.")

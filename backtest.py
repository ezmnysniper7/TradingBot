import backtrader as bt
import pandas as pd
from binance.client import Client
import datetime
import time  # Import time module for sleep function
from data_fetcher import get_historical_data
from strategies import AdvancedStrategy, MLStrategy

client = Client()  # No API keys needed for public data

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
        cerebro.addstrategy(AdvancedStrategy)

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

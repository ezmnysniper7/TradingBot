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
    end_str = "2024-10-01"  # Adjust the end date for a shorter timeframe

    start_ts = int(datetime.datetime.strptime(start_str, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.datetime.strptime(end_str, "%Y-%m-%d").timestamp() * 1000)
    
    symbols = ["ETHUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "SOLUSDT"]

    # Fetch historical data and save to CSV
    historical_data = get_historical_data(
        symbols=symbols,
        interval=Client.KLINE_INTERVAL_15MINUTE,
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

        # Add a TradeAnalyzer for each data feed
        for data in cerebro.datas:
            analyzer_name = 'ta_{}'.format(data._name)
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name=analyzer_name)

        # Run backtest
        print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
        results = cerebro.run()
        print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

        # Extract and print global analyzers
        strat = results[0]
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        print(f"Sharpe Ratio: {sharpe.get('sharperatio', None)}")
        print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")

        # Extract and print trade statistics per symbol
        for data in cerebro.datas:
            symbol = data._name
            analyzer_name = 'ta_{}'.format(symbol)
            trade_analyzer = strat.analyzers.getbyname(analyzer_name)
            trade_analysis = trade_analyzer.get_analysis()

            # Extract trade statistics
            total_trades = trade_analysis.total.closed if hasattr(trade_analysis.total, 'closed') else 0
            profitable_trades = trade_analysis.won.total if hasattr(trade_analysis.won, 'total') else 0
            losing_trades = trade_analysis.lost.total if hasattr(trade_analysis.lost, 'total') else 0

            # Calculate win rate
            win_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0

            # Total gross profit and loss
            gross_profit = trade_analysis.won.pnl.total if hasattr(trade_analysis.won.pnl, 'total') else 0
            gross_loss = trade_analysis.lost.pnl.total if hasattr(trade_analysis.lost.pnl, 'total') else 0

            # Average profit and loss per trade
            avg_profit = trade_analysis.won.pnl.average if hasattr(trade_analysis.won.pnl, 'average') else 0
            avg_loss = trade_analysis.lost.pnl.average if hasattr(trade_analysis.lost.pnl, 'average') else 0

            # Profit factor
            profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None

            # Print per-symbol statistics
            print(f"\n--- Trade Analysis for {symbol} ---")
            print(f"Total Trades: {total_trades}")
            print(f"Profitable Trades: {profitable_trades}")
            print(f"Losing Trades: {losing_trades}")
            print(f"Win Rate: {win_rate:.2f}%")
            print(f"Average Profit per Trade: {avg_profit:.2f}")
            print(f"Average Loss per Trade: {avg_loss:.2f}")
            print(f"Profit Factor: {profit_factor:.2f}")

        # Plot results
        cerebro.plot()
    else:
        print("Historical data could not be fetched.")

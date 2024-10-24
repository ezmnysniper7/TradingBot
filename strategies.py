# strategies.py

import backtrader as bt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from joblib import dump, load

class AdvancedStrategy(bt.Strategy):
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
            ind = self.indicators[symbol]
            ind['ema_short'] = bt.indicators.EMA(data.close, period=self.params.short_window)
            ind['ema_long'] = bt.indicators.EMA(data.close, period=self.params.long_window)
            ind['macd'] = bt.indicators.MACD(data.close)
            ind['adx'] = bt.indicators.ADX(data)
            ind['rsi'] = bt.indicators.RSI(data.close)
            ind['atr'] = bt.indicators.ATR(data, period=self.params.atr_period)
            ind['bollinger'] = bt.indicators.BollingerBands(data.close)
            ind['stochastic'] = bt.indicators.Stochastic(data)
            ind['ichimoku'] = bt.indicators.Ichimoku()
            ind['buy_price'] = None
            ind['stop_loss_price'] = None

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
            stochastic_k = ind['stochastic'].percK[0]
            stochastic_d = ind['stochastic'].percD[0]
            ichimoku_span_a = ind['ichimoku'].senkou_span_a[0]
            ichimoku_span_b = ind['ichimoku'].senkou_span_b[0]
            current_date = data.datetime.datetime(0)
            # Check if any indicators are NaN
            if any(np.isnan(value) for value in [
                ema_short, ema_long, macd_line, macd_signal, adx,
                rsi, stochastic_k, stochastic_d, ichimoku_span_a, ichimoku_span_b
            ]):
                continue

            # Print indicator values
            print(
                f"Symbol: {symbol}, Date: {current_date}, EMA Short: {ema_short:.2f}, "
                f"EMA Long: {ema_long:.2f}, MACD: {macd_line:.2f}, ADX: {adx:.2f}, RSI: {rsi:.2f}"
            )

            if pos == 0:
                # Entry Criteria
                if (
                    ema_short > ema_long and
                    macd_line > macd_signal and
                    adx > 20 and
                    10 < rsi < 90 and
                    stochastic_k > stochastic_d and
                    price > bollinger_mid and
                    price > ichimoku_span_a and
                    price > ichimoku_span_b
                ):
                    # Risk management: position sizing based on ATR
                    risk_per_trade = 0.01  # Risk 1% of portfolio
                    cash = self.broker.get_cash()
                    if atr > 0:
                        position_size = (cash * risk_per_trade) / (atr * 2)
                        if position_size > 0:
                            self.buy(data=data, size=position_size)
                            ind['buy_price'] = price
                            ind['stop_loss_price'] = price - atr * 2
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
                    stochastic_k < stochastic_d and
                    price < bollinger_mid
                ):
                    self.close(data=data)
                    print(f"Sell order executed for {symbol} on {current_date}")

class MLStrategy(bt.Strategy):
    params = (
        ("lookback", 14),
        ("n_estimators", 100),
    )

    def __init__(self):
        self.symbols = [data._name for data in self.datas]
        self.models = {}
        self.feature_data = {}
        self.min_data_points = self.params.lookback + 1

        for data in self.datas:
            symbol = data._name
            self.feature_data[symbol] = pd.DataFrame()
            self.models[symbol] = RandomForestClassifier(n_estimators=self.params.n_estimators)

    def next(self):
        for data in self.datas:
            symbol = data._name
            pos = self.getposition(data).size
            price = data.close[0]
            current_date = data.datetime.datetime(0)

            # Prepare features
            ind = {}
            ind['close'] = data.close[0]
            ind['open'] = data.open[0]
            ind['high'] = data.high[0]
            ind['low'] = data.low[0]
            ind['volume'] = data.volume[0]
            ind['rsi'] = bt.indicators.RSI(data.close, period=14)[0]
            ind['macd'] = bt.indicators.MACD(data.close).macd[0]
            ind['ema'] = bt.indicators.EMA(data.close, period=14)[0]

            # Append to feature data
            self.feature_data[symbol] = self.feature_data[symbol].append(ind, ignore_index=True)

            # Ensure enough data points to train
            if len(self.feature_data[symbol]) > self.min_data_points:
                # Prepare training data
                df = self.feature_data[symbol].copy()
                df['target'] = df['close'].shift(-1) > df['close']
                df.dropna(inplace=True)

                features = df[['close', 'open', 'high', 'low', 'volume', 'rsi', 'macd', 'ema']]
                target = df['target']

                # Train the model
                self.models[symbol].fit(features[:-1], target[:-1])

                # Make prediction
                last_features = features.iloc[-1].values.reshape(1, -1)
                prediction = self.models[symbol].predict(last_features)

                if pos == 0 and prediction == True:
                    self.buy(data=data)
                    print(f"Buy order executed for {symbol} on {current_date}")
                elif pos != 0 and prediction == False:
                    self.close(data=data)
                    print(f"Sell order executed for {symbol} on {current_date}")

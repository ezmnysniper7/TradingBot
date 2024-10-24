# strategies.py

import backtrader as bt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
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
            ind['ichimoku'] = bt.indicators.Ichimoku(data)
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
        self.scalers = {}
        self.feature_data = {}
        self.min_data_points = self.params.lookback + 50  # Increase to ensure enough data for training

        for data in self.datas:
            symbol = data._name
            self.feature_data[symbol] = pd.DataFrame()
            self.models[symbol] = RandomForestClassifier(n_estimators=self.params.n_estimators)
            self.scalers[symbol] = StandardScaler()

            # Initialize indicators for feature calculation
            data.ema_short = bt.indicators.EMA(data.close, period=12)
            data.ema_long = bt.indicators.EMA(data.close, period=26)
            data.macd = bt.indicators.MACD(data.close)
            data.rsi = bt.indicators.RSI(data.close)
            data.adx = bt.indicators.ADX(data)
            data.stochastic = bt.indicators.Stochastic(data)
            data.bollinger = bt.indicators.BollingerBands(data.close)

    def next(self):
        for data in self.datas:
            symbol = data._name
            pos = self.getposition(data).size
            current_date = data.datetime.datetime(0)

            # Prepare features
            features = {
                'close': data.close[0],
                'open': data.open[0],
                'high': data.high[0],
                'low': data.low[0],
                'volume': data.volume[0],
                'ema_short': data.ema_short[0],
                'ema_long': data.ema_long[0],
                'macd': data.macd.macd[0],
                'macd_signal': data.macd.signal[0],
                'rsi': data.rsi[0],
                'adx': data.adx[0],
                'stochastic_k': data.stochastic.percK[0],
                'stochastic_d': data.stochastic.percD[0],
                'bollinger_mid': data.bollinger.mid[0],
                'bollinger_upper': data.bollinger.top[0],
                'bollinger_lower': data.bollinger.bot[0],
            }

            # Append to feature data
            self.feature_data[symbol] = self.feature_data[symbol].append(features, ignore_index=True)

            # Ensure enough data points to train
            if len(self.feature_data[symbol]) > self.min_data_points:
                df = self.feature_data[symbol].copy()

                # Create lagged features
                for i in range(1, self.params.lookback + 1):
                    df[f'close_lag_{i}'] = df['close'].shift(i)
                    df[f'rsi_lag_{i}'] = df['rsi'].shift(i)

                # Drop rows with NaN values
                df.dropna(inplace=True)

                # Define target variable
                df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

                # Avoid look-ahead bias by excluding the last row
                X = df.drop(['target'], axis=1)[:-1]
                y = df['target'][:-1]

                # Scale features
                X_scaled = self.scalers[symbol].fit_transform(X)

                # Train the model using Time Series Split
                tscv = TimeSeriesSplit(n_splits=5)
                for train_index, test_index in tscv.split(X_scaled):
                    X_train, X_test = X_scaled[train_index], X_scaled[test_index]
                    y_train, y_test = y.iloc[train_index], y.iloc[test_index]
                    self.models[symbol].fit(X_train, y_train)

                # Make prediction on the latest data point
                last_features = X.iloc[-1].values.reshape(1, -1)
                last_features_scaled = self.scalers[symbol].transform(last_features)
                prediction = self.models[symbol].predict(last_features_scaled)

                # Trading logic
                if pos == 0 and prediction == 1:
                    self.buy(data=data)
                    print(f"Buy order executed for {symbol} on {current_date}")
                elif pos != 0 and prediction == 0:
                    self.close(data=data)
                    print(f"Sell order executed for {symbol} on {current_date}")

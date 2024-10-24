# main.py

import pandas as pd
import numpy as np
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
import time
import pandas_ta as ta
import logging
import traceback
from data_fetcher import get_historical_data
import config

client = Client(config.API_KEY, config.API_SECRET)
#Below line is testing URL
# client.API_URL = 'https://testnet.binance.vision/api' 

logging.basicConfig(filename='trading_bot.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def apply_technicals(df, short_window, long_window):
    df['EMA_Short'] = ta.ema(df['Close'], length=short_window)
    df['EMA_Long'] = ta.ema(df['Close'], length=long_window)
    df['RSI'] = ta.rsi(df['Close'], length=14)


def generate_signals(df):
    df['Signal'] = 0
    buy_condition = (
        (df['EMA_Short'] > df['EMA_Long']) &
        (df['RSI'] < 30)
    )
    sell_condition = (
        (df['EMA_Short'] < df['EMA_Long']) &
        (df['RSI'] > 70)
    )
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    df['Position'] = df['Signal'].diff()

    
def execute_trade(symbol, quantity, side):
    try:
        # Place market order
        order = client.create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        logging.info(f"Executed {side} order for {quantity} {symbol}")

        # Calculate stop-loss and take-profit prices
        last_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        stop_loss = last_price * 0.98 if side == SIDE_BUY else last_price * 1.02
        take_profit = last_price * 1.02 if side == SIDE_BUY else last_price * 0.98

        # Place OCO order
        oco_order = client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,
            quantity=quantity,
            price=str(round(take_profit, 2)),
            stopPrice=str(round(stop_loss, 2)),
            stopLimitPrice=str(round(stop_loss * 0.99, 2)),
            stopLimitTimeInForce=TIME_IN_FORCE_GTC
        )
        logging.info("OCO order placed for stop-loss and take-profit.")
        return order
    except BinanceAPIException as e:
        logging.error(f"Binance API Exception: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


    
symbol = 'BTCUSDT'
short_window = 5
long_window = 20
interval = '1m'
lookback = '30'

def get_trade_quantity(symbol, percentage=0.01):
    try:
        balance = client.get_asset_balance(asset='USDT')
        usdt_balance = float(balance['free'])
        last_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        quantity = (usdt_balance * percentage) / last_price
        quantity = round(quantity, 6)  # Binance allows up to 6 decimal places
        return quantity
    except Exception as e:
        logging.error(f"Error calculating trade quantity: {e}")
        return None


def check_balances():
    try:
        account_info = client.get_account()
        balances = account_info['balances']
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            if free > 0 or locked > 0:
                print(f"{asset}: Free = {free}, Locked = {locked}")
    except Exception as e:
        print(f"An error occurred while fetching balances: {e}")

def main():
    check_balances()
    position = 0
    while True:
        try:
            # Fetch the latest data
            df = get_historical_data(client, symbol, interval, lookback)
            apply_technicals(df, short_window, long_window)
            generate_signals(df)
            latest_signal = df['Signal'].iloc[-1]
            latest_position = df['Position'].iloc[-1]
            print(f"Latest Signal: {latest_signal}, Latest Position Change: {latest_position}")

            quantity = get_trade_quantity(symbol, percentage=0.01)
            if quantity is None or quantity <= 0:
                print("Insufficient balance to place order.")
                time.sleep(60)
                continue

            if latest_position == 1 and position == 0:
                # Buy signal
                execute_trade(symbol, quantity, SIDE_BUY)
                position = 1  # Update position to holding
            elif latest_position == -1 and position == 1:
                # Sell signal
                execute_trade(symbol, quantity, SIDE_SELL)
                position = 0  # Update position to no holding
            else:
                print("No trade executed.")

            time.sleep(60)  # Wait for the next interval
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-

import ccxt
import time
import pandas as pd
from datetime import datetime, timedelta
from ta.utils import dropna
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
import numpy as np


class OrderBook:
    exchange = None

    simulate_const = {
        '15m': {
            'candle_thres': 900000
        },
        '30m': {
            'candle_thres': 1800000
        },
        '1h': {
            'candle_thres': 3600000
        },
        '2h': {
            'candle_thres': 7200000
        },
        '4h': {
            'candle_thres': 14400000
        },
        '6h': {
            'candle_thres': 21600000
        },
        '8h': {
            'candle_thres': 28800000
        },
        '12h': {
            'candle_thres': 43200000
        },
        '1d': {
            'candle_thres': 86400000
        }
    }

    def __init__(self, exchange_str):
        if exchange_str == 'bitget':
            self.exchange = ccxt.bitget({'options': {
                'defaultType': 'spot'
            }})
        else:
            self.exchange = ccxt.binance({'options': {
                'defaultType': 'future'
            }})

    def fetch_markets(self):
        ret = self.exchange.fetch_markets()
        return ret

    def fetch_tickers(self):
        print(self.exchange.fetch_tickers())
        ret = list(map(lambda ticker: ticker.replace('/', ''), filter(lambda ticker: 'USDT' in ticker, self.exchange.fetch_tickers().keys())))
        return ret

    def generate_chart_data(self, symbol, timeframe='30m', limit=100):
        df = pd.DataFrame(data=None, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        since = int(time.time() * 1000)
        least = limit
        load = limit
        while True:
            if least > 1500:
                since -= 1500 * self.simulate_const[timeframe]['candle_thres']
                least -= 1500
                load = 1500
            else:
                since -= least * self.simulate_const[timeframe]['candle_thres']
                load = least
                least = 0

            btc = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=load
            )

            df = pd.concat([pd.DataFrame(data=btc, columns=['datetime', 'open', 'high', 'low', 'close', 'volume']), df])

            if least == 0:
                break

        ms = time.time() * 1000.0
        if timeframe == '1d' or ms - self.simulate_const[timeframe]['candle_thres'] < df.iloc[-1, 0]:
            df = df.iloc[:-1, :]

        df['date'] = pd.to_datetime(df['datetime'], unit='ms')
        if timeframe != '1d':
            df['date'] = pd.DatetimeIndex(df['date']) + timedelta(hours=9)
        df['datetime'] = df['datetime'] + 32400000

        df = dropna(df)
        indicator_bb = BollingerBands(close=df["close"], window=20, window_dev=2)

        # Add Bollinger Bands features
        df['bb_bbm'] = indicator_bb.bollinger_mavg()
        df['bb_bbh'] = indicator_bb.bollinger_hband()
        df['bb_bbl'] = indicator_bb.bollinger_lband()

        indicator_rsi = RSIIndicator(close=df["close"], window=14)
        df['rsi'] = indicator_rsi.rsi()

        '''
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_rows', None)
        print(df)
        
        plt.figure(figsize=(9, 5))
        plt.plot(df['datetime'], df['close'], label='close')
        plt.plot(df['datetime'], df['bb_bbh'], linestyle='dashed', label='Upper band')
        plt.plot(df['datetime'], df['bb_bbm'], linestyle='dashed', label='Moving Average 20')
        plt.plot(df['datetime'], df['bb_bbl'], linestyle='dashed', label='Lower band')
        plt.legend(loc='best')
        plt.show()
        '''

        return df

    @staticmethod
    def get_last_data(df):
        last_data = df.iloc[-1]

        return {
            'open': last_data['open'],
            'high': last_data['high'],
            'low': last_data['low'],
            'close': last_data['close']
        }

    @staticmethod
    def get_bb(df):
        last_data = df.iloc[-1]

        #  print(last_data)

        return last_data['bb_bbh'], last_data['bb_bbl']

    @staticmethod
    def get_rsi(df):
        pev_data = df.iloc[-2]
        last_data = df.iloc[-1]

        #  print(pev_data)
        #  print(last_data)

        return pev_data['rsi'], last_data['rsi']


'''
              datetime     open     high  ...        bb_bbh        bb_bbl        rsi
0  2022-06-09 02:30:00  30370.1  30399.0  ...           NaN           NaN        NaN
1  2022-06-09 03:00:00  30371.2  30407.3  ...           NaN           NaN        NaN
2  2022-06-09 03:30:00  30204.8  30324.3  ...           NaN           NaN        NaN
3  2022-06-09 04:00:00  30224.6  30272.0  ...           NaN           NaN        NaN
4  2022-06-09 04:30:00  30216.3  30298.4  ...           NaN           NaN        NaN
5  2022-06-09 05:00:00  30126.2  30206.8  ...           NaN           NaN        NaN
6  2022-06-09 05:30:00  30186.8  30319.6  ...           NaN           NaN        NaN
7  2022-06-09 06:00:00  30191.9  30372.0  ...           NaN           NaN        NaN
8  2022-06-09 06:30:00  30289.6  30515.8  ...           NaN           NaN        NaN
9  2022-06-09 07:00:00  30409.0  30444.5  ...           NaN           NaN        NaN
10 2022-06-09 07:30:00  30316.2  30383.8  ...           NaN           NaN        NaN
11 2022-06-09 08:00:00  30300.0  30364.4  ...           NaN           NaN        NaN
12 2022-06-09 08:30:00  30274.0  30344.7  ...           NaN           NaN        NaN
13 2022-06-09 09:00:00  30192.6  30232.4  ...           NaN           NaN  34.360973
14 2022-06-09 09:30:00  30128.3  30264.8  ...           NaN           NaN  43.483033
15 2022-06-09 10:00:00  30210.9  30312.6  ...           NaN           NaN  48.666768
16 2022-06-09 10:30:00  30266.2  30304.1  ...           NaN           NaN  36.403708
17 2022-06-09 11:00:00  30076.6  30184.9  ...           NaN           NaN  43.772203
18 2022-06-09 11:30:00  30168.4  30200.0  ...           NaN           NaN  45.251454
19 2022-06-09 12:00:00  30188.4  30268.0  ...  30389.309094  30070.030906  49.632836

[20 rows x 10 columns]
'''

# -*- coding: utf-8 -*-

import ccxt
import json
import pandas as pd
import math


class MyInfo:
    exchange = None

    access_key = ''
    secret_key = ''
    commission = 0

    def __init__(self, config_file_name, chains, leverage):
        self.leverage = leverage

        with open(config_file_name) as json_file:
            json_data = json.load(json_file)
            self.access_key = json_data["api_key"]
            self.secret_key = json_data["secret_key"]
            self.commission = float(json_data["commission"])

        self.exchange = ccxt.binance({
            'apiKey': self.access_key,
            'secret': self.secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })

        self.exchange.load_markets()

        for symbol in chains:
            self.exchange.fapiPrivate_post_leverage({
                'symbol': symbol,
                'leverage': leverage,
            })

    def getCommission(self):
        return self.commission

    def getBalance(self, symbol):
        ret = self.exchange.fetch_balance()

        '''
        print(ret['info']['assets'])
        df = pd.DataFrame(data=ret['info']['assets'], columns=['asset', 'walletBalance', 'unrealizedProfit', 'marginBalance', 'maintMargin', 'initialMargin', 'positionInitialMargin', 'openOrderInitialMargin', 'crossWalletBalance', 'crossUnPnl', 'availableBalance'])
        pd.set_option('display.max_columns', None)
        print(df)
        '''

        return ret[symbol]['free'], ret[symbol]['total']

    def getPosition(self, symbol):
        ret = self.exchange.fetch_balance()

        print(ret['info']['positions'])
        df = pd.DataFrame(data=ret['info']['positions'], columns=['symbol', 'initialMargin', 'maintMargin', 'unrealizedProfit', 'positionInitialMargin', 'openOrderInitialMargin', 'leverage', 'isolated', 'entryPrice', 'maxNotional', 'positionSide', 'positionAmt', 'notional', 'isolatedWallet', 'bidNotional', 'askNotional'])
        pd.set_option('display.max_columns', None)
        print(df.query('symbol == "' + symbol + '"'))

    def buyOrder(self, symbol, amount):
        ret = self.exchange.create_market_buy_order(symbol, amount * self.leverage)
        print(ret)

    def sellOrder(self, symbol, amount):
        ret = self.exchange.create_market_sell_order(symbol, amount * self.leverage)
        print(ret)
        # {'info': {'orderId': '21869924860', 'symbol': 'XRPUSDT', 'status': 'FILLED', 'clientOrderId': 'x-xcKtGhcud7d3dd4a62d03a19f60198', 'price': '0', 'avgPrice': '0.40700', 'origQty': '30', 'executedQty': '30', 'cumQty': '30', 'cumQuote': '12.21000', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'updateTime': '1654841602905'}, 'id': '21869924860', 'clientOrderId': 'x-xcKtGhcud7d3dd4a62d03a19f60198', 'timestamp': None, 'datetime': None, 'lastTradeTimestamp': None, 'symbol': 'XRP/USDT', 'type': 'market', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': False, 'side': 'sell', 'price': 0.407, 'stopPrice': None, 'amount': 30.0, 'cost': 12.21, 'average': 0.407, 'filled': 30.0, 'remaining': 0.0, 'status': 'closed', 'fee': None, 'trades': [], 'fees': []}


'''
  asset walletBalance unrealizedProfit marginBalance maintMargin  \
0   DOT    0.00000000       0.00000000    0.00000000  0.00000000   
1   BTC    0.00000000       0.00000000    0.00000000  0.00000000   
2   SOL    0.00000000       0.00000000    0.00000000  0.00000000   
3   BNB    0.00000000       0.00000000    0.00000000  0.00000000   
4   ETH    0.00000000       0.00000000    0.00000000  0.00000000   
5   ADA    0.00000000       0.00000000    0.00000000  0.00000000   
6  USDT  391.06289886       0.00000000  391.06289886  0.00000000   
7   XRP    0.00000000       0.00000000    0.00000000  0.00000000   
8  USDC    0.00000000       0.00000000    0.00000000  0.00000000   
9  BUSD    0.00000000       0.00000000    0.00000000  0.00000000   

  initialMargin positionInitialMargin openOrderInitialMargin  \
0    0.00000000            0.00000000             0.00000000   
1    0.00000000            0.00000000             0.00000000   
2    0.00000000            0.00000000             0.00000000   
3    0.00000000            0.00000000             0.00000000   
4    0.00000000            0.00000000             0.00000000   
5    0.00000000            0.00000000             0.00000000   
6    0.00000000            0.00000000             0.00000000   
7    0.00000000            0.00000000             0.00000000   
8    0.00000000            0.00000000             0.00000000   
9    0.00000000            0.00000000             0.00000000   

  crossWalletBalance  crossUnPnl availableBalance  
0         0.00000000  0.00000000       0.00000000  
1         0.00000000  0.00000000       0.00000000  
2         0.00000000  0.00000000       0.00000000  
3         0.00000000  0.00000000       0.00000000  
4         0.00000000  0.00000000       0.00000000  
5         0.00000000  0.00000000       0.00000000  
6       391.06289886  0.00000000     391.06289886  
7         0.00000000  0.00000000       0.00000000  
8         0.00000000  0.00000000       0.00000000  
9         0.00000000  0.00000000       0.00000000  '''
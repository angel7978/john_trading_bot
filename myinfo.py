# -*- coding: utf-8 -*-

import ccxt
import json
import pandas as pd
import math


class MyInfo:
    exchange = None

    access_key = ''
    secret_key = ''
    using_symbol = ''
    leverage = 5
    exchange_str = 'binance'
    title = ''
    password = ''

    def __init__(self, config_file_name, chains):
        with open(config_file_name) as json_file:
            json_data = json.load(json_file)
            self.access_key = json_data["api_key"]
            self.secret_key = json_data["secret_key"]
            self.using_symbol = json_data["symbol"]
            self.leverage = json_data["leverage"]
            self.exchange_str = json_data["exchange"]
            self.title = json_data['title']
            self.password = json_data['password'] if 'password' in json_data else ''

        if self.exchange_str == 'bitget':
            self.exchange = ccxt.bitget({
                'apiKey': self.access_key,
                'secret': self.secret_key,
                'password': self.password,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap'
                }
            })
        else:
            self.exchange = ccxt.binance({
                'apiKey': self.access_key,
                'secret': self.secret_key,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                }
            })

            for symbol in chains:
                self.exchange.fapiPrivate_post_leverage({
                    'symbol': symbol,
                    'leverage': self.leverage,
                })

        self.exchange.load_markets()

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

        #  print(ret['info']['positions'])
        df = pd.DataFrame(data=ret['info']['positions'], columns=['symbol', 'initialMargin', 'maintMargin', 'unrealizedProfit', 'positionInitialMargin', 'openOrderInitialMargin', 'leverage', 'isolated', 'entryPrice', 'maxNotional', 'positionSide', 'positionAmt', 'notional', 'isolatedWallet', 'bidNotional', 'askNotional'])
        pd.set_option('display.max_columns', None)
        return df.query('symbol == "' + symbol + '"')

    def getOrder(self, order_id, symbol):
        return self.exchange.fetch_order(order_id, symbol)

    def cancelAllOpenOrder(self, symbol):
        ret = self.exchange.fetch_open_orders(symbol)
        for record in ret:
            self.exchange.cancel_order(record['id'], symbol)

    def cancelOrder(self, order_id, symbol):
        return self.exchange.cancel_order(order_id, symbol)

    def buyOrder(self, symbol, amount, price, market=True):
        if market:
            ret = self.exchange.create_market_buy_order(symbol, amount)
        else:
            ret = self.exchange.create_limit_buy_order(symbol, amount, price)
        # print(ret)
        return ret

    def sellOrder(self, symbol, amount, price, market=True):
        if market:
            ret = self.exchange.create_market_sell_order(symbol, amount)
        else:
            ret = self.exchange.create_limit_sell_order(symbol, amount, price)
        # print(ret)
        # {'info': {'orderId': '21869924860', 'symbol': 'XRPUSDT', 'status': 'FILLED', 'clientOrderId': 'x-xcKtGhcud7d3dd4a62d03a19f60198', 'price': '0', 'avgPrice': '0.40700', 'origQty': '30', 'executedQty': '30', 'cumQty': '30', 'cumQuote': '12.21000', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'updateTime': '1654841602905'}, 'id': '21869924860', 'clientOrderId': 'x-xcKtGhcud7d3dd4a62d03a19f60198', 'timestamp': None, 'datetime': None, 'lastTradeTimestamp': None, 'symbol': 'XRP/USDT', 'type': 'market', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': False, 'side': 'sell', 'price': 0.407, 'stopPrice': None, 'amount': 30.0, 'cost': 12.21, 'average': 0.407, 'filled': 30.0, 'remaining': 0.0, 'status': 'closed', 'fee': None, 'trades': [], 'fees': []}
        return ret


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
9         0.00000000  0.00000000       0.00000000  

{'info': {'orderId': '59486857627', 'symbol': 'BTCUSDT', 'status': 'FILLED', 'clientOrderId': 'x-xcKtGhcudb6cb82cce95137a095704', 'price': '0', 'avgPrice': '20333.60000', 'origQty': '0.020', 'executedQty': '0.020', 'cumQty': '0.020', 'cumQuote': '406.67200', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'updateTime': '1655960127298'}, 'id': '59486857627', 'clientOrderId': 'x-xcKtGhcudb6cb82cce95137a095704', 'timestamp': None, 'datetime': None, 'lastTradeTimestamp': None, 'symbol': 'BTC/USDT', 'type': 'market', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': False, 'side': 'sell', 'price': 20333.6, 'stopPrice': None, 'amount': 0.02, 'cost': 406.672, 'average': 20333.6, 'filled': 0.02, 'remaining': 0.0, 'status': 'closed', 'fee': None, 'trades': [], 'fees': []}

'''
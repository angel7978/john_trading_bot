# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook_trend_bb
import time
import datetime
import pandas as pd
from datetime import date
import sys
import json
import traceback
import os
from shutil import copyfile
from functools import reduce

from abc import *


class TickerUpdator(metaclass=ABCMeta):
    balance = {
        'total': 0.0,
        'free': 0.0
    }

    position_data = [
    ]

    is_simulate = False

    def __init__(self, file_name):
        self.info = myinfo.MyInfo(file_name, [])
        self.book = orderbook_trend_bb.OrderBook('binance')

        self.taker_commission = 0.0004  # taker 수수료
        self.entry_amount_per = 0.1  # 진입시 사용되는 USDT
        self.bb_length_thres = 10

    @staticmethod
    def resetData(data):
        data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['stable'] = 0
        data['triggered'] = False

    def sellOrder(self, data, amount, price):
        gain_usdt_leverage = price * amount
        my_usdt_leverage = data['entry'] * data['amount']
        commission = gain_usdt_leverage * self.taker_commission
        pnl = 0

        self.balance['total'] -= commission
        data['commission'] -= commission

        if data['position'] is None:
            data['position'] = 'Short'

            data['amount'] = amount
            data['entry'] = price
            data['using'] = price * amount / self.info.leverage
        elif data['position'] == 'Short':  # chasing
            total_gain = gain_usdt_leverage + my_usdt_leverage
            total_amount = amount + data['amount']

            data['using'] = total_gain / self.info.leverage
            data['amount'] = total_amount
            data['entry'] = self.floor(total_gain / total_amount)
        else:
            if data['amount'] == amount:  # close
                data['position'] = None
                self.resetData(data)

                pnl = gain_usdt_leverage - my_usdt_leverage

                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
            else:  # limit or s/l
                pre_pnl = (price - data['entry']) * data['amount']
                data['using'] -= amount * data['entry'] / self.info.leverage
                data['amount'] -= amount
                post_pnl = (price - data['entry']) * data['amount']

                pnl = pre_pnl - post_pnl
                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
        self.balance['total'] += pnl
        return pnl

    def buyOrder(self, data, amount, price):
        using_usdt_leverage = price * amount
        my_usdt_leverage = data['entry'] * data['amount']
        commission = using_usdt_leverage * self.taker_commission
        pnl = 0

        self.balance['total'] -= commission
        data['commission'] -= commission

        if data['position'] is None:
            data['position'] = 'Long'

            data['amount'] = amount
            data['entry'] = price
            data['using'] = price * amount / self.info.leverage
        elif data['position'] == 'Long':  # chasing
            total_using = using_usdt_leverage + my_usdt_leverage
            total_amount = amount + data['amount']

            data['using'] = total_using / self.info.leverage
            data['amount'] = total_amount
            data['entry'] = self.floor(total_using / total_amount)
        else:
            if data['amount'] == amount:  # close
                data['position'] = None
                self.resetData(data)

                pnl = my_usdt_leverage - using_usdt_leverage

                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
            else:  # limit or s/l
                pre_pnl = (price - data['entry']) * data['amount']
                data['using'] -= amount * data['entry'] / self.info.leverage
                data['amount'] -= amount
                post_pnl = (price - data['entry']) * data['amount']

                pnl = pre_pnl - post_pnl
                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
        self.balance['total'] += pnl
        return pnl

    def isUpTrend(self, candle_trend):
        return candle_trend['rsi'] > 55

    def isDownTrend(self, candle_trend):
        return candle_trend['rsi'] < 45

    @staticmethod
    def createCandle(record):
        return {
            'datetime': record['datetime'],
            'date': record['date'],
            'open': record['open'],
            'close': record['close'],
            'low': record['low'],
            'high': record['high'],
            'rsi': record['rsi'],
            'bb_h': record['bb_bbh'],
            'bb_m': record['bb_bbm'],
            'bb_l': record['bb_bbl'],
            'bb_lp': record['bb_bb_lp'],
            'bb_lp_h': record['bb_bbh_p'],
            'bb_lp_l': record['bb_bbm_p']
        }

    def start(self, simulate=0):
        self.is_simulate = True

        # interval_arr = ['15m', '30m', '1h']
        interval_arr = ['30m']
        trend_interval_arr = ['1d', '12h', '8h', '6h', '4h', '2h']
        logs = ""

        for ticker in self.book.fetch_tickers():
            data = {'symbol': ticker, 'amount_min': 0, 'position': None, 'amount': 0, 'using': 0, 'entry': 0, 'pnl': 0}
            result = []
            self.position_data.append(data)

            # data['df_15m'] = self.book.generate_chart_data(data['symbol'], '15m', simulate * 2 + 100)
            data['df_30m'] = self.book.generate_chart_data(data['symbol'], '30m', simulate + 100)
            # data['df_1h'] = self.book.generate_chart_data(data['symbol'], '1h', int(simulate / 2) + 100)
            data['df_2h'] = self.book.generate_chart_data(data['symbol'], '2h', int(simulate / 4) + 100)
            data['df_4h'] = self.book.generate_chart_data(data['symbol'], '4h', int(simulate / 8) + 100)
            data['df_6h'] = self.book.generate_chart_data(data['symbol'], '6h', int(simulate / 12) + 100)
            data['df_8h'] = self.book.generate_chart_data(data['symbol'], '8h', int(simulate / 16) + 100)
            data['df_12h'] = self.book.generate_chart_data(data['symbol'], '12h', int(simulate / 24) + 100)
            data['df_1d'] = self.book.generate_chart_data(data['symbol'], '1d', int(simulate / 48) + 100)

            try:
                for interval in interval_arr:
                    for trend_interval in trend_interval_arr:
                        self.balance['total'] = self.balance['free'] = 1000.0
                        data['position'] = None
                        self.resetData(data)
                        data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = 0
                        data['input'] = 1

                        interval_df = data['df_%s' % interval]
                        trend_df = data['df_%s' % trend_interval]

                        candle_count = 0
                        if interval == '1h':
                            simulate_max = int(simulate / 2)
                        elif interval == '15m':
                            simulate_max = simulate * 2
                        else:
                            simulate_max = simulate

                        while candle_count < simulate_max:
                            candle_now = self.createCandle(interval_df.iloc[-simulate_max + candle_count])

                            if trend_interval == '2h':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 5400000].iloc[-1])
                            elif trend_interval == '4h':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 12600000].iloc[-1])
                            elif trend_interval == '6h':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 19800000].iloc[-1])
                            elif trend_interval == '8h':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 27000000].iloc[-1])
                            elif trend_interval == '12h':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 41400000].iloc[-1])
                            else:  # trend_interval == '1d':
                                candle_trend = self.createCandle(trend_df.loc[trend_df['datetime'] <= candle_now['datetime'] - 52200000].iloc[-1])

                            if data['position'] is not None:
                                if not data['triggered'] and candle_now['bb_lp'] >= candle_now['bb_lp_h']:
                                    data['triggered'] = True
                                    data['stable'] = 0

                                if data['triggered'] and candle_now['bb_lp'] <= candle_now['bb_lp_l']:
                                    data['stable'] += 1
                                else:
                                    data['stable'] = 0

                                if data['position'] == 'Long':
                                    price = candle_now['close'] + data['amount_min']
                                    if self.is_simulate:
                                        data['pnl'] = (price - data['entry']) * data['amount']

                                    # 손절각일 경우 손절
                                    if not self.isUpTrend(candle_trend) or (candle_now['bb_lp'] >= candle_now['bb_lp_l'] and candle_now['close'] <= candle_now['bb_l']):
                                        reason = '(Trend Change)' if not self.isUpTrend(candle_trend) else '(S/L)'
                                        gain_usdt = data['amount'] * price / self.info.leverage
                                        pnl = self.sellOrder(data, data['amount'], price)

                                        data['stable'] = 0
                                        data['triggered'] = False
                                    elif data['stable'] >= self.bb_length_thres:
                                        if self.isUpTrend(candle_trend):
                                            data['triggered'] = False
                                            data['stable'] = -999
                                        else:
                                            reason = ''
                                            used_usdt = data['amount'] * data['entry'] / self.info.leverage
                                            gain_usdt = data['amount'] * price / self.info.leverage
                                            pnl = self.sellOrder(data, data['amount'], price)

                                            data['stable'] = self.bb_length_thres
                                            data['triggered'] = False

                                else:
                                    price = candle_now['close'] - data['amount_min']
                                    if self.is_simulate:
                                        data['pnl'] = (data['entry'] - price) * data['amount']

                                    # 손절각일 경우 손절
                                    if not self.isDownTrend(candle_trend) or (candle_now['bb_lp'] >= candle_now['bb_lp_l'] and candle_now['close'] >= candle_now['bb_h']):
                                        reason = '(Trend Change)' if not self.isDownTrend(candle_trend) else '(S/L)'
                                        using_usdt = data['amount'] * price / self.info.leverage
                                        pnl = self.buyOrder(data, data['amount'], price)

                                        data['stable'] = 0
                                        data['triggered'] = False
                                    elif data['stable'] >= self.bb_length_thres:
                                        if self.isDownTrend(candle_trend):
                                            data['triggered'] = False
                                            data['stable'] = -999
                                        else:
                                            reason = ''
                                            gained_usdt = data['amount'] * data['entry'] / self.info.leverage
                                            using_usdt = data['amount'] * price / self.info.leverage
                                            pnl = self.buyOrder(data, data['amount'], price)

                                            data['stable'] = self.bb_length_thres
                                            data['triggered'] = False

                            if data['position'] is None:
                                if candle_now['bb_lp'] <= candle_now['bb_lp_l']:
                                    data['stable'] += 1
                                else:
                                    data['stable'] = 0

                                using_usdt = self.balance['total'] * self.entry_amount_per * data['input']

                                long_entry = data['stable'] >= self.bb_length_thres and self.isUpTrend(candle_trend)
                                short_entry = data['stable'] >= self.bb_length_thres and self.isDownTrend(candle_trend)
                                if long_entry:
                                    reason = ''
                                    price = candle_now['close'] + data['amount_min']
                                    amount = using_usdt * self.info.leverage / price
                                    self.buyOrder(data, amount, price)

                                    data['stable'] = 0
                                elif short_entry:
                                    reason = ''
                                    price = candle_now['close'] - data['amount_min']
                                    amount = using_usdt * self.info.leverage / price
                                    self.sellOrder(data, amount, price)

                                    data['stable'] = 0

                            candle_count += 1

                        if data['position'] is not None:
                            self.balance['total'] += data['pnl']

                        result.append({
                            'it': interval,
                            'trend': trend_interval,
                            'pnl': self.balance['total']
                        })

            except Exception as e:
                # traceback.print_exc()
                data['interval'] = '30m'
                data['trend_interval'] = '1d'
                data['best_pnl'] = 0
                data['average_pnl'] = 0
                data['worst_pnl'] = 0
                continue

            sorted_result = sorted(result, key=lambda it: it['pnl'], reverse=True)
            print('%s : %s' % (data['symbol'], sorted_result))
            logs += '%s : %s\n' % (data['symbol'], sorted_result)
            data['interval'] = sorted_result[0]['it']
            data['trend_interval'] = sorted_result[0]['trend']
            data['best_pnl'] = sorted_result[0]['pnl']
            data['worst_pnl'] = sorted_result[len(sorted_result) - 1]['pnl']
            data['average_pnl'] = reduce(lambda x, y: x + y, map(lambda it: it['pnl'], result)) / len(result)

        with open('tickers.json') as json_file:
            json_data = json.load(json_file)

        '''
        for j_data in json_data:
            if 'trend_interval' not in j_data:
                j_data['trend_interval'] = ''
            if 'best_pnl' not in j_data:
                j_data['best_pnl'] = 0
            if 'average_pnl' not in j_data:
                j_data['average_pnl'] = 0
            if 'worst_pnl' not in j_data:
                j_data['worst_pnl'] = 0
        '''

        for record in self.position_data:
            print('[%s] It %s Trend %s PnL %.4f' % (record['symbol'], record['interval'], record['trend_interval'], record['best_pnl']))
            logs += '[%s] It %s Trend %s PnL %.4f\n' % (record['symbol'], record['interval'], record['trend_interval'], record['best_pnl'])

            found = False
            for j_data in json_data:
                if j_data['symbol'] == record['symbol']:
                    j_data['interval'] = record['interval']
                    j_data['trend_interval'] = record['trend_interval']
                    j_data['best_pnl'] = record['best_pnl']
                    j_data['worst_pnl'] = record['worst_pnl']
                    j_data['average_pnl'] = record['average_pnl']
                    found = True
                    break

            if not found:
                json_data.append({
                    'symbol': record['symbol'],
                    'interval': record['interval'],
                    'trend_interval': record['trend_interval'],
                    'best_pnl': record['best_pnl'],
                    'worst_pnl': record['worst_pnl'],
                    'average_pnl': record['average_pnl'],
                    "amount_min": 0,
                })

        for record in self.book.fetch_markets():
            if 'USDT' not in record['id']:
                continue

            for j_data in json_data:
                if record['id'] == j_data['symbol']:
                    j_data['amount_min'] = 1 / pow(10, record['precision']['price'])
                    break

        json_data = sorted(json_data, key=lambda item: item['best_pnl'], reverse=True)

        with open("tickers.json", "w") as json_file:
            json.dump(json_data, json_file, indent=4)

        date_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")
        copyfile('tickers.json', 'tickers_backup/%s_trend_tickers.json' % date_str)
        with open('logs/%s_log.json' % date_str, "w") as log_file:
            log_file.write(logs)

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

TickerUpdator(config_file_name).start(48 * 365)


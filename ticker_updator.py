# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook
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
        self.book = orderbook.OrderBook('binance')

        self.taker_commission = 0.0004
        self.entry_amount_per = 0.2
        self.added_amount_per = 0.05
        self.stop_loss_threshold_total_per = 0.5
        self.stop_loss_amount_per = 0.5
        self.close_position_threshold_bb_height = 0.80
        self.chasing_target_profit = 0.01
        self.chasing_maximum_total_per = 0.1
        self.forced_close_min_length = 12
        self.forced_close_bb_length_thres_per = 0.015

    def checkSellOrderForSimulation(self, data, amount, price, date):
        gain_usdt = amount * price / self.info.leverage
        pnl = self.sellOrder(data, amount, price)

    def makeSellOrder(self, data, amount, price, candle_now, candle_prev):
        if candle_now['high'] >= candle_prev['bb_h']:
            gain_usdt = data['amount'] * price / self.info.leverage
            pnl = self.sellOrder(data, amount, candle_prev['bb_h'])

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
                if data['position_length'] not in data['closing_length']:
                    data['closing_length'][data['position_length']] = 0
                data['closing_length'][data['position_length']] += 1
                data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['position_length'] = data['tp_price'] = data['tp_price_best'] = data['chasing_amount'] = data['chasing_remain'] = 0

                pnl = gain_usdt_leverage - my_usdt_leverage

                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
            else:  # s/l
                pre_pnl = (price - data['entry']) * data['amount']
                data['using'] -= amount * data['entry'] / self.info.leverage
                data['amount'] -= amount
                post_pnl = (price - data['entry']) * data['amount']

                pnl = pre_pnl - post_pnl
                data['loss'] += pnl
        self.balance['total'] += pnl
        return pnl

    def checkBuyOrderForSimulation(self, data, amount, price, date):
        if self.is_simulate:
            using_usdt = amount * price / self.info.leverage
            pnl = self.buyOrder(data, amount, price)

    def makeBuyOrder(self, data, amount, price, candle_now, candle_prev):
        if candle_now['low'] <= candle_prev['bb_l']:
            using_usdt = data['amount'] * price / self.info.leverage
            pnl = self.buyOrder(data, amount, candle_prev['bb_l'])

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
                if data['position_length'] not in data['closing_length']:
                    data['closing_length'][data['position_length']] = 0
                data['closing_length'][data['position_length']] += 1
                data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['position_length'] = data['tp_price'] = data['tp_price_best'] = data['chasing_amount'] = data['chasing_remain'] = 0

                pnl = my_usdt_leverage - using_usdt_leverage

                if pnl > 0:
                    data['win'] += 1
                    data['profit'] += pnl
                else:
                    data['lose'] += 1
                    data['loss'] += pnl
            else:  # s/l
                pre_pnl = (price - data['entry']) * data['amount']
                data['using'] -= amount * data['entry'] / self.info.leverage
                data['amount'] -= amount
                post_pnl = (price - data['entry']) * data['amount']

                pnl = post_pnl - pre_pnl
                data['loss'] += pnl
        self.balance['total'] += pnl
        return pnl

    def runChasing(self, data, amount, close, date_for_simulation=''):
        if data['chasing_amount'] == 0 or data['chasing_remain'] == 0 or data['position'] is None:
            data['chasing_amount'] = data['chasing_remain'] = 0
            return

        amount *= 3
        data['chasing_remain'] = 1

        if data['position'] == 'Long':
            # 물타기
            price = close + data['amount_min']
            self.buyOrder(data, amount, price)
        elif data['position'] == 'Short':
            # 물타기
            price = close - data['amount_min']
            self.sellOrder(data, amount, price)

        data['chasing_remain'] -= 1

        if data['chasing_remain'] == 0:
            data['chasing_amount'] = 0

    @staticmethod
    def createCandle(record):
        return {
            'datetime': record['datetime'],
            'date': record['date'],
            'open': record['open'],
            'close': record['close'],
            'low': record['low'],
            'high': record['high'],
            'bb_h': record['bb_bbh'],
            'bb_m': record['bb_bbm'],
            'bb_l': record['bb_bbl'],
            'rsi': record['rsi'],
            'volume': record['volume'],
            'bb_vm': record['bb_vm'],
            'bb_vh': record['bb_vh']
        }

    def start(self, simulate=0):
        self.is_simulate = True

        interval_arr = ['15m', '30m', '1h']
        sl_interval_arr = ['1d', '12h', '8h', '6h', '4h', '2h']
        logs = ""

        for ticker in self.book.fetch_tickers():
            data = {'symbol': ticker, 'amount_min': 0, 'position': None, 'amount': 0, 'using': 0, 'entry': 0, 'pnl': 0}
            result = []
            self.position_data.append(data)

            data['df_15m'] = self.book.generate_chart_data(data['symbol'], '15m', simulate * 2 + 100)
            data['df_30m'] = self.book.generate_chart_data(data['symbol'], '30m', simulate + 100)
            data['df_1h'] = self.book.generate_chart_data(data['symbol'], '1h', int(simulate / 2) + 100)
            data['df_2h'] = self.book.generate_chart_data(data['symbol'], '2h', int(simulate / 4) + 100)
            data['df_4h'] = self.book.generate_chart_data(data['symbol'], '4h', int(simulate / 8) + 100)
            data['df_6h'] = self.book.generate_chart_data(data['symbol'], '6h', int(simulate / 12) + 100)
            data['df_8h'] = self.book.generate_chart_data(data['symbol'], '8h', int(simulate / 16) + 100)
            data['df_12h'] = self.book.generate_chart_data(data['symbol'], '12h', int(simulate / 24) + 100)
            data['df_1d'] = self.book.generate_chart_data(data['symbol'], '1d', int(simulate / 48) + 100)

            try:
                for interval in interval_arr:
                    for sl_interval in sl_interval_arr:
                        self.balance['total'] = self.balance['free'] = 1000.0
                        data['position'] = None
                        data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = data['position_length'] = data['chasing_amount'] = data['chasing_remain'] = data['tp_price'] = data['tp_price_best'] = 0
                        data['closing_length'] = {}

                        interval_df = data['df_%s' % interval]
                        sl_df = data['df_%s' % sl_interval]

                        candle_count = 0
                        if interval == '1h':
                            simulate_max = int(simulate / 2)
                        elif interval == '15m':
                            simulate_max = simulate * 2
                        else:
                            simulate_max = simulate

                        while candle_count < simulate_max:
                            candle_prev = self.createCandle(interval_df.iloc[-simulate_max + candle_count - 1])
                            candle_now = self.createCandle(interval_df.iloc[-simulate_max + candle_count])

                            if sl_interval == '2h':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 7200000].iloc[-1])
                            elif sl_interval == '4h':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 14400000].iloc[-1])
                            elif sl_interval == '6h':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 21600000].iloc[-1])
                            elif sl_interval == '8h':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 28800000].iloc[-1])
                            elif sl_interval == '12h':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 43200000].iloc[-1])
                            else:  # sl_interval == '1d':
                                candle_sl = self.createCandle(sl_df.loc[sl_df['datetime'] <= candle_now['datetime'] - 54000000].iloc[-1])

                            if data['position'] == 'Long' and data['tp_price'] != 0 and candle_now['low'] <= data['tp_price']:
                                self.checkSellOrderForSimulation(data, data['amount'], data['tp_price'] - data['amount_min'], candle_now['date'])
                            elif data['position'] == 'Short' and data['tp_price'] != 0 and candle_now['high'] >= data['tp_price']:
                                self.checkBuyOrderForSimulation(data, data['amount'], data['tp_price'] + data['amount_min'], candle_now['date'])

                            if data['position'] == 'Long':
                                price = candle_now['close'] + data['amount_min']
                                if self.is_simulate:
                                    data['pnl'] = (price - data['entry']) * data['amount']

                                # 종료 체크
                                now_clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                                low_bb = candle_sl['low'] < candle_sl['bb_l']
                                forced_close_by_bb = data['position_length'] >= self.forced_close_min_length and (candle_now['bb_h'] - candle_now['bb_l']) / candle_now['bb_m'] < self.forced_close_bb_length_thres_per
                                if forced_close_by_bb or now_clearing_price < candle_now['close'] or low_bb or data['tp_price'] != 0:
                                    pending_by_volume = data['tp_price'] == 0 and candle_now['volume'] >= candle_now['bb_vh']
                                    if pending_by_volume:
                                        data['tp_price'] = now_clearing_price
                                        data['tp_price_best'] = candle_now['close']

                                    update_tp_price = data['tp_price'] != 0 and data['tp_price_best'] < candle_now['close'] and candle_now['volume'] >= candle_now['bb_vh']
                                    if update_tp_price:
                                        data['tp_price'] = data['tp_price_best']
                                        data['tp_price_best'] = candle_now['close']

                                    close_by_volume = data['tp_price'] != 0 and candle_now['volume'] <= candle_now['bb_vm']

                                    if data['tp_price'] == 0 or close_by_volume:
                                        reason = ''
                                        if forced_close_by_bb:
                                            reason = '(BB 폭이 좁아져 강제 종료)'
                                        elif low_bb:
                                            reason = '(이전 %s 캔들이 BB 하단 돌파)' % sl_interval
                                        used_usdt = data['amount'] * data['entry'] / self.info.leverage
                                        gain_usdt = data['amount'] * price / self.info.leverage
                                        pnl = self.sellOrder(data, data['amount'], price)
                                else:
                                    chasing_reason = ''
                                    # 물타기 체크
                                    if candle_now['open'] < candle_now['bb_l'] < candle_now['close']:
                                        chasing_reason += 'B1'
                                    elif candle_prev['open'] < candle_prev['close'] < candle_prev['bb_l'] and candle_now['bb_l'] < candle_now['open'] < candle_now['close']:
                                        chasing_reason += 'B2'
                                    if candle_prev['rsi'] < 30 < candle_now['rsi']:
                                        chasing_reason += 'R'

                                    if chasing_reason != '':
                                        clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                                        if clearing_price < data['entry']:
                                            # (평단가 * 현재 개수 + 지금 가격 * x개) * 101% = 정리 가격 * (현재 개수 + x개)
                                            chasing_amount = (data['entry'] * (1 + self.chasing_target_profit) - clearing_price) * data['amount'] / (clearing_price - candle_now['close'] * (1 + self.chasing_target_profit))
                                            # print('    Chasing Entry %.4f Amount %.4f Now %.4f Clear %.4f Chasing amount %.4f' % (data['entry'], data['amount'], candle_now['close'], clearing_price, chasing_amount))
                                            if chasing_amount * candle_now['close'] > self.balance['total'] * self.chasing_maximum_total_per * self.info.leverage:
                                                chasing_amount = self.balance['total'] * self.chasing_maximum_total_per / candle_now['close']
                                                # print('    Chasing amount modified %.4f' % chasing_amount)
                                                data['chasing_amount'] = chasing_amount if chasing_amount > 0 else 0
                                                data['chasing_remain'] = 3 if chasing_amount > 0 else 0

                                    # 손절각일 경우 손절
                                    if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                        gain_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                        pnl = self.sellOrder(data, data['amount'] * self.stop_loss_amount_per, price)
                            else:
                                price = candle_now['close'] - data['amount_min']
                                if self.is_simulate:
                                    data['pnl'] = (data['entry'] - price) * data['amount']

                                # 종료 체크
                                now_clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                                high_bb = candle_sl['high'] > candle_sl['bb_h']
                                forced_close_by_bb = data['position_length'] >= self.forced_close_min_length and (candle_now['bb_h'] - candle_now['bb_l']) / candle_now['bb_m'] < self.forced_close_bb_length_thres_per
                                if forced_close_by_bb or now_clearing_price > candle_now['close'] or high_bb or data['tp_price'] != 0:
                                    pending_by_volume = data['tp_price'] == 0 and candle_now['volume'] >= candle_now['bb_vh']
                                    if pending_by_volume:
                                        data['tp_price'] = now_clearing_price
                                        data['tp_price_best'] = candle_now['close']

                                    update_tp_price = data['tp_price'] != 0 and data['tp_price_best'] > candle_now['close'] and candle_now['volume'] >= candle_now['bb_vh']
                                    if update_tp_price:
                                        data['tp_price'] = data['tp_price_best']
                                        data['tp_price_best'] = candle_now['close']

                                    close_by_volume = data['tp_price'] != 0 and candle_now['volume'] <= candle_now['bb_vm']

                                    if data['tp_price'] == 0 or close_by_volume:
                                        reason = ''
                                        if forced_close_by_bb:
                                            reason = '(BB 폭이 좁아져 강제 종료)'
                                        elif high_bb:
                                            reason = '(이전 %s 캔들이 BB 상단 돌파)' % sl_interval

                                        gained_usdt = data['amount'] * data['entry'] / self.info.leverage
                                        using_usdt = data['amount'] * price / self.info.leverage
                                        pnl = self.buyOrder(data, data['amount'], price)
                                else:
                                    chasing_reason = ''
                                    # 물타기 체크
                                    if candle_now['open'] > candle_now['bb_h'] > candle_now['close']:
                                        chasing_reason += 'B1'
                                    elif candle_prev['open'] > candle_prev['close'] > candle_prev['bb_h'] and candle_now['bb_h'] > candle_now['open'] > candle_now['close']:
                                        chasing_reason += 'B2'
                                    if candle_prev['rsi'] > 70 > candle_now['rsi']:
                                        chasing_reason += 'R'

                                    if chasing_reason != '':
                                        clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height + 0.00
                                        if clearing_price > data['entry']:
                                            # (평단가 * 현재 개수 + 지금 가격 * x개) * 99% = 정리 가격 * (현재 개수 + x개)
                                            chasing_amount = (clearing_price - data['entry'] * (1 - self.chasing_target_profit)) * data['amount'] / (candle_now['close'] * (1 - self.chasing_target_profit) - clearing_price)
                                            # print('    Chasing Entry %.4f Amount %.4f Now %.4f Clear %.4f Chasing amount %.4f' % (data['entry'], data['amount'], candle_now['close'], clearing_price, chasing_amount))
                                            if chasing_amount * candle_now['close'] > self.balance['total'] * self.chasing_maximum_total_per * self.info.leverage:
                                                chasing_amount = self.balance['total'] * self.chasing_maximum_total_per / candle_now['close']
                                                # print('    Chasing amount modified %.4f' % chasing_amount)
                                                data['chasing_amount'] = chasing_amount if chasing_amount > 0 else 0
                                                data['chasing_remain'] = 3 if chasing_amount > 0 else 0

                                    # 손절각일 경우 손절
                                    if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                        using_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                        pnl = self.buyOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                            # 진입 체크
                            if data['position'] is None:
                                using_usdt = self.balance['total'] * self.entry_amount_per

                                if candle_sl['low'] >= candle_sl['bb_l'] and candle_now['close'] < candle_now['bb_l']:
                                    price = candle_now['close'] + data['amount_min']
                                    amount = using_usdt * self.info.leverage / price
                                    self.buyOrder(data, amount, price)

                                elif candle_sl['high'] <= candle_sl['bb_h'] and candle_now['close'] > candle_now['bb_h']:
                                    price = candle_now['close'] - data['amount_min']
                                    amount = using_usdt * self.info.leverage / price
                                    self.sellOrder(data, amount, price)

                            self.runChasing(data, data['chasing_amount'] / 3, candle_now['close'], candle_now['date'])

                            candle_count += 1

                        result.append({
                            'it': interval,
                            'sl': sl_interval,
                            'pnl': self.balance['total']
                        })

            except Exception as e:
                traceback.print_exc()
                data['interval'] = '30m'
                data['sl_interval'] = '1d'
                data['best_pnl'] = 0
                data['average_pnl'] = 0
                data['worst_pnl'] = 0
                continue

            sorted_result = sorted(result, key=lambda it: it['pnl'], reverse=True)
            print('%s : %s' % (data['symbol'], sorted_result))
            logs += '%s : %s\n' % (data['symbol'], sorted_result)
            data['interval'] = sorted_result[0]['it']
            data['sl_interval'] = sorted_result[0]['sl']
            data['best_pnl'] = sorted_result[0]['pnl']
            data['worst_pnl'] = sorted_result[len(sorted_result) - 1]['pnl']
            data['average_pnl'] = reduce(lambda x, y: x + y, map(lambda it: it['pnl'], result)) / len(result)

        with open('tickers.json') as json_file:
            json_data = json.load(json_file)

        '''
        for j_data in json_data:
            if 'sl_interval' not in j_data:
                j_data['sl_interval'] = ''
            if 'best_pnl' not in j_data:
                j_data['best_pnl'] = 0
            if 'average_pnl' not in j_data:
                j_data['average_pnl'] = 0
            if 'worst_pnl' not in j_data:
                j_data['worst_pnl'] = 0
        '''

        for record in self.position_data:
            print('[%s] I %s SI %s PnL %.4f' % (record['symbol'], record['interval'], record['sl_interval'], record['best_pnl']))
            logs += '[%s] I %s SI %s PnL %.4f\n' % (record['symbol'], record['interval'], record['sl_interval'], record['best_pnl'])

            found = False
            for j_data in json_data:
                if j_data['symbol'] == record['symbol']:
                    j_data['interval'] = record['interval']
                    j_data['sl_interval'] = record['sl_interval']
                    j_data['best_pnl'] = record['best_pnl']
                    j_data['worst_pnl'] = record['worst_pnl']
                    j_data['average_pnl'] = record['average_pnl']
                    found = True
                    break

            if not found:
                json_data.append({
                    'symbol': record['symbol'],
                    'interval': record['interval'],
                    'sl_interval': record['sl_interval'],
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

        date_str = date.today().strftime("%Y_%d_%m_%H_%M")
        copyfile('tickers.json', 'tickers_backup/tickers_%s.json' % date_str)
        with open('logs/log_%s.json' % date_str, "w") as log_file:
            log_file.write(logs)

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

TickerUpdator(config_file_name).start(48 * 30)


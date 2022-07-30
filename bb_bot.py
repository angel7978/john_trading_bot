# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook
import time
import datetime
import pandas as pd
import json
import sys

from abc import *


class Bot(metaclass=ABCMeta):
    title = 'BB Bot'
    using_pnl_shortcut = True
    simulation_usdt = 1000
    balance = {
        'total': 0.0,
        'free': 0.0
    }
    positions_data = [
        {
            "symbol": "BTCUSDT",
            "amount_min": 0.1,
            "sl_interval": "8h",
            "interval": "30m",
            "fever_mode": False
        },
        {
            "symbol": "ETHUSDT",
            "amount_min": 0.01,
            "sl_interval": "6h",
            "interval": "30m",
            "fever_mode": False
        },
        {
            "symbol": "BCHUSDT",
            "amount_min": 0.01,
            "sl_interval": "8h",
            "interval": "30m",
            "fever_mode": False
        },
        {
            "symbol": "LTCUSDT",
            "amount_min": 0.01,
            "sl_interval": "4h",
            "interval": "30m",
            "fever_mode": False
        },
        {
            "symbol": "ETCUSDT",
            "amount_min": 0.001,
            "sl_interval": "2h",
            "interval": "30m",
            "fever_mode": True
        }
    ]
    simulate_const = {
        '15m': {
            'sl_mul': 0.5,
            'simulate_candle_div': 1
        },
        '30m': {
            'sl_mul': 1,
            'simulate_candle_div': 2
        },
        '1h': {
            'sl_mul': 2,
            'simulate_candle_div': 4
        },
        '2h': {
            'sl_div': 4,
            'candle_offset': 5400000
        },
        '4h': {
            'sl_div': 8,
            'candle_offset': 12600000
        },
        '6h': {
            'sl_div': 12,
            'candle_offset': 19800000
        },
        '8h': {
            'sl_div': 16,
            'candle_offset': 27000000
        },
        '12h': {
            'sl_div': 24,
            'candle_offset': 41400000
        },
        '1d': {
            'sl_div': 48,
            'candle_offset': 52200000
        },
    }
    is_simulate = False

    def __init__(self, file_name):
        # with open('tickers.json') as json_file:
        #     self.positions_data = json.load(json_file)

        self.info = myinfo.MyInfo(file_name, list(map(lambda d: d['symbol'], self.positions_data)))
        self.book = orderbook.OrderBook(self.info.exchange_str)
        self.telegram = telegram_module.Telegram(file_name)

        self.title = self.info.title

        data_length = 0
        for data in self.positions_data:
            data['enabled'] = data['symbol'] in self.info.using_symbol
            data_length += 1 if data['enabled'] else 0

        if data_length == 0:
            self.sendTelegramPush(self.title, '체인이 선택되지 않았습니다!! config 파일을 확인 해 주세요. [%s]' % self.info.using_symbol)

        self.taker_commission = 0.0004  # taker 수수료
        self.entry_amount_per = 0.1  # 진입시 사용되는 USDT
        self.stop_loss_threshold_total_per = 0.2  # 손절 상한
        self.stop_loss_amount_per = 0.5  # 손절 시 털어낼 비율
        self.close_position_threshold_bb_height = 0.80
        self.chasing_target_profit = 0.01
        self.chasing_maximum_total_per = 0.1
        self.forced_close_min_length = 12
        self.forced_close_bb_length_thres_per = 0.015

    def updateBalance(self):
        if self.is_simulate:
            if self.balance['total'] == 0:
                self.balance['total'] = self.balance['free'] = self.simulation_usdt
        else:
            balance = self.info.getBalance('USDT')
            self.balance['free'] = balance[0]
            self.balance['total'] = balance[1]

    def updatePositions(self, data):
        if self.is_simulate:
            return

        record = self.info.getPosition(data['symbol'])
        amount = float(record['positionAmt'])
        if amount < 0:
            data['position'] = 'Short'
            data['amount'] = -amount
        elif amount > 0:
            data['position'] = 'Long'
            data['amount'] = amount
        else:
            if data['tp_price'] != 0:
                self.notifyTPClose(data)

            data['position'] = None
            data['amount'] = data['position_length'] = data['tp_price'] = data['tp_price_best'] = 0
        data['using'] = float(record['positionInitialMargin'])
        data['entry'] = float(record['entryPrice'])
        data['pnl'] = float(record['unrealizedProfit'])

    def notifyTPClose(self, data):
        if self.is_simulate:
            return

        now = datetime.datetime.now() - datetime.timedelta(minutes=30)
        date = now.strftime("%Y-%m-%d %H:%M:00")

        if data['position'] == 'Long':
            used_usdt = data['amount'] * data['entry'] / self.info.leverage
            gain_usdt = data['amount'] * data['tp_price'] / self.info.leverage
            pnl = (gain_usdt - used_usdt) * self.info.leverage

            print('%s [%s] Long Close (TP/SL) - Size (%.4f USDT)' % (date, data['symbol'], gain_usdt))
            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
            self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Long 종료 (T/P)', 'Size (%.4f USDT -> %.4f USDT)' % (used_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

        elif data['position'] == 'Short':
            gained_usdt = data['amount'] * data['entry'] / self.info.leverage
            using_usdt = data['amount'] * data['tp_price'] / self.info.leverage
            pnl = (gained_usdt - using_usdt) * self.info.leverage

            print('%s [%s] Short Close (TP/SL) - Size (%.4f USDT)' % (date, data['symbol'], using_usdt))
            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
            self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Short 종료 (T/P)', 'Size (%.4f USDT -> %.4f USDT)' % (gained_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

    def waitUntilOrderDone(self, order_id, symbol):
        if self.is_simulate:
            return

        time.sleep(10)

        '''
        ret = self.info.getOrder(order_id, symbol)

        for i in range(10):
            if ret['status'] == 'closed':
                return

            time.sleep(1)
            ret = self.info.getOrder(order_id, symbol)

        print('Order closing timeout')
        self.sendTelegramPush(self.title, '거래 에러', '주문이 닫히지 않습니다. 확인 해 주세요.')
        '''

    def cancelAllOpenOrder(self, symbol):
        if self.is_simulate:
            return

        self.info.cancelAllOpenOrder(symbol)

    def checkSellOrderForSimulation(self, data, amount, price, date):
        if self.is_simulate:
            gain_usdt = amount * price / self.info.leverage
            pnl = self.sellOrder(data, amount, price)

            print('%s [%s] Long Close (T/P) - Size (%.4f USDT)' % (date, data['symbol'], gain_usdt))
            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

    def makeSellOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.sellOrder(data['symbol'], amount, price, False)

    def makeTPSellOrder(self, data):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], data['amount'], data['tp_price'], True)

    def sellOrder(self, data, amount, price):
        if self.is_simulate:
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
        else:
            pre_pnl = data['pnl']
            ret = self.info.sellOrder(data['symbol'], amount, price)

            self.waitUntilOrderDone(ret['id'], data['symbol'])

            self.updatePositions(data)
            self.updateBalance()

            post_pnl = data['pnl']

            return self.floor(pre_pnl - post_pnl)

    def checkBuyOrderForSimulation(self, data, amount, price, date):
        if self.is_simulate:
            using_usdt = amount * price / self.info.leverage
            pnl = self.buyOrder(data, amount, price)

            print('%s [%s] Short Close (T/P) - Size (%.4f USDT)' % (date, data['symbol'], using_usdt))
            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

    def makeBuyOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.buyOrder(data['symbol'], amount, price, False)

    def makeTPBuyOrder(self, data):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], data['amount'], data['tp_price'], False)

    def buyOrder(self, data, amount, price):
        if self.is_simulate:
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
        else:
            pre_pnl = data['pnl']
            ret = self.info.buyOrder(data['symbol'], amount, price)

            self.waitUntilOrderDone(ret['id'], data['symbol'])

            self.updatePositions(data)
            self.updateBalance()

            post_pnl = data['pnl']

            return self.floor(pre_pnl - post_pnl)

    def runChasing(self, data, amount, close, date_for_simulation=''):
        if data['chasing_amount'] == 0 or data['chasing_remain'] == 0 or data['position'] is None:
            data['chasing_amount'] = data['chasing_remain'] = 0
            return

        if self.is_simulate:
            amount *= 3
            date = date_for_simulation
            data['chasing_remain'] = 1
        else:
            now = datetime.datetime.now()
            date = now.strftime("%Y-%m-%d %H:%M:00")

        if data['position'] == 'Long':
            # 물타기
            price = close + data['amount_min']
            self.buyOrder(data, amount, price)

            print('%s [%s] Long Chasing %d/3 (%.4f USDT) - Size (%.4f USDT / %.4f USDT)' % (date, data['symbol'], 4 - data['chasing_remain'], amount * price / self.info.leverage, data['using'], self.balance['total']))
            self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Long 추매 %d/3' % (4 - data['chasing_remain']), 'Size (%.4f USDT / %.4f USDT)' % (data['using'], self.balance['total']))
        elif data['position'] == 'Short':
            # 물타기
            price = close - data['amount_min']
            self.sellOrder(data, amount, price)

            print('%s [%s] Short Chasing %d/3 (%.4f USDT) - Size (%.4f USDT / %.4f USDT)' % (date, data['symbol'], 4 - data['chasing_remain'], amount * price / self.info.leverage, data['using'], self.balance['total']))
            self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Short 추매 %d/3' % (4 - data['chasing_remain']), 'Size (%.4f USDT / %.4f USDT)' % (data['using'], self.balance['total']))

        data['chasing_remain'] -= 1

        if data['chasing_remain'] == 0:
            data['chasing_amount'] = 0

    def waitUntil15CandleMade(self):
        if self.is_simulate:
            return

        for data in self.positions_data:
            if data['chasing_amount'] > 0 and data['chasing_remain'] > 0:
                time.sleep(600)
                return

        # 15분에 맞게 대기
        minute = datetime.datetime.now().minute
        second = datetime.datetime.now().second

        mod = minute % 15
        waiting_time_sec = (14 - mod) * 60 + (60 - second) + 1
        print('Wait %d sec' % waiting_time_sec)
        time.sleep(waiting_time_sec)

    @staticmethod
    def getExpectedPnL(data, price, amount, close_price, close_price_inc, is_long=True):
        if 'closing_rate' not in data:
            print('There is no closing_rate in data')
            return 0

        expected_pnl_list = []
        for item in data['closing_rate']:
            expected_pnl_list.append({
                'length': item['length'],
                'rate': item['rate'],
                'expected_pnl': ((close_price + close_price_inc * item['length'] ) - price) * amount * (1 if is_long else -1) #  * pow(0.9, item['length'])
            })

        expected_pnl = 0
        for item in expected_pnl_list:
            expected_pnl += item['rate'] * item['expected_pnl']

        # print('%.4f, %.4f, %.4f, %.4f' % (price, amount, close_price, close_price_inc))
        # print('  expected pnl = %.4f, unrealized pnl = %.4f, raw = %s' % (expected_pnl, data['pnl'], expected_pnl_list))
        return expected_pnl

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

    def sendTelegramPush(self, *msgs):
        if self.is_simulate:
            return

        self.telegram.sendTelegramPush(*msgs)

    def start(self, simulate=0):
        self.is_simulate = simulate != 0

        self.updateBalance()

        print('Bot start!, Free (%.4f USDT), Total (%.4f USDT)' % (self.balance['free'], self.balance['total']))
        self.sendTelegramPush(self.title, 'Bot start!', 'Free (%.4f USDT), Total (%.4f USDT)' % (self.balance['free'], self.balance['total']))

        for data in self.positions_data:
            data['position'] = None
            data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = data['position_length'] = data['chasing_amount'] = data['chasing_remain'] = data['tp_price'] = data['tp_price_best'] = 0
            data['closing_length'] = {}
            data['input'] = 1 if data['symbol'] not in self.info.input else self.info.input[data['symbol']]
            self.updatePositions(data)
            if data['position'] is not None or data['enabled']:
                print('    [%s] Position (%s), Size (%.4f USDT)' % (data['symbol'], data['position'], data['using']))

        if self.is_simulate:
            for data in self.positions_data:
                if not data['enabled']:
                    continue

                data['df_interval'] = self.book.generate_chart_data(data['symbol'], data['interval'], int(simulate / self.simulate_const[data['interval']]['simulate_candle_div']) + 100)
                data['df_sl_interval'] = self.book.generate_chart_data(data['symbol'], data['sl_interval'], int(simulate * self.simulate_const[data['interval']]['sl_mul'] / self.simulate_const[data['sl_interval']]['sl_div']) + 100)

        candle_count = 0
        while not self.is_simulate or candle_count < simulate:
            self.waitUntil15CandleMade()

            self.updateBalance()

            for data in self.positions_data:
                if data['position'] is None and not data['enabled']:
                    continue

                self.updatePositions(data)

                if self.is_simulate:
                    bonus_candle_count = 0
                    minute = datetime.datetime.now().minute
                    if data['interval'] == '30m':
                        bonus_candle_count = 1 if 15 <= minute < 30 or 45 <= minute < 60 else 0
                    elif data['interval'] == '1h':
                        bonus_candle_count = int(minute / 15)

                    if (candle_count + bonus_candle_count) % self.simulate_const[data['interval']]['simulate_candle_div'] != 0:
                        continue
                    candle_idx = int((-simulate + candle_count) / self.simulate_const[data['interval']]['simulate_candle_div'])
                    if candle_idx >= 0:
                        continue
                    candle_prev = self.createCandle(data['df_interval'].iloc[candle_idx - 1])
                    candle_now = self.createCandle(data['df_interval'].iloc[candle_idx])
                    candle_sl = self.createCandle(data['df_sl_interval'].loc[data['df_sl_interval']['datetime'] <= candle_now['datetime'] - self.simulate_const[data['sl_interval']]['candle_offset']].iloc[-1])
                else:
                    minute = datetime.datetime.now().minute
                    if data['chasing_amount'] > 0 or data['chasing_remain'] > 0:
                        self.runChasing(data, data['chasing_amount'] / 3, self.book.get_last_price(data['symbol']))

                    if data['interval'] == '30m' and minute % 30 != 0:
                        continue
                    elif data['interval'] == '1h' and minute != 0:
                        continue

                    df_interval = self.book.generate_chart_data(data['symbol'], data['interval'])
                    df_sl = self.book.generate_chart_data(data['symbol'], data['sl_interval'])

                    candle_prev = self.createCandle(df_interval.iloc[-2])
                    candle_now = self.createCandle(df_interval.iloc[-1])
                    candle_sl = self.createCandle(df_sl.iloc[-1])

                    print("- Log [%s]" % data['symbol'])
                    print('    candle %s' % candle_now)

                if self.is_simulate:
                    if data['position'] == 'Long' and data['tp_price'] != 0 and candle_now['low'] <= data['tp_price']:
                        self.checkSellOrderForSimulation(data, data['amount'], data['tp_price'] - data['amount_min'], candle_now['date'])
                    elif data['position'] == 'Short' and data['tp_price'] != 0 and candle_now['high'] >= data['tp_price']:
                        self.checkBuyOrderForSimulation(data, data['amount'], data['tp_price'] + data['amount_min'], candle_now['date'])

                if data['position'] is not None:
                    data['position_length'] += 1

                    if data['position'] == 'Long':
                        price = candle_now['close'] + data['amount_min']
                        if self.is_simulate:
                            data['pnl'] = (price - data['entry']) * data['amount']

                        # 종료 체크
                        low_bb = candle_sl['low'] < candle_sl['bb_l']
                        now_clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        forced_close_by_bb = data['position_length'] >= self.forced_close_min_length and (candle_now['bb_h'] - candle_now['bb_l']) / candle_now['bb_m'] < self.forced_close_bb_length_thres_per
                        if data['fever_mode'] and candle_sl['high'] > candle_sl['bb_h']:  # fever mode
                            data['tp_price'] = data['tp_price_best'] = 0
                        elif forced_close_by_bb or now_clearing_price < candle_now['close'] or low_bb or data['tp_price'] != 0:
                            if forced_close_by_bb or low_bb:
                                data['tp_price'] = data['tp_price_best'] = 0
                            else:
                                pending_by_volume = data['tp_price'] == 0 and candle_now['volume'] >= candle_now['bb_vh']
                                if pending_by_volume:
                                    data['tp_price'] = now_clearing_price
                                    data['tp_price_best'] = candle_now['close']
                                    print('%s [%s] Long Close Pending - TP (%.4f USDT), TPB (%.4f USDT), Volume (%.4f), VolumeH (%.4f), VolumeM (%.4f)' % (candle_now['date'], data['symbol'], data['tp_price'], data['tp_price_best'], candle_now['volume'], candle_now['bb_vh'], candle_now['bb_vm']))
                                    self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 지연', '볼륨이 (%.4f) 이하로 떨어질 때 까지' % candle_now['bb_vm'], 'T/P 추가, Limit (%.4f)' % data['tp_price'])

                                update_tp_price = data['tp_price'] != 0 and data['tp_price_best'] < candle_now['close'] and candle_now['volume'] >= candle_now['bb_vh']
                                if update_tp_price:
                                    data['tp_price'] = data['tp_price_best']
                                    data['tp_price_best'] = candle_now['close']
                                    print('%s [%s] Long TP Update - TP (%.4f USDT), TPB (%.4f USDT), Volume (%.4f), VolumeH (%.4f), VolumeM (%.4f)' % (candle_now['date'], data['symbol'], data['tp_price'], data['tp_price_best'], candle_now['volume'], candle_now['bb_vh'], candle_now['bb_vm']))
                                    self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 지연', '볼륨이 (%.4f) 이하로 떨어질 때 까지' % candle_now['bb_vm'], 'T/P 업데이트, Limit (%.4f)' % data['tp_price'])

                            close_by_volume = data['tp_price'] != 0 and candle_now['volume'] <= candle_now['bb_vm']

                            if data['tp_price'] == 0 or close_by_volume:
                                reason = ''
                                if forced_close_by_bb:
                                    reason = '(BB 폭이 좁아져 강제 종료)'
                                elif low_bb:
                                    reason = '(이전 %s 캔들이 BB 하단 돌파)' % data['sl_interval']
                                elif close_by_volume:
                                    reason = '(볼륨 하락으로 인해 종료)'

                                used_usdt = data['amount'] * data['entry'] / self.info.leverage
                                gain_usdt = data['amount'] * price / self.info.leverage
                                pnl = self.sellOrder(data, data['amount'], price)

                                print('%s [%s] Long Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], used_usdt, gain_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (used_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
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
                                    if chasing_amount * candle_now['close'] > self.balance['total'] * self.chasing_maximum_total_per * data['input'] * self.info.leverage:
                                        chasing_amount = self.balance['total'] * self.chasing_maximum_total_per * data['input'] / candle_now['close']
                                        # print('    Chasing amount modified %.4f' % chasing_amount)
                                        data['chasing_amount'] = chasing_amount if chasing_amount > 0 else 0
                                        data['chasing_remain'] = 3 if chasing_amount > 0 else 0

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per * data['input']:
                                gain_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                pnl = self.sellOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Long S/L - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], gain_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 손절', 'Size (%.4f USDT)' % gain_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    else:
                        price = candle_now['close'] - data['amount_min']
                        if self.is_simulate:
                            data['pnl'] = (data['entry'] - price) * data['amount']

                        # 종료 체크
                        high_bb = candle_sl['high'] > candle_sl['bb_h']
                        now_clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        forced_close_by_bb = data['position_length'] >= self.forced_close_min_length and (candle_now['bb_h'] - candle_now['bb_l']) / candle_now['bb_m'] < self.forced_close_bb_length_thres_per
                        if data['fever_mode'] and candle_sl['low'] < candle_sl['bb_l']:  # fever mode
                            data['tp_price'] = data['tp_price_best'] = 0
                        elif forced_close_by_bb or now_clearing_price > candle_now['close'] or high_bb or data['tp_price'] != 0:
                            if forced_close_by_bb or high_bb:
                                data['tp_price'] = data['tp_price_best'] = 0
                            else:
                                pending_by_volume = data['tp_price'] == 0 and candle_now['volume'] >= candle_now['bb_vh']
                                if pending_by_volume:
                                    data['tp_price'] = now_clearing_price
                                    data['tp_price_best'] = candle_now['close']
                                    print('%s [%s] Short Close Pending - TP (%.4f USDT), TPB (%.4f USDT), Volume (%.4f), VolumeH (%.4f), VolumeM (%.4f)' % (candle_now['date'], data['symbol'], data['tp_price'], data['tp_price_best'], candle_now['volume'], candle_now['bb_vh'], candle_now['bb_vm']))
                                    self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 지연', '볼륨이 (%.4f) 이하로 떨어질 때 까지' % candle_now['bb_vm'], 'T/P 추가, Limit (%.4f)' % data['tp_price'])

                                update_tp_price = data['tp_price'] != 0 and data['tp_price_best'] > candle_now['close'] and candle_now['volume'] >= candle_now['bb_vh']
                                if update_tp_price:
                                    data['tp_price'] = data['tp_price_best']
                                    data['tp_price_best'] = candle_now['close']
                                    print('%s [%s] Short TP Update - TP (%.4f USDT), TPB (%.4f USDT), Volume (%.4f), VolumeH (%.4f), VolumeM (%.4f)' % (candle_now['date'], data['symbol'], data['tp_price'], data['tp_price_best'], candle_now['volume'], candle_now['bb_vh'], candle_now['bb_vm']))
                                    self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 지연', '볼륨이 (%.4f) 이하로 떨어질 때 까지' % candle_now['bb_vm'], 'T/P 업데이트, Limit (%.4f)' % data['tp_price'])

                            close_by_volume = data['tp_price'] != 0 and candle_now['volume'] <= candle_now['bb_vm']

                            if data['tp_price'] == 0 or close_by_volume:
                                reason = ''
                                if forced_close_by_bb:
                                    reason = '(BB 폭이 좁아져 강제 종료)'
                                elif high_bb:
                                    reason = '(이전 %s 캔들이 BB 상단 돌파)' % data['sl_interval']
                                elif close_by_volume:
                                    reason = '(볼륨 하락으로 인해 종료)'

                                gained_usdt = data['amount'] * data['entry'] / self.info.leverage
                                using_usdt = data['amount'] * price / self.info.leverage
                                pnl = self.buyOrder(data, data['amount'], price)

                                print('%s [%s] Short Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], gained_usdt, using_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (gained_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
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
                                clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                                if clearing_price > data['entry']:
                                    # (평단가 * 현재 개수 + 지금 가격 * x개) * 99% = 정리 가격 * (현재 개수 + x개)
                                    chasing_amount = (clearing_price - data['entry'] * (1 - self.chasing_target_profit)) * data['amount'] / (candle_now['close'] * (1 - self.chasing_target_profit) - clearing_price)
                                    # print('    Chasing Entry %.4f Amount %.4f Now %.4f Clear %.4f Chasing amount %.4f' % (data['entry'], data['amount'], candle_now['close'], clearing_price, chasing_amount))
                                    if chasing_amount * candle_now['close'] > self.balance['total'] * self.chasing_maximum_total_per * data['input'] * self.info.leverage:
                                        chasing_amount = self.balance['total'] * self.chasing_maximum_total_per * data['input'] / candle_now['close']
                                        # print('    Chasing amount modified %.4f' % chasing_amount)
                                        data['chasing_amount'] = chasing_amount if chasing_amount > 0 else 0
                                        data['chasing_remain'] = 3 if chasing_amount > 0 else 0

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per * data['input']:
                                using_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                pnl = self.buyOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Short S/L - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 손절', 'Size (%.4f USDT)' % using_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

                self.cancelAllOpenOrder(data['symbol'])

                # 진입 체크
                if data['position'] is None and data['enabled']:
                    using_usdt = self.balance['total'] * self.entry_amount_per * data['input']

                    fever_long = data['fever_mode'] and candle_sl['high'] > candle_sl['bb_h']
                    fever_short = data['fever_mode'] and candle_sl['low'] < candle_sl['bb_l']
                    enter_long = candle_now['close'] < candle_now['bb_l'] and not fever_short and candle_sl['low'] >= candle_sl['bb_l']
                    enter_short = candle_now['close'] > candle_now['bb_h'] and not fever_long and candle_sl['high'] <= candle_sl['bb_h']
                    if fever_long or enter_long:
                        reason = '(Fever)' if fever_long else ''
                        price = candle_now['close'] + data['amount_min']
                        amount = using_usdt * self.info.leverage / price
                        self.buyOrder(data, amount, price)

                        print('%s [%s] Long Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))
                    elif fever_short or enter_short:
                        reason = '(Fever)' if fever_short else ''
                        price = candle_now['close'] - data['amount_min']
                        amount = using_usdt * self.info.leverage / price
                        self.sellOrder(data, amount, price)

                        print('%s [%s] Short Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                # TAKE_PROFIT_MARKET 오더 오픈
                if data['tp_price'] != 0:
                    if data['position'] == 'Long':
                        self.makeTPSellOrder(data)
                    elif data['position'] == 'Short':
                        self.makeTPBuyOrder(data)

                self.runChasing(data, data['chasing_amount'] / 3, candle_now['close'], candle_now['date'])

                if not self.is_simulate:
                    print('    data %s' % data)

            candle_count += 1

        if self.is_simulate:
            for data in self.positions_data:
                if not data['enabled']:
                    continue
                if False and data['position'] is not None:
                    print('[%s] unrealized pnl %.4f' % (data['symbol'], data['pnl']))
                    self.balance['total'] += data['pnl']

                total_tx = data['win'] + data['lose']
                print('[%s] Summery : Win rate (%d / %d, %.4f%%), Total profit (%.4f USDT), Avg profit (%.4f USDT), Total loss (%.4f USDT), Avg loss (%.4f USDT), Commission (%.4f USDT), Total PnL (%.4f USDT, %.4f%%)' % (data['symbol'], data['win'], total_tx, (data['win'] * 100) / total_tx, data['profit'], 0 if data['win'] == 0 else data['profit'] / data['win'], data['loss'], 0 if data['lose'] == 0 else data['loss'] / data['lose'], data['commission'], data['profit'] + data['loss'], (data['profit'] + data['loss']) * 100 / self.simulation_usdt))

                if not self.using_pnl_shortcut:
                    closing_rate_data = []
                    for i in range(24):
                        closing_rate_data.append({
                            'length': i * 4 + 4,
                            'value': 0,
                            'rate': 0.0,
                            'ac_rate': 0.0
                        })
                    total = 0
                    for item in sorted(data['closing_length'].items(), key=lambda it: it[0]):
                        idx = int(item[0] / 4)
                        if idx > 23:
                            idx = 23
                        closing_rate_data[idx]['value'] += item[1]
                        total += item[1]
                    for i in range(24):
                        closing_rate_data[i]['rate'] = closing_rate_data[i]['value'] / total
                        if i == 0:
                            closing_rate_data[i]['ac_rate'] = closing_rate_data[i]['rate']
                        else:
                            closing_rate_data[i]['ac_rate'] = closing_rate_data[i - 1]['ac_rate'] + closing_rate_data[i]['rate']

                    print('    Closing length : %s' % closing_rate_data)

            print('Total (%.4f USDT), Total PnL (%.4f%%)' % (self.balance['total'], (self.balance['total'] - self.simulation_usdt) * 100 / self.simulation_usdt))

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

Bot(config_file_name).start(96*7)


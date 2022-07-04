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
    balance = {
        'total': 0.0,
        'free': 0.0
    }
    positions_data = [
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
            'candle_offset': 7200000
        },
        '4h': {
            'sl_div': 8,
            'candle_offset': 14400000
        },
        '6h': {
            'sl_div': 12,
            'candle_offset': 21600000
        },
        '8h': {
            'sl_div': 16,
            'candle_offset': 28800000
        },
        '12h': {
            'sl_div': 24,
            'candle_offset': 43200000
        },
        '1d': {
            'sl_div': 48,
            'candle_offset': 54000000
        },
    }
    is_simulate = False

    def __init__(self, file_name):
        with open('tickers.json') as json_file:
            self.positions_data = json.load(json_file)

        self.info = myinfo.MyInfo(file_name, list(map(lambda d: d['symbol'], self.positions_data)))
        self.book = orderbook.OrderBook(self.info.exchange_str)
        self.telegram = telegram_module.Telegram(file_name)

        title = self.info.title

        data_length = 0
        for data in self.positions_data:
            data['enabled'] = data['symbol'] in self.info.using_symbol
            data_length += 1 if data['enabled'] else 0

        self.entry_amount_per = 0.1
        self.added_amount_per = 0.025
        self.stop_loss_threshold_total_per = 0.25
        self.stop_loss_amount_per = 0.5
        self.close_position_threshold_bb_height = 0.80

    def updateBalance(self):
        if self.is_simulate:
            if self.balance['total'] == 0:
                self.balance['total'] = self.balance['free'] = 1000.0
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
            data['position'] = None
            data['amount'] = 0
        data['using'] = float(record['positionInitialMargin'])
        data['entry'] = float(record['entryPrice'])
        data['pnl'] = float(record['unrealizedProfit'])

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
            pass
        else:
            self.info.cancelAllOpenOrder(symbol)

    def makeSellOrder(self, data, amount, price, candle_now, candle_prev):
        if self.is_simulate:
            if candle_now['high'] >= candle_prev['bb_h']:
                gain_usdt = data['amount'] * price / self.info.leverage
                pnl = self.sellOrder(data, amount, candle_prev['bb_h'])

                print('%s [%s] Long Close - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], gain_usdt))
                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
        else:
            self.info.sellOrder(data['symbol'], amount, price, False)

    def sellOrder(self, data, amount, price):
        if self.is_simulate:
            gain_usdt_leverage = price * amount
            my_usdt_leverage = data['entry'] * data['amount']
            commission = gain_usdt_leverage * 0.0004
            pnl = 0

            self.balance['total'] -= commission

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
                    data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

                    pnl = gain_usdt_leverage - my_usdt_leverage
                else:  # s/l
                    pre_pnl = (price - data['entry']) * data['amount']
                    data['using'] -= amount * data['entry'] / self.info.leverage
                    data['amount'] -= amount
                    post_pnl = (price - data['entry']) * data['amount']

                    pnl = pre_pnl - post_pnl
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

    def makeBuyOrder(self, data, amount, price, candle_now, candle_prev):
        if self.is_simulate:
            if candle_now['low'] <= candle_prev['bb_l']:
                using_usdt = data['amount'] * price / self.info.leverage
                pnl = self.buyOrder(data, amount, candle_prev['bb_l'])

                print('%s [%s] Short Close - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
        else:
            self.info.buyOrder(data['symbol'], amount, price, False)

    def buyOrder(self, data, amount, price):
        if self.is_simulate:
            using_usdt_leverage = price * amount
            my_usdt_leverage = data['entry'] * data['amount']
            commission = using_usdt_leverage * 0.0004
            pnl = 0

            self.balance['total'] += pnl
            self.balance['total'] -= commission

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
                    data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

                    pnl = my_usdt_leverage - using_usdt_leverage
                else:  # s/l
                    pre_pnl = (price - data['entry']) * data['amount']
                    data['using'] -= amount * data['entry'] / self.info.leverage
                    data['amount'] -= amount
                    post_pnl = (price - data['entry']) * data['amount']

                    pnl = pre_pnl - post_pnl
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

    def waitUntil15CandleMade(self):
        if self.is_simulate:
            return

        # 15분에 맞게 대기
        minute = datetime.datetime.now().minute
        second = datetime.datetime.now().second

        mod = minute % 15
        waiting_time_sec = (14 - mod) * 60 + (60 - second) + 1
        print('Wait %d sec' % waiting_time_sec)
        time.sleep(waiting_time_sec)

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
            'rsi': record['rsi']
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
            if self.is_simulate:
                data['position'] = None
                data['amount'] = 0
                data['using'] = 0
                data['entry'] = 0
                data['pnl'] = 0
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
                    candle_prev = self.createCandle(data['df_interval'].iloc[candle_idx - 1])
                    candle_now = self.createCandle(data['df_interval'].iloc[candle_idx])
                    candle_sl = self.createCandle(data['df_sl_interval'].loc[data['df_sl_interval']['datetime'] <= candle_now['datetime'] - self.simulate_const[data['sl_interval']]['candle_offset']].iloc[-1])
                else:
                    minute = datetime.datetime.now().minute
                    if data['interval'] == '30m' and minute % 30 != 0:
                        continue
                    elif data['interval'] == '1h' and minute != 0:
                        continue

                    df_interval = self.book.generate_chart_data(data['symbol'], data['interval'])
                    df_sl = self.book.generate_chart_data(data['symbol'], data['sl_interval'])

                    candle_prev = self.createCandle(df_interval.iloc[-2])
                    candle_now = self.createCandle(df_interval.iloc[-1])
                    candle_sl = self.createCandle(df_sl.iloc[-1])

                    print("- Candle data [%s]" % data['symbol'])
                    print(candle_now)

                if data['position'] is not None:
                    using_usdt = 0

                    if data['position'] == 'Long':
                        price = candle_now['close'] + data['amount_min']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        if now_clearing_price < candle_now['close'] or candle_sl['low'] < candle_sl['bb_l']:
                            using_usdt = data['amount'] * data['entry'] / self.info.leverage
                            gain_usdt = data['amount'] * price / self.info.leverage
                            pnl = self.sellOrder(data, data['amount'], price)

                            print('%s [%s] Long Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt, gain_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 - Size (%.4f USDT -> %.4f USDT)' % (using_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                        else:
                            reason = ''
                            # 물타기 체크
                            if candle_now['open'] < candle_now['bb_l'] < candle_now['close']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'B1'
                            elif candle_prev['open'] < candle_prev['close'] < candle_prev['bb_l'] and candle_now['bb_l'] < candle_now['open'] < candle_now['close']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'B2'
                            if candle_prev['rsi'] < 30 < candle_now['rsi']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'R'

                            if using_usdt > 0 and price < data['entry']:
                                # 물타기
                                self.buyOrder(data, using_usdt * self.info.leverage / price, price)

                                print('%s [%s] Long Chasing %s (%.4f USDT) - Size (%.4f USDT / %.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt, data['using'], self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 추매 - Size (%.4f USDT / %.4f USDT)' % (data['using'], self.balance['total']))

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                gain_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                pnl = self.sellOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Long S/L - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], gain_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 손절 - Size (%.4f USDT)' % gain_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    else:
                        price = candle_now['close'] - data['amount_min']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        if now_clearing_price > candle_now['close'] or candle_sl['high'] > candle_sl['bb_h']:
                            gain_usdt = data['amount'] * data['entry'] / self.info.leverage
                            using_usdt = data['amount'] * price / self.info.leverage
                            pnl = self.buyOrder(data, data['amount'], price)

                            print('%s [%s] Short Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], gain_usdt, using_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 - Size (%.4f USDT -> %.4f USDT)' % (gain_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                        else:
                            reason = ''
                            # 물타기 체크
                            if candle_now['open'] > candle_now['bb_h'] > candle_now['close']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'B1'
                            elif candle_prev['open'] > candle_prev['close'] > candle_prev['bb_h'] and candle_now['bb_h'] > candle_now['open'] > candle_now['close']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'B2'
                            if candle_prev['rsi'] > 70 > candle_now['rsi']:
                                using_usdt += self.balance['total'] * self.added_amount_per
                                reason += 'R'

                            if using_usdt > 0 and price > data['entry']:
                                # 물타기
                                self.sellOrder(data, using_usdt * self.info.leverage / price, price)

                                print('%s [%s] Short Chasing %s (%.4f USDT) - Size (%.4f USDT / %.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt, data['using'], self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 추매 - Size (%.4f USDT / %.4f USDT)' % (data['using'], self.balance['total']))

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                using_usdt = data['amount'] * price * self.stop_loss_amount_per / self.info.leverage
                                pnl = self.buyOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Short S/L - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 손절 - Size (%.4f USDT)' % using_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

                self.cancelAllOpenOrder(data['symbol'])

                # 진입 체크
                if data['position'] is None and data['enabled']:
                    using_usdt = self.balance['total'] * self.entry_amount_per

                    if candle_sl['low'] >= candle_sl['bb_l'] and candle_now['close'] < candle_now['bb_l']:
                        price = candle_now['close'] + data['amount_min']
                        self.buyOrder(data, using_usdt * self.info.leverage / price, price)

                        print('%s [%s] Long Entry - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 - Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                    elif candle_sl['high'] <= candle_sl['bb_h'] and candle_now['close'] > candle_now['bb_h']:
                        price = candle_now['close'] - data['amount_min']
                        self.sellOrder(data, using_usdt * self.info.leverage / price, price)

                        print('%s [%s] Short Entry - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 - Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                # 오더 오픈
                if data['position'] == 'Long':
                    self.makeSellOrder(data, data['amount'], candle_now['bb_h'], candle_now, candle_prev)
                elif data['position'] == 'Short':
                    self.makeBuyOrder(data, data['amount'], candle_now['bb_l'], candle_now, candle_prev)

            candle_count += 1

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

Bot(config_file_name).start()


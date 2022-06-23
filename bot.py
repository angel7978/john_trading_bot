# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook
import time
import datetime
import pandas as pd

from abc import *


class Bot(metaclass=ABCMeta):
    title = 'BB봇'
    balance = {
        'total': 0.0,
        'free': 0.0
    }
    positions_data = [
        {
            'symbol': 'BTCUSDT',
            'quote': 0.1,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        },
        {
            'symbol': 'ETHUSDT',
            'quote': 0.01,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        }
    ]
    '''
        {
            'symbol': 'BTCUSDT',
            'quote': 0.1,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        },
        {
            'symbol': 'ETHUSDT',
            'quote': 0.01,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        }'''
    leverage = 5

    def __init__(self, config_file_name):
        self.info = myinfo.MyInfo(config_file_name, list(map(lambda data: data['symbol'], self.positions_data)),
                                  self.leverage)
        self.book = orderbook.OrderBook()
        self.telegram = telegram_module.Telegram(config_file_name)

        self.entry_amount_per = 0.2 / len(self.positions_data)
        self.added_amount_per = 0.05 / len(self.positions_data)
        self.stop_loss_threshold_total_per = 0.5 / len(self.positions_data)
        self.stop_loss_amount_per = 0.5
        self.close_position_threshold_bb_height = 0.8

    def updateBalance(self):
        balance = self.info.getBalance('USDT')
        self.balance['free'] = balance[0]
        self.balance['total'] = balance[1]

    def updatePositions(self, data):
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

    def waitUntilOrderDone(self, order_id, symbol):
        ret = self.info.getOrder(order_id, symbol)

        for i in range(10):
            if ret['status'] == 'closed':
                return

            time.sleep(1)
            ret = self.info.getOrder(order_id, symbol)

        print('Order closing timeout')
        self.telegram.sendTelegramPush(self.title, '거래 에러', '주문이 닫히지 않습니다. 확인 해 주세요.')

    def sellOrder(self, data, amount):
        ret = self.info.sellOrder(data['symbol'], self.floor(amount))

        self.waitUntilOrderDone(ret['id'], data['symbol'])

        self.updateBalance()
        self.updatePositions(data)

        return self.floor(float(ret['filled']) * float(ret['average']))

    def buyOrder(self, data, amount):
        ret = self.info.buyOrder(data['symbol'], self.floor(amount))

        self.waitUntilOrderDone(ret['id'], data['symbol'])

        self.updateBalance()
        self.updatePositions(data)

        return self.floor(float(ret['filled']) * float(ret['average']))

    def start(self):
        self.updateBalance()

        print('Bot start!, Current USDT (free : %.4f, total : %.4f)' % (self.balance['free'], self.balance['total']))
        self.telegram.sendTelegramPush(self.title, '봇 시작!', '현재 보유 USDT (free : %.4f, total : %.4f)' % (self.balance['free'], self.balance['total']))

        for data in self.positions_data:
            self.updatePositions(data)
            print('    [%s] Position : %s, size : (%.4f USDT)' % (data['symbol'], data['position'], data['using'] * self.leverage))

        while True:
            # 30분에 맞게 대기
            minute = datetime.datetime.now().minute
            second = datetime.datetime.now().second
            if minute >= 30:
                waiting_time_sec = (60 - minute) * 60 - second + 1
            else:
                waiting_time_sec = (30 - minute) * 60 - second + 1
            print('Wait %d sec' % waiting_time_sec)
            time.sleep(waiting_time_sec)

            for data in self.positions_data:
                df = self.book.generate_chart_data(data['symbol'])

                prev_record = df.iloc[-2]
                now_record = df.iloc[-1]

                candle = {
                    'date': now_record['datetime'],
                    'open': now_record['open'],
                    'close': now_record['close'],
                    'prev_close': prev_record['close'],
                    'bb_h': now_record['bb_bbh'],
                    'bb_l': now_record['bb_bbl'],
                    'prev_bb_h': prev_record['bb_bbh'],
                    'prev_bb_l': prev_record['bb_bbl'],
                    'rsi': now_record['rsi'],
                    'prev_rsi': prev_record['rsi']
                }

                print("- Candle data [%s]" % data['symbol'])
                print(candle)

                if data['position'] is not None:
                    using_usdt = 0

                    if data['position'] == 'Long':
                        # 물타기 체크
                        if candle['open'] < candle['bb_l'] < candle['close']:
                            using_usdt += self.balance['total'] * self.added_amount_per
                        if candle['prev_rsi'] < 30 < candle['rsi']:
                            using_usdt += self.balance['total'] * self.added_amount_per

                        if using_usdt > 0:
                            # 손절각일 경우 손절 후 물타기
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_threshold_total_per:
                                using_usdt_leverage = data['using'] * self.leverage
                                gain_usdt_leverage = self.sellOrder(data, data['amount'] * self.stop_loss_amount_per / self.info.leverage)

                                print('%s [%s] Long S/L - size : (%.4f USDT / %.4f USDT)' % (candle['date'], data['symbol'], gain_usdt_leverage, data['amount'] * data['entry']))
                                print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                                self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Long 손절 - size : (%.4f USDT / %.4f USDT)' % (gain_usdt_leverage, data['amount'] * data['entry']), '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                            else:
                                price = candle['close'] + data['quote']
                                ret = self.buyOrder(data['symbol'], using_usdt / price)

                                print('%s [%s] Long Chasing - size : (%.4f USDT / %.4f USDT)' % (candle['date'], data['symbol'], using_usdt * self.leverage, data['using'] * self.leverage))
                                self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Long 추매 - size : (%.4f USDT / %.4f USDT)' % (using_usdt * self.leverage, data['using'] * self.leverage))

                        # 종료 체크
                        prev_clearing_price = candle['prev_bb_l'] + (candle['prev_bb_h'] - candle['prev_bb_l']) * self.close_position_threshold_bb_height
                        now_clearing_price = candle['bb_l'] + (candle['bb_h'] - candle['bb_l']) * self.close_position_threshold_bb_height
                        if prev_clearing_price < candle['prev_close'] and now_clearing_price > candle['close']:
                            using_usdt_leverage = data['using'] * self.leverage
                            gain_usdt_leverage = self.sellOrder(data['symbol'], data['amount'] / self.info.leverage)

                            print('%s [%s] Long Close - size : (%.4f USDT)' % (candle['date'], data['symbol'], gain_usdt_leverage))
                            print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                            self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Long 종료 - size : (%.4f USDT)' % gain_usdt_leverage, '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                    else:
                        # 물타기 체크
                        if candle['open'] > candle['bb_h'] > candle['close']:
                            using_usdt += self.balance['total'] * self.added_amount_per
                        if candle['prev_rsi'] > 70 > candle['rsi']:
                            using_usdt += self.balance['total'] * self.added_amount_per

                        if using_usdt > 0:
                            # 손절각일 경우 손절 후 물타기
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_threshold_total_per:
                                gain_usdt_leverage = data['using'] * self.leverage
                                using_usdt_leverage = self.buyOrder(data['symbol'], data['amount'] * self.stop_loss_amount_per / self.info.leverage)

                                print('%s [%s] Short S/L - size : (%.4f USDT / %.4f USDT)' % (candle['date'], data['symbol'], using_usdt_leverage, data['amount'] * data['entry']))
                                print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                                self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Short 손절 - size : (%.4f USDT / %.4f USDT)' % (gain_usdt_leverage, data['amount'] * data['entry']), '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                            else:
                                price = candle['close'] - data['quote']
                                ret = self.sellOrder(data['symbol'], using_usdt / price)

                                print('%s [%s] Short Chasing - size : (%.4f USDT / %.4f USDT)' % (candle['date'], data['symbol'], using_usdt * self.leverage, data['using'] * self.leverage))
                                self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Short 추매 - size : (%.4f USDT / %.4f USDT)' % (using_usdt * self.leverage, data['using'] * self.leverage))

                        # 종료 체크
                        prev_clearing_price = candle['prev_bb_h'] - (candle['prev_bb_h'] - candle['prev_bb_l']) * self.close_position_threshold_bb_height
                        now_clearing_price = candle['bb_h'] - (candle['bb_h'] - candle['bb_l']) * self.close_position_threshold_bb_height
                        if prev_clearing_price > candle['prev_close'] and now_clearing_price < candle['close']:
                            gain_usdt_leverage = data['using'] * self.leverage
                            using_usdt_leverage = self.buyOrder(data['symbol'], data['amount'] / self.info.leverage)

                            print('%s [%s] Short Close - size : (%.4f USDT)' % (candle['date'], data['symbol'], using_usdt_leverage))
                            print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))
                            self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Short 종료 - size : (%.4f USDT)' % using_usdt_leverage, '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (gain_usdt_leverage - using_usdt_leverage, self.balance['total']))

                if data['position'] is None:
                    # 진입 체크
                    using_usdt = self.balance['total'] * self.entry_amount_per

                    if False and candle['close'] < candle['bb_l']:
                        price = candle['close'] + data['quote']
                        ret = self.buyOrder(data['symbol'], using_usdt / price)

                        print('%s [%s] Long Entry - size : (%.4f USDT)' % (candle['date'], data['symbol'], using_usdt * self.leverage))
                        self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Long 진입 - size : (%.4f USDT)' % (using_usdt * self.leverage))

                    elif candle['close'] > candle['bb_h']:
                        price = candle['close'] - data['quote']
                        ret = self.buyOrder(data['symbol'], using_usdt / price)

                        print('%s [%s] Short Entry - size : (%.4f USDT)' % (candle['date'], data['symbol'], using_usdt * self.leverage))
                        self.telegram.sendTelegramPush(self.title, '%s [%s]' % (candle['date'], data['symbol']), 'Short 진입 - size : (%.4f USDT)' % (using_usdt * self.leverage))

    def simulate(self, candle_count):  # 48 ea == 1 day
        self.balance['total'] = self.balance['free'] = 1000.0

        for data in self.positions_data:
            data['last_df'] = self.book.generate_chart_data(data['symbol'], candle_count + 20)

        for delta in range(candle_count):
            for data in self.positions_data:

                prev_record = data['last_df'].iloc[-candle_count + delta - 1]
                record = data['last_df'].iloc[-candle_count + delta]
                candle = {
                    'date': record['datetime'],
                    'open': record['open'],
                    'close': record['close'],
                    'prev_close': prev_record['close'],
                    'bb_h': record['bb_bbh'],
                    'bb_l': record['bb_bbl'],
                    'prev_bb_h': prev_record['bb_bbh'],
                    'prev_bb_l': prev_record['bb_bbl'],
                    'rsi': record['rsi'],
                    'prev_rsi': prev_record['rsi']
                }

                if data['position'] is not None:
                    using_usdt = 0

                    if data['position'] == 'Long':
                        # 물타기 체크
                        if candle['open'] < candle['bb_l'] < candle['close']:
                            using_usdt += self.balance['total'] * self.added_amount_per
                        if candle['prev_rsi'] < 30 < candle['rsi']:
                            using_usdt += self.balance['total'] * self.added_amount_per

                        if using_usdt > 0:
                            # 손절각일 경우 손절 후 물타기
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_threshold_total_per:
                                price = candle['close'] - data['quote']
                                amount = data['amount'] * 0.5
                                gain_usdt_leverage = price * amount
                                using_usdt_leverage = data['entry'] * amount
                                commission = gain_usdt_leverage * self.info.commission
                                profits = gain_usdt_leverage - using_usdt_leverage

                                self.balance['total'] += profits
                                self.balance['total'] -= commission

                                print('%s [%s] Long 손절 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                    candle['date'], data['symbol'], gain_usdt_leverage, data['amount'] * data['entry'],
                                    price))
                                print('    순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (profits, self.balance['total']))

                                data['using'] *= 0.5
                                data['amount'] *= 0.5
                                data['commission'] += commission
                            else:
                                price = candle['close'] + data['quote']
                                using_usdt_leverage = using_usdt * self.leverage
                                amount = self.floor(using_usdt_leverage / price)
                                total_using = using_usdt_leverage + data['amount'] * data['entry']
                                total_amount = amount + data['amount']
                                commission = using_usdt_leverage * self.info.commission

                                print('%s [%s] Long 추매 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                    candle['date'], data['symbol'], using_usdt_leverage, total_using, price))

                                data['using'] += using_usdt
                                data['amount'] = total_amount
                                data['entry'] = self.floor(total_using / total_amount)
                                data['commission'] += commission

                        # 종료 체크
                        prev_clearing_price = candle['prev_bb_l'] + (candle['prev_bb_h'] - candle['prev_bb_l']) * 0.8
                        clearing_price = candle['bb_l'] + (candle['bb_h'] - candle['bb_l']) * 0.8
                        if prev_clearing_price < candle['prev_close'] and clearing_price > candle['close']:
                            # if clearing_price < candle['close']:
                            price = candle['close'] - data['quote']
                            gain_usdt = data['amount'] * price
                            entry_usdt = data['amount'] * data['entry']
                            commission = data['commission'] + gain_usdt * self.info.commission
                            profits = gain_usdt - entry_usdt - commission

                            self.balance['total'] += profits

                            print('%s [%s] Long 종료 - size : (%.4f USDT), price : (%.4f USDT)' % (
                                candle['date'], data['symbol'], gain_usdt, price))
                            print('    순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (profits, self.balance['total']))

                            data['position'] = None
                            data['amount'] = data['using'] = data['entry'] = data['commission'] = 0
                    else:
                        # 물타기 체크
                        if candle['open'] > candle['bb_h'] > candle['close']:
                            using_usdt += self.balance['total'] * self.added_amount_per
                        if candle['prev_rsi'] > 70 > candle['rsi']:
                            using_usdt += self.balance['total'] * self.added_amount_per

                        if using_usdt > 0:
                            # 손절각일 경우 손절 후 물타기
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_threshold_total_per:
                                price = candle['close'] + data['quote']
                                amount = data['amount'] * 0.5
                                gain_usdt_leverage = price * amount
                                using_usdt_leverage = data['entry'] * amount
                                commission = gain_usdt_leverage * self.info.commission
                                profits = using_usdt_leverage - gain_usdt_leverage

                                self.balance['total'] += profits
                                self.balance['total'] -= commission

                                print('%s [%s] Short 손절 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                    candle['date'], data['symbol'], gain_usdt_leverage, data['amount'] * data['entry'],
                                    price))
                                print('    순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (profits, self.balance['total']))

                                data['using'] *= 0.5
                                data['amount'] *= 0.5
                                data['commission'] += commission
                            else:
                                price = candle['close'] - data['quote']
                                using_usdt_leverage = using_usdt * self.leverage
                                amount = self.floor(using_usdt_leverage / price)
                                total_using = using_usdt_leverage + data['amount'] * data['entry']
                                total_amount = amount + data['amount']
                                commission = using_usdt_leverage * self.info.commission

                                print('%s [%s] Short 추매 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                    candle['date'], data['symbol'], using_usdt_leverage, total_using, price))

                                data['using'] += using_usdt
                                data['amount'] = total_amount
                                data['entry'] = self.floor(total_using / total_amount)
                                data['commission'] += commission

                        # 종료 체크
                        prev_clearing_price = candle['prev_bb_h'] - (candle['prev_bb_h'] - candle['prev_bb_l']) * 0.8
                        clearing_price = candle['bb_h'] - (candle['bb_h'] - candle['bb_l']) * 0.8
                        if prev_clearing_price > candle['prev_close'] and clearing_price < candle['close']:
                            # if clearing_price > candle['close']:
                            price = candle['close'] + data['quote']
                            gain_usdt = data['amount'] * price
                            entry_usdt = data['amount'] * data['entry']
                            commission = data['commission'] + gain_usdt * self.info.commission
                            profits = entry_usdt - gain_usdt - commission

                            self.balance['total'] += profits

                            print('%s [%s] Short 종료 - size : (%.4f USDT), price : (%.4f USDT)' % (
                                candle['date'], data['symbol'], gain_usdt, price))
                            print('    순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (profits, self.balance['total']))

                            data['position'] = None
                            data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

                if data['position'] is None:
                    # 진입 체크
                    using_usdt = self.balance['total'] * self.entry_amount_per
                    using_usdt_leverage = using_usdt * self.leverage
                    commission = using_usdt_leverage * self.info.commission

                    if False and candle['close'] < candle['bb_l']:
                        data['position'] = 'Long'

                        price = candle['close'] + data['quote']
                        data['amount'] = self.floor(using_usdt_leverage / price)
                        data['entry'] = price
                        data['using'] = using_usdt
                        data['commission'] = commission

                        self.balance['total'] -= commission

                        print('%s [%s] Long 진입 - size : (%.4f USDT), price : (%.4f USDT)' % (
                            candle['date'], data['symbol'], using_usdt_leverage, price))
                    elif candle['close'] > candle['bb_h']:
                        data['position'] = 'Short'

                        price = candle['close'] - data['quote']
                        data['amount'] = self.floor(using_usdt_leverage / price)
                        data['entry'] = price
                        data['using'] = using_usdt
                        data['commission'] = commission

                        self.balance['total'] -= commission

                        print('%s [%s] Short 진입 - size : (%.4f USDT), price : (%.4f USDT)' % (
                            candle['date'], data['symbol'], using_usdt_leverage, price))

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000

    #   self.telegram.sendTelegramPush(self.info.title, '체인 성공 %s' % symbol, '최종 이익 %.8f, 이익률 %.2f%%' % (current_amount - start_amount, profit_rate * 100))

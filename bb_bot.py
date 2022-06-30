# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook
import time
import datetime
import pandas as pd
import sys

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
            'entry': 0,
            'pnl': 0,
            'sl_interval': '12h'
        },
        {
            'symbol': 'ETHUSDT',
            'quote': 0.01,
            'position': None,
            'amount': 0,
            'using': 0,
            'entry': 0,
            'pnl': 0,
            'sl_interval': '6h'
        }
    ]
    '''
        {
            'symbol': 'BTCUSDT',
            'quote': 0.1,
            'position': None,
            'amount': 0,
            'using': 0,
            'entry': 0,
            'pnl': 0,
            'sl_interval': '12h'
        },
        {
            'symbol': 'ETHUSDT',
            'quote': 0.01,
            'position': None,
            'amount': 0,
            'using': 0,
            'entry': 0,
            'pnl': 0,
            'sl_interval': '6h'
        }'''
    leverage = 5
    is_simulate = False

    def __init__(self, file_name):
        self.info = myinfo.MyInfo(file_name, list(map(lambda data: data['symbol'], self.positions_data)), self.leverage)
        self.book = orderbook.OrderBook()
        self.telegram = telegram_module.Telegram(file_name)

        self.entry_amount_per = 0.2 / len(self.positions_data)
        self.added_amount_per = 0.05 / len(self.positions_data)
        self.stop_loss_threshold_total_per = 0.5 / len(self.positions_data)
        self.stop_loss_amount_per = 0.5
        self.close_position_threshold_bb_height = 0.8

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

        time.sleep(5)

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
                self.sellOrder(data, amount, candle_prev['bb_h'])
        else:
            self.info.sellOrder(data['symbol'], amount, price, False)

    def sellOrder(self, data, amount, price):
        if self.is_simulate:
            gain_usdt_leverage = price * amount
            my_usdt_leverage = data['entry'] * data['amount']
            commission = gain_usdt_leverage * self.info.commission
            pnl = 0

            self.balance['total'] -= commission

            if data['position'] is None:
                data['position'] = 'Short'

                data['amount'] = amount
                data['entry'] = price
                data['using'] = price * amount / self.leverage
            elif data['position'] == 'Short':  # chasing
                total_gain = gain_usdt_leverage + my_usdt_leverage
                total_amount = amount + data['amount']

                data['using'] = total_gain / self.leverage
                data['amount'] = total_amount
                data['entry'] = self.floor(total_gain / total_amount)
            else:
                if data['amount'] == amount:  # close
                    data['position'] = None
                    data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

                    pnl = gain_usdt_leverage - my_usdt_leverage
                else:  # s/l
                    pre_pnl = (price - data['entry']) * data['amount']
                    data['using'] -= amount * data['entry'] / self.leverage
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
                self.sellOrder(data, amount, candle_prev['bb_l'])
        else:
            self.info.buyOrder(data['symbol'], amount, price, False)

    def buyOrder(self, data, amount, price):
        if self.is_simulate:
            using_usdt_leverage = price * amount
            my_usdt_leverage = data['entry'] * data['amount']
            commission = using_usdt_leverage * self.info.commission
            pnl = 0

            self.balance['total'] += pnl
            self.balance['total'] -= commission

            if data['position'] is None:
                data['position'] = 'Long'

                data['amount'] = amount
                data['entry'] = price
                data['using'] = price * amount / self.leverage
            elif data['position'] == 'Long':  # chasing
                total_using = using_usdt_leverage + my_usdt_leverage
                total_amount = amount + data['amount']

                data['using'] = total_using / self.leverage
                data['amount'] = total_amount
                data['entry'] = self.floor(total_using / total_amount)
            else:
                if data['amount'] == amount:  # close
                    data['position'] = None
                    data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

                    pnl = my_usdt_leverage - using_usdt_leverage
                else:  # s/l
                    pre_pnl = (price - data['entry']) * data['amount']
                    data['using'] -= amount * data['entry'] / self.leverage
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

    def waitUntil30CandleMade(self):
        if self.is_simulate:
            return

        # 30분에 맞게 대기
        minute = datetime.datetime.now().minute
        second = datetime.datetime.now().second
        if minute >= 30:
            waiting_time_sec = (60 - minute) * 60 - second + 1
        else:
            waiting_time_sec = (30 - minute) * 60 - second + 1
        print('Wait %d sec' % waiting_time_sec)
        time.sleep(waiting_time_sec)

    @staticmethod
    def createCandle(record):
        return {
            'date': record['datetime'],
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

        print('Bot start!, Current USDT (free : %.4f, total : %.4f)' % (self.balance['free'], self.balance['total']))
        self.sendTelegramPush(self.title, '봇 시작!', '현재 보유 USDT (free : %.4f, total : %.4f)' % (self.balance['free'], self.balance['total']))

        for data in self.positions_data:
            self.updatePositions(data)
            print('    [%s] Position : %s, size : (%.4f USDT)' % (data['symbol'], data['position'], data['using'] * self.leverage))

        if self.is_simulate:
            for data in self.positions_data:
                data['last_df_30m'] = self.book.generate_chart_data(data['symbol'], '30m', simulate + 100)
                if data['sl_interval'] == '2h':
                    data['last_df_2h'] = self.book.generate_chart_data(data['symbol'], '2h', int(simulate / 4) + 100)
                elif data['sl_interval'] == '4h':
                    data['last_df_4h'] = self.book.generate_chart_data(data['symbol'], '4h', int(simulate / 8) + 100)
                elif data['sl_interval'] == '6h':
                    data['last_df_6h'] = self.book.generate_chart_data(data['symbol'], '6h', int(simulate / 12) + 100)
                elif data['sl_interval'] == '8h':
                    data['last_df_8h'] = self.book.generate_chart_data(data['symbol'], '8h', int(simulate / 16) + 100)
                elif data['sl_interval'] == '12h':
                    data['last_df_12h'] = self.book.generate_chart_data(data['symbol'], '12h', int(simulate / 24) + 100)
                else:  # data['sl_interval'] == '1d':
                    data['last_df_1d'] = self.book.generate_chart_data(data['symbol'], '1d', int(simulate / 48) + 100)

        candle_count = 0
        while not self.is_simulate or candle_count < simulate:
            self.waitUntil30CandleMade()

            self.updateBalance()

            for data in self.positions_data:
                self.updatePositions(data)

                if self.is_simulate:
                    now = datetime.datetime.today()
                    diff_2h_by_30m = (now.hour * 2 + int(now.minute / 30) - 1) % 4 - 4
                    diff_4h_by_30m = (now.hour * 2 + int(now.minute / 30) - 1) % 8 - 8
                    diff_6h_by_30m = (now.hour * 2 + int(now.minute / 30) - 5) % 12 - 12
                    diff_8h_by_30m = (now.hour * 2 + int(now.minute / 30) - 1) % 16 - 16
                    diff_12h_by_30m = (now.hour * 2 + int(now.minute / 30) - 17) % 24 - 24
                    diff_1d_by_30m = now.hour * 2 + int(now.minute / 30) - 47

                    candle_prev = self.createCandle(data['last_df_30m'].iloc[-simulate + candle_count - 1])
                    candle_now = self.createCandle(data['last_df_30m'].iloc[-simulate + candle_count])
                    if data['sl_interval'] == '2h':
                        candle_sl = self.createCandle(data['last_df_2h'].iloc[int((-simulate + candle_count + diff_2h_by_30m) / 4) - 1])
                    elif data['sl_interval'] == '4h':
                        candle_sl = self.createCandle(data['last_df_4h'].iloc[int((-simulate + candle_count + diff_4h_by_30m) / 8) - 1])
                    elif data['sl_interval'] == '6h':
                        candle_sl = self.createCandle(data['last_df_6h'].iloc[int((-simulate + candle_count + diff_6h_by_30m) / 12) - 1])
                    elif data['sl_interval'] == '8h':
                        candle_sl = self.createCandle(data['last_df_8h'].iloc[int((-simulate + candle_count + diff_8h_by_30m) / 16) - 1])
                    elif data['sl_interval'] == '12h':
                        candle_sl = self.createCandle(data['last_df_12h'].iloc[int((-simulate + candle_count + diff_12h_by_30m) / 24) - 1])
                    else:  # data['sl_interval'] == '1d':
                        candle_sl = self.createCandle(data['last_df_1d'].iloc[int((-simulate + candle_count + diff_1d_by_30m) / 48) - 1])
                else:
                    df_30m = self.book.generate_chart_data(data['symbol'])
                    df_sl = self.book.generate_chart_data(data['symbol'], data['sl_interval'])

                    candle_prev = self.createCandle(df_30m.iloc[-2])
                    candle_now = self.createCandle(df_30m.iloc[-1])
                    candle_sl = self.createCandle(df_sl.iloc[-1])

                    print("- Candle data [%s]" % data['symbol'])
                    print(candle_now)

                if data['position'] is not None:
                    using_usdt = 0

                    if data['position'] == 'Long':
                        price = candle_now['close'] + data['quote']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        if now_clearing_price < candle_now['close'] or candle_sl['low'] < candle_sl['bb_l']:
                            gain_usdt_leverage = data['amount'] * price
                            pnl = self.sellOrder(data, data['amount'], price)

                            print('%s [%s] Long Close - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], gain_usdt_leverage))
                            print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 - size : (%.4f USDT)' % gain_usdt_leverage, '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (pnl, self.balance['total']))
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
                                self.buyOrder(data, using_usdt * self.leverage / price, price)

                                print('%s [%s] Long Chasing (%s) - size : (%.4f USDT / %.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt * self.leverage, data['using'] * self.leverage))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 추매 - size : (%.4f USDT / %.4f USDT)' % (using_usdt * self.leverage, data['using'] * self.leverage))

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                pnl = self.sellOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Long S/L - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], data['amount'] * data['entry']))
                                print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 손절 - size : (%.4f USDT)' % (data['amount'] * data['entry']), '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (pnl, self.balance['total']))
                    else:
                        price = candle_now['close'] - data['quote']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * self.close_position_threshold_bb_height
                        if now_clearing_price > candle_now['close'] or candle_sl['high'] > candle_sl['bb_h']:
                            using_usdt_leverage = data['amount'] * price
                            pnl = self.buyOrder(data, data['amount'], price)

                            print('%s [%s] Short Close - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt_leverage))
                            print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 - size : (%.4f USDT)' % using_usdt_leverage, '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (pnl, self.balance['total']))
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
                                self.sellOrder(data, using_usdt * self.leverage / price, price)

                                print('%s [%s] Short Chasing (%s) - size : (%.4f USDT / %.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt * self.leverage, data['using'] * self.leverage))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 추매 - size : (%.4f USDT / %.4f USDT)' % (using_usdt * self.leverage, data['using'] * self.leverage))

                            # 손절각일 경우 손절
                            if data['using'] > self.balance['total'] * self.stop_loss_threshold_total_per:
                                pnl = self.buyOrder(data, data['amount'] * self.stop_loss_amount_per, price)

                                print('%s [%s] Short S/L - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], data['amount'] * data['entry']))
                                print('    PnL : (%.4f USDT), Wallet (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 손절 - size : (%.4f USDT)' % (data['amount'] * data['entry']), '순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (pnl, self.balance['total']))

                self.cancelAllOpenOrder(data['symbol'])

                # 진입 체크
                if data['position'] is None:
                    using_usdt = self.balance['total'] * self.entry_amount_per

                    if candle_sl['low'] >= candle_sl['bb_l'] and candle_now['close'] < candle_now['bb_l']:
                        price = candle_now['close'] + data['quote']
                        self.buyOrder(data, using_usdt * self.leverage / price, price)

                        print('%s [%s] Long Entry - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt * self.leverage))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 - size : (%.4f USDT)' % (using_usdt * self.leverage))

                    elif candle_sl['high'] <= candle_sl['bb_h'] and candle_now['close'] > candle_now['bb_h']:
                        price = candle_now['close'] - data['quote']
                        self.sellOrder(data, using_usdt * self.leverage / price, price)

                        print('%s [%s] Short Entry - size : (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt * self.leverage))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 - size : (%.4f USDT)' % (using_usdt * self.leverage))

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

Bot(config_file_name).start(48*30)


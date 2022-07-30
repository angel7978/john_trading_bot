# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook_trend_bb
import time
import datetime
import pandas as pd
import json
import sys

from abc import *


class Bot(metaclass=ABCMeta):
    title = 'BB Bot (Trend)'
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
            "interval": "30m",
            "trend_interval": "1d"
        },
        {
            "symbol": "ETHUSDT",
            "amount_min": 0.01,
            "interval": "30m",
            "trend_interval": "1d"
        },
        {
            "symbol": "BCHUSDT",
            "amount_min": 0.01,
            "interval": "30m",
            "trend_interval": "1d"
        },
        {
            "symbol": "LTCUSDT",
            "amount_min": 0.01,
            "interval": "30m",
            "trend_interval": "1d"
        },
        {
            "symbol": "ETCUSDT",
            "amount_min": 0.001,
            "interval": "30m",
            "trend_interval": "1d"
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
        self.book = orderbook_trend_bb.OrderBook(self.info.exchange_str)
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
        self.bb_length_thres = 10

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
            return

        self.info.cancelAllOpenOrder(symbol)

    def makeSellOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.sellOrder(data['symbol'], amount, price, False)

    def makeTPSellOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], amount, price, True)

    @staticmethod
    def resetData(data):
        data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['stable'] = 0
        data['triggered'] = False

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
        else:
            pre_pnl = data['pnl']
            ret = self.info.sellOrder(data['symbol'], amount, price)

            self.waitUntilOrderDone(ret['id'], data['symbol'])

            self.updatePositions(data)
            self.updateBalance()

            post_pnl = data['pnl']

            return self.floor(pre_pnl - post_pnl)

    def makeBuyOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.buyOrder(data['symbol'], amount, price, False)

    def makeTPBuyOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], amount, price, False)

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
            'rsi': record['rsi'],
            'bb_h': record['bb_bbh'],
            'bb_m': record['bb_bbm'],
            'bb_l': record['bb_bbl'],
            'bb_lp': record['bb_bb_lp'],
            'bb_lp_h': record['bb_bbh_p'],
            'bb_lp_l': record['bb_bbm_p']
        }

    def sendTelegramPush(self, *msgs):
        if self.is_simulate:
            return

        self.telegram.sendTelegramPush(*msgs)

    def isUpTrend(self, candle_trend):
        return candle_trend['rsi'] > 55

    def isDownTrend(self, candle_trend):
        return candle_trend['rsi'] < 45

    def start(self, simulate=0):
        self.is_simulate = simulate != 0

        self.updateBalance()

        print('Bot start!, Free (%.4f USDT), Total (%.4f USDT)' % (self.balance['free'], self.balance['total']))
        self.sendTelegramPush(self.title, 'Bot start!', 'Free (%.4f USDT), Total (%.4f USDT)' % (self.balance['free'], self.balance['total']))

        for data in self.positions_data:
            data['position'] = None
            self.resetData(data)
            data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = 0
            data['input'] = 1 if data['symbol'] not in self.info.input else self.info.input[data['symbol']]
            self.updatePositions(data)

            # init stable setup
            df_interval = self.book.generate_chart_data(data['symbol'], data['interval'], 135)

            for i in range(self.bb_length_thres):
                bb_bb_lp = df_interval.iloc[-1 - i]['bb_bb_lp']
                bb_bbm_p = df_interval.iloc[-1 - i]['bb_bbm_p']
                if bb_bb_lp <= bb_bbm_p:
                    data['stable'] += 1
                else:
                    break

            if data['position'] is not None or data['enabled']:
                print('    [%s] Position (%s), Size (%.4f USDT), Stable Length (%d)' % (data['symbol'], data['position'], data['using'], data['stable']))

        if self.is_simulate:
            for data in self.positions_data:
                if not data['enabled']:
                    continue

                data['df_interval'] = self.book.generate_chart_data(data['symbol'], data['interval'], int(simulate / self.simulate_const[data['interval']]['simulate_candle_div']) + 125)
                data['df_trend_interval'] = self.book.generate_chart_data(data['symbol'], data['trend_interval'], int(simulate * self.simulate_const[data['interval']]['sl_mul'] / self.simulate_const[data['trend_interval']]['sl_div']) + 125)

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
                    candle_now = self.createCandle(data['df_interval'].iloc[candle_idx])
                    candle_trend = self.createCandle(data['df_trend_interval'].loc[data['df_trend_interval']['datetime'] <= candle_now['datetime'] - self.simulate_const[data['trend_interval']]['candle_offset']].iloc[-1])
                else:
                    minute = datetime.datetime.now().minute

                    if data['interval'] == '30m' and minute % 30 != 0:
                        continue
                    elif data['interval'] == '1h' and minute != 0:
                        continue

                    df_interval = self.book.generate_chart_data(data['symbol'], data['interval'])
                    df_trend = self.book.generate_chart_data(data['symbol'], data['trend_interval'], True)

                    candle_now = self.createCandle(df_interval.iloc[-1])
                    candle_trend = self.createCandle(df_trend.iloc[-1])

                    print("- Log [%s]" % data['symbol'])
                    print('    candle %s' % candle_now)
                    print('    candle trend rsi %.4f' % candle_trend['rsi'])

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

                            print('%s [%s] Long Close %s - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, gain_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 손절', 'Size (%.4f USDT)' % gain_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

                            data['stable'] = 0
                            data['triggered'] = False
                        elif data['stable'] >= self.bb_length_thres:
                            if self.isUpTrend(candle_trend):
                                data['triggered'] = False
                                data['stable'] = -999
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 지연 (상승장)')
                            else:
                                reason = ''
                                used_usdt = data['amount'] * data['entry'] / self.info.leverage
                                gain_usdt = data['amount'] * price / self.info.leverage
                                pnl = self.sellOrder(data, data['amount'], price)

                                print('%s [%s] Long Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], used_usdt, gain_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (used_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

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

                            print('%s [%s] Short Close %s - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 손절', 'Size (%.4f USDT)' % using_usdt, 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

                            data['stable'] = 0
                            data['triggered'] = False
                        elif data['stable'] >= self.bb_length_thres:
                            if self.isDownTrend(candle_trend):
                                data['triggered'] = False
                                data['stable'] = -999
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 지연 (하락장)')
                            else:
                                reason = ''
                                gained_usdt = data['amount'] * data['entry'] / self.info.leverage
                                using_usdt = data['amount'] * price / self.info.leverage
                                pnl = self.buyOrder(data, data['amount'], price)

                                print('%s [%s] Short Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], gained_usdt, using_usdt))
                                print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                                self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (gained_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))

                                data['stable'] = self.bb_length_thres
                                data['triggered'] = False

                self.cancelAllOpenOrder(data['symbol'])

                # 진입 체크
                if data['position'] is None and data['enabled']:
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

                        print('%s [%s] Long Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                        data['stable'] = 0
                    elif short_entry:
                        reason = ''
                        price = candle_now['close'] - data['amount_min']
                        amount = using_usdt * self.info.leverage / price
                        self.sellOrder(data, amount, price)

                        print('%s [%s] Short Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                        data['stable'] = 0

                if not self.is_simulate:
                    print('    data %s' % data)

            candle_count += 1

        if self.is_simulate:
            for data in self.positions_data:
                if not data['enabled']:
                    continue
                if data['position'] is not None:
                    print('[%s] unrealized pnl %.4f' % (data['symbol'], data['pnl']))
                    self.balance['total'] += data['pnl']

                total_tx = data['win'] + data['lose']
                print('[%s] Summery : Win rate (%d / %d, %.4f%%), Total profit (%.4f USDT), Avg profit (%.4f USDT), Total loss (%.4f USDT), Avg loss (%.4f USDT), Commission (%.4f USDT), Total PnL (%.4f USDT, %.4f%%)' % (data['symbol'], data['win'], total_tx, (data['win'] * 100) / total_tx, data['profit'], 0 if data['win'] == 0 else data['profit'] / data['win'], data['loss'], 0 if data['lose'] == 0 else data['loss'] / data['lose'], data['commission'], data['profit'] + data['loss'], (data['profit'] + data['loss']) * 100 / self.simulation_usdt))

            print('Total (%.4f USDT), Total PnL (%.4f%%)' % (self.balance['total'], (self.balance['total'] - self.simulation_usdt) * 100 / self.simulation_usdt))

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

Bot(config_file_name).start()


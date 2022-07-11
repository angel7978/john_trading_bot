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
    simulation_usdt = 5000
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
            "closing_rate": [{'length': 4, 'value': 44, 'rate': 0.08270676691729323, 'ac_rate': 0.08270676691729323}, {'length': 8, 'value': 62, 'rate': 0.11654135338345864, 'ac_rate': 0.19924812030075187}, {'length': 12, 'value': 72, 'rate': 0.13533834586466165, 'ac_rate': 0.33458646616541354}, {'length': 16, 'value': 57, 'rate': 0.10714285714285714, 'ac_rate': 0.4417293233082707}, {'length': 20, 'value': 77, 'rate': 0.14473684210526316, 'ac_rate': 0.5864661654135339}, {'length': 24, 'value': 47, 'rate': 0.08834586466165413, 'ac_rate': 0.6748120300751881}, {'length': 28, 'value': 42, 'rate': 0.07894736842105263, 'ac_rate': 0.7537593984962407}, {'length': 32, 'value': 38, 'rate': 0.07142857142857142, 'ac_rate': 0.8251879699248121}, {'length': 36, 'value': 25, 'rate': 0.046992481203007516, 'ac_rate': 0.8721804511278196}, {'length': 40, 'value': 19, 'rate': 0.03571428571428571, 'ac_rate': 0.9078947368421053}, {'length': 44, 'value': 17, 'rate': 0.03195488721804511, 'ac_rate': 0.9398496240601504}, {'length': 48, 'value': 11, 'rate': 0.020676691729323307, 'ac_rate': 0.9605263157894737}, {'length': 52, 'value': 6, 'rate': 0.011278195488721804, 'ac_rate': 0.9718045112781954}, {'length': 56, 'value': 4, 'rate': 0.007518796992481203, 'ac_rate': 0.9793233082706767}, {'length': 60, 'value': 2, 'rate': 0.0037593984962406013, 'ac_rate': 0.9830827067669173}, {'length': 64, 'value': 4, 'rate': 0.007518796992481203, 'ac_rate': 0.9906015037593985}, {'length': 68, 'value': 1, 'rate': 0.0018796992481203006, 'ac_rate': 0.9924812030075187}, {'length': 72, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9924812030075187}, {'length': 76, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9924812030075187}, {'length': 80, 'value': 1, 'rate': 0.0018796992481203006, 'ac_rate': 0.994360902255639}, {'length': 84, 'value': 2, 'rate': 0.0037593984962406013, 'ac_rate': 0.9981203007518796}, {'length': 88, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9981203007518796}, {'length': 92, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9981203007518796}, {'length': 96, 'value': 1, 'rate': 0.0018796992481203006, 'ac_rate': 0.9999999999999999}]

        },
        {
            "symbol": "ETHUSDT",
            "amount_min": 0.01,
            "sl_interval": "6h",
            "interval": "30m",
            "closing_rate": [{'length': 4, 'value': 27, 'rate': 0.04981549815498155, 'ac_rate': 0.04981549815498155}, {'length': 8, 'value': 74, 'rate': 0.13653136531365315, 'ac_rate': 0.1863468634686347}, {'length': 12, 'value': 80, 'rate': 0.14760147601476015, 'ac_rate': 0.33394833948339486}, {'length': 16, 'value': 72, 'rate': 0.13284132841328414, 'ac_rate': 0.466789667896679}, {'length': 20, 'value': 74, 'rate': 0.13653136531365315, 'ac_rate': 0.6033210332103321}, {'length': 24, 'value': 49, 'rate': 0.09040590405904059, 'ac_rate': 0.6937269372693727}, {'length': 28, 'value': 40, 'rate': 0.07380073800738007, 'ac_rate': 0.7675276752767528}, {'length': 32, 'value': 37, 'rate': 0.06826568265682657, 'ac_rate': 0.8357933579335793}, {'length': 36, 'value': 25, 'rate': 0.046125461254612546, 'ac_rate': 0.8819188191881919}, {'length': 40, 'value': 20, 'rate': 0.03690036900369004, 'ac_rate': 0.9188191881918819}, {'length': 44, 'value': 14, 'rate': 0.025830258302583026, 'ac_rate': 0.9446494464944649}, {'length': 48, 'value': 9, 'rate': 0.016605166051660517, 'ac_rate': 0.9612546125461254}, {'length': 52, 'value': 6, 'rate': 0.01107011070110701, 'ac_rate': 0.9723247232472324}, {'length': 56, 'value': 4, 'rate': 0.007380073800738007, 'ac_rate': 0.9797047970479704}, {'length': 60, 'value': 3, 'rate': 0.005535055350553505, 'ac_rate': 0.985239852398524}, {'length': 64, 'value': 1, 'rate': 0.0018450184501845018, 'ac_rate': 0.9870848708487084}, {'length': 68, 'value': 4, 'rate': 0.007380073800738007, 'ac_rate': 0.9944649446494465}, {'length': 72, 'value': 1, 'rate': 0.0018450184501845018, 'ac_rate': 0.9963099630996309}, {'length': 76, 'value': 1, 'rate': 0.0018450184501845018, 'ac_rate': 0.9981549815498154}, {'length': 80, 'value': 1, 'rate': 0.0018450184501845018, 'ac_rate': 0.9999999999999999}, {'length': 84, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9999999999999999}, {'length': 88, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9999999999999999}, {'length': 92, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9999999999999999}, {'length': 96, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9999999999999999}]
        },
        {
            "symbol": "BCHUSDT",
            "amount_min": 0.01,
            "sl_interval": "8h",
            "interval": "30m",
            "closing_rate": [{'length': 4, 'value': 27, 'rate': 0.0533596837944664, 'ac_rate': 0.0533596837944664}, {'length': 8, 'value': 58, 'rate': 0.11462450592885376, 'ac_rate': 0.16798418972332016}, {'length': 12, 'value': 72, 'rate': 0.1422924901185771, 'ac_rate': 0.3102766798418972}, {'length': 16, 'value': 70, 'rate': 0.1383399209486166, 'ac_rate': 0.4486166007905138}, {'length': 20, 'value': 79, 'rate': 0.15612648221343872, 'ac_rate': 0.6047430830039525}, {'length': 24, 'value': 54, 'rate': 0.1067193675889328, 'ac_rate': 0.7114624505928853}, {'length': 28, 'value': 50, 'rate': 0.09881422924901186, 'ac_rate': 0.8102766798418971}, {'length': 32, 'value': 15, 'rate': 0.029644268774703556, 'ac_rate': 0.8399209486166007}, {'length': 36, 'value': 24, 'rate': 0.04743083003952569, 'ac_rate': 0.8873517786561264}, {'length': 40, 'value': 17, 'rate': 0.03359683794466403, 'ac_rate': 0.9209486166007904}, {'length': 44, 'value': 9, 'rate': 0.017786561264822136, 'ac_rate': 0.9387351778656126}, {'length': 48, 'value': 8, 'rate': 0.015810276679841896, 'ac_rate': 0.9545454545454545}, {'length': 52, 'value': 6, 'rate': 0.011857707509881422, 'ac_rate': 0.9664031620553359}, {'length': 56, 'value': 6, 'rate': 0.011857707509881422, 'ac_rate': 0.9782608695652174}, {'length': 60, 'value': 1, 'rate': 0.001976284584980237, 'ac_rate': 0.9802371541501976}, {'length': 64, 'value': 3, 'rate': 0.005928853754940711, 'ac_rate': 0.9861660079051383}, {'length': 68, 'value': 5, 'rate': 0.009881422924901186, 'ac_rate': 0.9960474308300395}, {'length': 72, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9960474308300395}, {'length': 76, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9960474308300395}, {'length': 80, 'value': 1, 'rate': 0.001976284584980237, 'ac_rate': 0.9980237154150198}, {'length': 84, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9980237154150198}, {'length': 88, 'value': 0, 'rate': 0.0, 'ac_rate': 0.9980237154150198}, {'length': 92, 'value': 1, 'rate': 0.001976284584980237, 'ac_rate': 1.0}, {'length': 96, 'value': 0, 'rate': 0.0, 'ac_rate': 1.0}]
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
            data_length = 1
            self.sendTelegramPush(self.title, '체인이 선택되지 않았습니다!! config 파일을 확인 해 주세요. [%s]' % self.info.using_symbol)

        self.entry_amount_per = 0.1
        self.added_amount_per = 0.025
        self.stop_loss_threshold_total_per = 0.25
        self.stop_loss_amount_per = 0.5
        self.close_position_threshold_bb_height = 0.80

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
                    data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['position_length'] = data['up'] = data['down'] = 0

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
                    data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['position_length'] = data['up'] = data['down'] = 0

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
    def getExpectedPnL(data, price, amount, close_price, close_price_inc, is_long=True):
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
            'volume': record['volume']
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
                data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = data['position_length'] = data['up'] = data['down'] = 0
                data['closing_length'] = {}
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
                    data['position_length'] += 1
                    using_usdt = 0

                    if candle_now['open'] < candle_now['close']:
                        data['up'] += 1
                    else:
                        data['down'] += 1

                    if data['position'] == 'Long':
                        price = candle_now['close'] + data['amount_min']
                        if self.is_simulate:
                            data['pnl'] = (price - data['entry']) * data['amount']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_l'] + (candle_now['bb_h'] - candle_now['bb_l']) * (self.close_position_threshold_bb_height + 0.00 * (data['up'] - data['down']))
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
                        if self.is_simulate:
                            data['pnl'] = (data['entry'] - price) * data['amount']

                        # 종료 체크
                        now_clearing_price = candle_now['bb_h'] - (candle_now['bb_h'] - candle_now['bb_l']) * (self.close_position_threshold_bb_height + 0.00 * (data['up'] - data['down']))
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
                        amount = using_usdt * self.info.leverage / price
                        self.buyOrder(data, amount, price)

                        print('%s [%s] Long Entry - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 - Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                    elif candle_sl['high'] <= candle_sl['bb_h'] and candle_now['close'] > candle_now['bb_h']:
                        price = candle_now['close'] - data['amount_min']
                        amount = using_usdt * self.info.leverage / price
                        self.sellOrder(data, amount, price)

                        print('%s [%s] Short Entry - Size (%.4f USDT)' % (candle_now['date'], data['symbol'], using_usdt))
                        self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 - Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                # 오더 오픈
                if data['position'] == 'Long':
                    self.makeSellOrder(data, data['amount'], candle_now['bb_h'], candle_now, candle_prev)
                elif data['position'] == 'Short':
                    self.makeBuyOrder(data, data['amount'], candle_now['bb_l'], candle_now, candle_prev)

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


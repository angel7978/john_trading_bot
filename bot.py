# -*- coding: utf-8 -*-

import telegram_module
import math
import myinfo
import orderbook
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
            'chain': 'BTCUSDT',
            'quote': 0.1,
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
            'chain': 'BTCUSDT',
            'quote': 0.1,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        },
        {
            'chain': 'ETHUSDT',
            'quote': 0.01,
            'position': None,
            'amount': 0,
            'using': 0,
            'commission': 0,
            'entry': 0,
            'last_df': pd.DataFrame()
        }'''
    leverage = 4

    def __init__(self, config_file_name):
        self.info = myinfo.MyInfo(config_file_name, list(map(lambda data: data['chain'], self.positions_data)),
                                  self.leverage)
        self.book = orderbook.OrderBook()
        self.telegram = telegram_module.Telegram(config_file_name)

        self.entry_amount_per = 0.2 / len(self.positions_data)
        self.added_amount_per = 0.05 / len(self.positions_data)
        self.stop_loss_amount_per = 0.5 / len(self.positions_data)

    def start(self):
        usdt_amount = self.info.getBalance('USDT')

        self.telegram.sendTelegramPush(self.title, '봇 시작!',
                                       '현재 보유 USDT (free : %.4f, total : %.4f)' % (usdt_amount[0], usdt_amount[1]))
        # while True:
        # 30분에 맞게 딜레이

        # 현재 포지션 체크

        # 진입 중일 경우

        # 물타기 체크

        # 손절각일 경우 손절 후 물타기

        # 청산 체크

        # 진입 중이 아닐 경우

        # 진입 체크

    def simulate(self, candle_count):  # 48 ea == 1 day
        self.balance['total'] = self.balance['free'] = 1000.0

        for data in self.positions_data:
            data['last_df'] = self.book.generate_chart_data(data['chain'], candle_count + 20)

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

                if data['position'] is None:
                    # 진입 체크
                    using_usdt = self.balance['total'] * self.entry_amount_per
                    using_usdt_leverage = using_usdt * self.leverage
                    commission = using_usdt_leverage * self.info.commission

                    if candle['close'] < candle['bb_l']:
                        data['position'] = 'Long'

                        price = candle['close'] + data['quote']
                        data['amount'] = self.floor(using_usdt_leverage / price)
                        data['entry'] = price
                        data['using'] = using_usdt
                        data['commission'] = commission

                        self.balance['total'] -= commission

                        print('%s [%s] Long 진입 - size : (%.4f USDT), price : (%.4f USDT)' % (
                        candle['date'], data['chain'], using_usdt_leverage, price))
                    elif candle['close'] > candle['bb_h']:
                        data['position'] = 'Short'

                        price = candle['close'] - data['quote']
                        data['amount'] = self.floor(using_usdt_leverage / price)
                        data['entry'] = price
                        data['using'] = using_usdt
                        data['commission'] = commission

                        self.balance['total'] -= commission

                        print('%s [%s] Short 진입 - size : (%.4f USDT), price : (%.4f USDT)' % (
                        candle['date'], data['chain'], using_usdt_leverage, price))
                else:
                    using_usdt = 0

                    if data['position'] is 'Long':
                        # 물타기 체크
                        if candle['open'] < candle['bb_l'] < candle['close']:
                            using_usdt += self.balance['total'] * self.added_amount_per
                        if candle['prev_rsi'] < 30 < candle['rsi']:
                            using_usdt += self.balance['total'] * self.added_amount_per

                        if using_usdt > 0:
                            # 손절각일 경우 손절 후 물타기
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_amount_per:
                                price = candle['close'] - data['quote']
                                amount = data['amount'] * 0.5
                                gain_usdt_leverage = price * amount
                                using_usdt_leverage = data['entry'] * amount
                                commission = gain_usdt_leverage * self.info.commission
                                profits = gain_usdt_leverage - using_usdt_leverage

                                self.balance['total'] += profits
                                self.balance['total'] -= commission

                                print('%s [%s] Long 손절 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                candle['date'], data['chain'], gain_usdt_leverage, data['amount'] * data['entry'],
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
                                candle['date'], data['chain'], using_usdt_leverage, total_using, price))

                                data['using'] += using_usdt
                                data['amount'] = total_amount
                                data['entry'] = self.floor(total_using / total_amount)
                                data['commission'] += commission

                        # 청산 체크
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

                            print('%s [%s] Long 청산 - size : (%.4f USDT), price : (%.4f USDT)' % (
                            candle['date'], data['chain'], gain_usdt, price))
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
                            if data['using'] + using_usdt > self.balance['total'] * self.stop_loss_amount_per:
                                price = candle['close'] + data['quote']
                                amount = data['amount'] * 0.5
                                gain_usdt_leverage = price * amount
                                using_usdt_leverage = data['entry'] * amount
                                commission = gain_usdt_leverage * self.info.commission
                                profits = using_usdt_leverage - gain_usdt_leverage

                                self.balance['total'] += profits
                                self.balance['total'] -= commission

                                print('%s [%s] Short 손절 - size : (%.4f USDT/%.4f USDT), price : (%.4f USDT)' % (
                                candle['date'], data['chain'], gain_usdt_leverage, data['amount'] * data['entry'],
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
                                candle['date'], data['chain'], using_usdt_leverage, total_using, price))

                                data['using'] += using_usdt
                                data['amount'] = total_amount
                                data['entry'] = self.floor(total_using / total_amount)
                                data['commission'] += commission

                        # 청산 체크
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

                            print('%s [%s] Short 청산 - size : (%.4f USDT), price : (%.4f USDT)' % (
                            candle['date'], data['chain'], gain_usdt, price))
                            print('    순 이익 : (%.4f USDT), 현재 보유 (%.4f USDT)' % (profits, self.balance['total']))

                            data['position'] = None
                            data['amount'] = data['using'] = data['entry'] = data['commission'] = 0

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000

    #   self.telegram.sendTelegramPush(self.info.title, '체인 성공 %s' % chain, '최종 이익 %.8f, 이익률 %.2f%%' % (current_amount - start_amount, profit_rate * 100))

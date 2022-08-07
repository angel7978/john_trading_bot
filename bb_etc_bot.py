# -*- coding: utf-8 -*-
import os.path

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
    title = 'BB Bot (ETC)'
    folder_name = 'summary'
    log_file_name = 'bb_etc_bot.log'
    using_pnl_shortcut = True
    simulation_usdt = 1000
    balance = {
        'total': 0.0,
        'free': 0.0
    }
    positions_data = [
        {
            "symbol": "ETCUSDT",
            "amount_min": 0.001,
            "interval": '1m'
        }
    ]
    simulation_order = {
        "buy_order": [],
        "sell_order": []
    }
    is_simulate = False

    def __init__(self, file_name):
        # with open('tickers.json') as json_file:
        #     self.positions_data = json.load(json_file)

        self.info = myinfo.MyInfo(file_name, list(map(lambda d: d['symbol'], self.positions_data)))
        self.book = orderbook.OrderBook(self.info.exchange_str)
        self.telegram = telegram_module.Telegram(file_name)

        self.title = self.info.title

        self.taker_commission = 0.0004  # taker 수수료
        self.entry_amount_per = 0.1  # 진입시 사용되는 USDT

        self.log_file_name = file_name + '.' + self.log_file_name

    def writeLog(self, data, pnl):
        file_path = self.folder_name + '/' + self.log_file_name

        if not os.path.exists(self.folder_name):
            os.mkdir(self.folder_name)

        if not os.path.exists(file_path):
            with open(file_path, 'w') as outfile:
                json.dump({}, outfile)

        with open(file_path) as json_file:
            json_data = json.load(json_file)

            if data['symbol'] not in json_data:
                json_data[data['symbol']] = {
                    'win': 0,
                    'lose': 0,
                    'pnl': 0
                }

            record = json_data[data['symbol']]
            if pnl > 0:
                record['win'] += 1
            else:
                record['lose'] += 1
            record['pnl'] += pnl

        with open(file_path, 'w') as outfile:
            json.dump(json_data, outfile, indent=4)

        total_tx = json_data[data['symbol']]['win'] + json_data[data['symbol']]['lose']
        win_rate = 'Win rate (%d / %d, %.2f%%' % (json_data[data['symbol']]['win'], total_tx, 0 if total_tx == 0 else (json_data[data['symbol']]['win'] * 100 / total_tx))
        total_pnl = 'Total PnL (%.4f USDT)' % json_data[data['symbol']]['pnl']
        return win_rate, total_pnl

    def updateBalance(self):
        if self.is_simulate:
            if self.balance['total'] == 0:
                self.balance['total'] = self.balance['free'] = self.simulation_usdt
        else:
            balance = self.info.getBalance('USDT')
            self.balance['free'] = balance[0]
            self.balance['total'] = balance[1]

    def updatePositions(self, data, check_limit=False):
        if self.is_simulate:
            return

        record = self.info.getPosition(data['symbol'])
        amount = float(record['positionAmt'])

        pre_position = data['position']
        pre_amount = data['amount']
        pre_pnl = data['pnl']
        pre_using = data['using']

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

        if check_limit:
            now = datetime.datetime.now() - datetime.timedelta(minutes=1)
            date = now.strftime("%Y-%m-%d %H:%M:00")

            if pre_position == data['position'] == 'Long':
                if data['amount'] > pre_amount:
                    print('%s [%s] Long Chasing - Size (%.4f USDT -> %.4f USDT)' % (date, data['symbol'], pre_using, data['using']))
                    self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Long 추매', 'Size (%.4f USDT -> %.4f USDT)' % (pre_using, data['using']))
                else:
                    pnl = pre_pnl - data['pnl']
                    print('%s [%s] Long Some Close - Size (%.4f USDT -> %.4f USDT)' % (date, data['symbol'], pre_using, data['using']))
                    print('    Estimated PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    win_rate, total_pnl = self.writeLog(data, pnl)
                    self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Long 일부 종료', 'Size (%.4f USDT -> %.4f USDT)' % (pre_using, data['using']), '추정 PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)

            if pre_position == data['position'] == 'Short':
                if data['amount'] > pre_amount:
                    print('%s [%s] Short Chasing - Size (%.4f USDT -> %.4f USDT)' % (date, data['symbol'], pre_using, data['using']))
                    self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Short 추매', 'Size (%.4f USDT -> %.4f USDT)' % (pre_using, data['using']))
                else:
                    pnl = pre_pnl - data['pnl']
                    print('%s [%s] Short Some Close - Size (%.4f USDT -> %.4f USDT)' % (date, data['symbol'], pre_using, data['using']))
                    print('    Estimated PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    win_rate, total_pnl = self.writeLog(data, pnl)
                    self.sendTelegramPush(self.title, '%s [%s]' % (date, data['symbol']), 'Short 일부 종료', 'Size (%.4f USDT -> %.4f USDT)' % (pre_using, data['using']), '추정 PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)

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
            self.simulation_order["sell_order"].clear()
            self.simulation_order["buy_order"].clear()
        else:
            self.info.cancelAllOpenOrder(symbol)

    def makeSellOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.sellOrder(data['symbol'], amount, price, False)
        else:
            self.simulation_order["sell_order"].append({
                "amount": amount,
                "price": price
            })

    def makeTPSellOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], amount, price, True)

    @staticmethod
    def resetData(data):
        data['amount'] = data['using'] = data['entry'] = data['pnl'] = data['volume'] = data['datetime'] = data['corner_price'] = 0

    def sellOrder(self, data, amount, price):
        if self.is_simulate:
            gain_usdt_leverage = price * amount
            used_usdt_leverage = data['entry'] * data['amount']
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
                total_gain = gain_usdt_leverage + used_usdt_leverage
                total_amount = amount + data['amount']

                data['using'] = total_gain / self.info.leverage
                data['amount'] = total_amount
                data['entry'] = self.floor(total_gain / total_amount)
            else:
                if data['amount'] == amount:  # close
                    data['position'] = None
                    self.resetData(data)

                    pnl = gain_usdt_leverage - used_usdt_leverage

                    if pnl > 0:
                        data['win'] += 1
                        data['profit'] += pnl
                    else:
                        data['lose'] += 1
                        data['loss'] += pnl
                else:  # limit or s/l
                    gain_usdt_leverage = price * amount
                    used_usdt_leverage = data['entry'] * amount

                    data['using'] -= amount * data['entry'] / self.info.leverage
                    data['amount'] -= amount

                    pnl = gain_usdt_leverage - used_usdt_leverage
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
        else:
            self.simulation_order["buy_order"].append({
                "amount": amount,
                "price": price
            })

    def makeTPBuyOrder(self, data, amount, price):
        if not self.is_simulate:
            self.info.createTPMarketOrder(data['symbol'], amount, price, False)

    def buyOrder(self, data, amount, price):
        if self.is_simulate:
            using_usdt_leverage = price * amount
            gained_usdt_leverage = data['entry'] * data['amount']
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
                total_using = using_usdt_leverage + gained_usdt_leverage
                total_amount = amount + data['amount']

                data['using'] = total_using / self.info.leverage
                data['amount'] = total_amount
                data['entry'] = self.floor(total_using / total_amount)
            else:
                if data['amount'] == amount:  # close
                    data['position'] = None
                    self.resetData(data)

                    pnl = gained_usdt_leverage - using_usdt_leverage

                    if pnl > 0:
                        data['win'] += 1
                        data['profit'] += pnl
                    else:
                        data['lose'] += 1
                        data['loss'] += pnl
                else:  # limit or s/l
                    using_usdt_leverage = price * amount
                    gained_usdt_leverage = data['entry'] * amount

                    data['using'] -= amount * data['entry'] / self.info.leverage
                    data['amount'] -= amount

                    pnl = gained_usdt_leverage - using_usdt_leverage
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

    def waitUntilCandleMade(self):
        if self.is_simulate:
            return

        # 1분에 맞게 대기
        second = datetime.datetime.now().second

        waiting_time_sec = (60 - second) + 1
        print('Wait %d sec' % waiting_time_sec)
        time.sleep(waiting_time_sec)

    def checkSimulationOrder(self, data, candle_now):
        if not self.is_simulate:
            return

        remove_list = []
        for order in self.simulation_order['sell_order']:
            if order['price'] < candle_now['high']:
                pre_using = data['using']
                if data['position'] == 'Long':
                    pnl = self.sellOrder(data, order['amount'], order['price'])

                    print('%s [%s] Long Some Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], pre_using, data['using']))
                    print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    win_rate, total_pnl = self.writeLog(data, pnl)
                else:
                    self.sellOrder(data, order['amount'], order['price'])

                    print('%s [%s] Short Chasing - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], pre_using, data['using']))

                remove_list.append(order)

        for remove_order in remove_list:
            self.simulation_order['sell_order'].remove(remove_order)

        remove_list = []
        for order in self.simulation_order['buy_order']:
            if order['price'] > candle_now['low']:
                pre_using = data['using']
                if data['position'] == 'Short':
                    pnl = self.buyOrder(data, order['amount'], order['price'])

                    print('%s [%s] Short Some Close - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], pre_using, data['using']))
                    print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                    win_rate, total_pnl = self.writeLog(data, pnl)
                else:
                    self.buyOrder(data, order['amount'], order['price'])

                    print('%s [%s] Long Chasing - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], pre_using, data['using']))

                remove_list.append(order)

        for remove_order in remove_list:
            self.simulation_order['buy_order'].remove(remove_order)


    @staticmethod
    def createCandle(record):
        return {
            'datetime': record['datetime'],
            'date': record['date'],
            'open': record['open'],
            'close': record['close'],
            'volume': record['volume'],
            'low': record['low'],
            'high': record['high'],
            'rsi': record['rsi'],
            'bb_h': record['bb_bbh'],
            'bb_m': record['bb_bbm'],
            'bb_l': record['bb_bbl'],
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
            self.resetData(data)
            data['win'] = data['lose'] = data['profit'] = data['loss'] = data['commission'] = 0
            data['input'] = 1 if data['symbol'] not in self.info.input else self.info.input[data['symbol']]
            self.updatePositions(data)

            if data['position'] is not None:
                print('    [%s] Position (%s), Size (%.4f USDT)' % (data['symbol'], data['position'], data['using']))

        if self.is_simulate:
            for data in self.positions_data:
                data['df_interval'] = self.book.generate_chart_data(data['symbol'], data['interval'], simulate + 110)

        candle_count = 0
        while not self.is_simulate or candle_count < simulate:
            self.waitUntilCandleMade()

            self.updateBalance()

            for data in self.positions_data:
                self.updatePositions(data, True)

                if self.is_simulate:
                    candle_idx = -simulate + candle_count
                    if candle_idx >= 0:
                        continue
                    candle_now = self.createCandle(data['df_interval'].iloc[candle_idx])
                else:
                    df_interval = self.book.generate_chart_data(data['symbol'], data['interval'])

                    candle_now = self.createCandle(df_interval.iloc[-1])

                    print("- Log [%s]" % (data['symbol']))
                    print('    candle %s' % candle_now)

                self.checkSimulationOrder(data, candle_now)

                if data['position'] is not None:
                    if data['position'] == 'Long':
                        if data['corner_price'] < candle_now['high']:
                            data['corner_price'] = candle_now['high']

                        price = candle_now['close'] + data['amount_min']
                        min_amount = self.balance['total'] * self.entry_amount_per * data['input'] * self.info.leverage / price * 0.4
                        if self.is_simulate:
                            data['pnl'] = (price - data['entry']) * data['amount']

                        # 종료
                        high_price = candle_now['close'] >= candle_now['bb_h']
                        low_amount = data['amount'] < min_amount
                        if not low_amount and high_price and candle_now['close'] < data['entry']:
                            used_usdt = data['amount'] * 0.5 * data['entry'] / self.info.leverage
                            gain_usdt = data['amount'] * 0.5 * price / self.info.leverage
                            pnl = self.sellOrder(data, data['amount'] * 0.5, price)

                            print('%s [%s] Long S/L - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], used_usdt, gain_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            win_rate, total_pnl = self.writeLog(data, pnl)
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 일부 손절', 'Size (%.4f USDT -> %.4f USDT)' % (used_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)
                        elif high_price or low_amount:
                            reason = 'Low amount' if low_amount else 'BB'
                            used_usdt = data['amount'] * data['entry'] / self.info.leverage
                            gain_usdt = data['amount'] * price / self.info.leverage
                            pnl = self.sellOrder(data, data['amount'], price)

                            print('%s [%s] Long Close (%s) - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], reason, used_usdt, gain_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            win_rate, total_pnl = self.writeLog(data, pnl)
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (used_usdt, gain_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)
                    else:
                        if data['corner_price'] > candle_now['low']:
                            data['corner_price'] = candle_now['low']

                        price = candle_now['close'] - data['amount_min']
                        min_amount = self.balance['total'] * self.entry_amount_per * data['input'] * self.info.leverage / price * 0.4
                        if self.is_simulate:
                            data['pnl'] = (data['entry'] - price) * data['amount']

                        # 종료
                        low_price = candle_now['close'] <= candle_now['bb_l']
                        low_amount = data['amount'] < min_amount
                        if not low_amount and low_price and candle_now['close'] > data['entry']:
                            gained_usdt = data['amount'] * 0.5 * data['entry'] / self.info.leverage
                            using_usdt = data['amount'] * 0.5 * price / self.info.leverage
                            pnl = self.buyOrder(data, data['amount'] * 0.5, price)

                            print('%s [%s] Short S/L - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], gained_usdt, using_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            win_rate, total_pnl = self.writeLog(data, pnl)
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 일부 손절', 'Size (%.4f USDT -> %.4f USDT)' % (gained_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)
                        elif low_price or low_amount:
                            reason = 'Low amount' if low_amount else 'BB'
                            gained_usdt = data['amount'] * data['entry'] / self.info.leverage
                            using_usdt = data['amount'] * price / self.info.leverage
                            pnl = self.buyOrder(data, data['amount'], price)

                            print('%s [%s] Short Close (%s) - Size (%.4f USDT -> %.4f USDT)' % (candle_now['date'], data['symbol'], reason, gained_usdt, using_usdt))
                            print('    PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']))
                            win_rate, total_pnl = self.writeLog(data, pnl)
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 종료 %s' % reason, 'Size (%.4f USDT -> %.4f USDT)' % (gained_usdt, using_usdt), 'PnL (%.4f USDT), Total (%.4f USDT)' % (pnl, self.balance['total']), win_rate, total_pnl)

                self.cancelAllOpenOrder(data['symbol'])

                # 진입 체크
                if data['position'] is None:
                    using_usdt = self.balance['total'] * self.entry_amount_per * data['input']

                    long_entry = candle_now['open'] > candle_now['close'] and candle_now['bb_l'] > candle_now['close']
                    short_entry = candle_now['open'] < candle_now['close'] and candle_now['bb_h'] < candle_now['close']
                    if long_entry:
                        if data['volume'] < candle_now['volume']:
                            reason = 'Triggered' if data['volume'] == 0 else 'Updated'
                            data['volume'] = candle_now['volume']
                            data['datetime'] = candle_now['datetime']
                            print('%s [%s] Long Entry %s, Volume : (%.4f)' % (candle_now['date'], data['symbol'], reason, data['volume']))
                        else:
                            reason = ''
                            price = candle_now['close'] + data['amount_min']
                            amount = using_usdt * self.info.leverage / price
                            self.buyOrder(data, amount, price)

                            print('%s [%s] Long Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Long 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                            data['corner_price'] = price
                            data['volume'] = data['datetime'] = 0
                    elif short_entry:
                        if data['volume'] < candle_now['volume']:
                            reason = 'Triggered' if data['volume'] == 0 else 'Updated'
                            data['volume'] = candle_now['volume']
                            data['datetime'] = candle_now['datetime']
                            print('%s [%s] Short Entry %s, Volume : (%.4f)' % (candle_now['date'], data['symbol'], reason, data['volume']))
                        else:
                            reason = ''
                            price = candle_now['close'] - data['amount_min']
                            amount = using_usdt * self.info.leverage / price
                            self.sellOrder(data, amount, price)

                            print('%s [%s] Short Entry %s- Size (%.4f USDT)' % (candle_now['date'], data['symbol'], reason, using_usdt))
                            self.sendTelegramPush(self.title, '%s [%s]' % (candle_now['date'], data['symbol']), 'Short 진입 %s' % reason, 'Size (%.4f USDT / %.4f USDT)' % (using_usdt, self.balance['total']))

                            data['corner_price'] = price
                            data['volume'] = data['datetime'] = 0

                    if data['datetime'] != 0 and data['datetime'] < candle_now['datetime'] - 300000:
                        data['volume'] = data['datetime'] = 0
                        print('%s [%s] Entry Reset' % (candle_now['date'], data['symbol']))

                if data['position'] is not None:
                    bb_length = candle_now['bb_h'] - candle_now['bb_l']
                    if data['position'] == 'Long':
                        # 물타기
                        if candle_now['close'] > data['entry'] - bb_length * 0.5:
                            self.makeBuyOrder(data, data['amount'] / 3, data['entry'] - bb_length * 0.5)
                        if candle_now['close'] > data['entry'] - bb_length:
                            self.makeBuyOrder(data, data['amount'] / 3, data['entry'] - bb_length)
                        if candle_now['close'] > data['entry'] - bb_length * 1.5:
                            self.makeBuyOrder(data, data['amount'] / 3, data['entry'] - bb_length * 1.5)

                        # 익절
                        if data['corner_price'] < candle_now['bb_l'] + bb_length * 0.8:
                            self.makeSellOrder(data, data['amount'] * 0.2, candle_now['bb_h'] - bb_length * 0.2)
                        if data['corner_price'] < candle_now['bb_l'] + bb_length:
                            self.makeSellOrder(data, data['amount'] * 0.4, candle_now['bb_h'])
                    else:
                        # 물타기
                        if candle_now['close'] < data['entry'] + bb_length * 0.5:
                            self.makeSellOrder(data, data['amount'] / 3, data['entry'] + bb_length * 0.5)
                        if candle_now['close'] < data['entry'] + bb_length:
                            self.makeSellOrder(data, data['amount'] / 3, data['entry'] + bb_length)
                        if candle_now['close'] < data['entry'] + bb_length * 1.5:
                            self.makeSellOrder(data, data['amount'] / 3, data['entry'] + bb_length * 1.5)

                        # 익절
                        if data['corner_price'] > candle_now['bb_h'] - bb_length * 0.8:
                            self.makeBuyOrder(data, data['amount'] * 0.2, candle_now['bb_l'] + bb_length * 0.2)
                        if data['corner_price'] > candle_now['bb_h'] - bb_length:
                            self.makeBuyOrder(data, data['amount'] * 0.4, candle_now['bb_l'])

                # print('    %s %s \n %s' % (candle_now['date'], self.simulation_order, data['entry']))
                if not self.is_simulate:
                    print('    data %s' % data)

            candle_count += 1

        if self.is_simulate:
            for data in self.positions_data:
                if data['position'] is not None:
                    print('[%s] unrealized pnl %.4f' % (data['symbol'], data['pnl']))
                    self.balance['total'] += data['pnl']

                total_tx = data['win'] + data['lose']
                print('[%s] summary : Win rate (%d / %d, %.4f%%), Total profit (%.4f USDT), Avg profit (%.4f USDT), Total loss (%.4f USDT), Avg loss (%.4f USDT), Commission (%.4f USDT), Total PnL (%.4f USDT, %.4f%%)' % (data['symbol'], data['win'], total_tx, 0 if total_tx == 0 else (data['win'] * 100) / total_tx, data['profit'], 0 if data['win'] == 0 else data['profit'] / data['win'], data['loss'], 0 if data['lose'] == 0 else data['loss'] / data['lose'], data['commission'], data['profit'] + data['loss'], (data['profit'] + data['loss']) * 100 / self.simulation_usdt))

            print('Total (%.4f USDT), Total PnL (%.4f%%)' % (self.balance['total'], (self.balance['total'] - self.simulation_usdt) * 100 / self.simulation_usdt))

    @staticmethod
    def floor(num):
        return math.floor(num * 100000000) / 100000000


if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

Bot(config_file_name).start()


# -*- coding: utf-8 -*-
import time

import requests
import threading
import json
import telegram
from telegram.ext import Updater
from telegram.ext import CommandHandler


class Telegram:
    def __init__(self, config_file_name):
        with open(config_file_name) as json_file:
            json_data = json.load(json_file)
            self.token = json_data['token']
            self.id = json_data['telegram_id']
            self.bot = telegram.Bot(self.token)
            '''
            self.updater = Updater(token=self.token, use_context=True)
            self.dispatcher = self.updater.dispatcher
            
            self.start_handler = CommandHandler('start', self.start)
            self.dispatcher.add_handler(self.start_handler)
            
            self.updater.start_polling()
            '''

    def start(self, update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="아이앰더봇")

    def sendTelegramPush(self, *msgs):
        if self.token == '' or self.id == '':
            return

        msg = ''
        for i in range(len(msgs)):
            msg += str(msgs[i]) + '\n'

        t = threading.Thread(target=self.run, args=(msg,))
        t.daemon = True
        t.start()

    def run(self, msg):
        self.bot.sendMessage(self.id, msg)
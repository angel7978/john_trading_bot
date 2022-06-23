# -*- coding: utf-8 -*-

import bot
import sys

if len(sys.argv) <= 1:
    config_file_name = 'config.json'
else:
    config_file_name = sys.argv[1]

#  bot.Bot(config_file_name).simulate(48*14)
bot.Bot(config_file_name).start()
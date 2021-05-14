# -*- coding: utf-8 -*-
import sqlite3
import re
import telebot
import config
import requests
import os.path
from telebot import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "database_exchange.db")
BASE_INFO = {'timestamp': None}
bot = telebot.TeleBot(config.TOKEN_bot)


# http://api.exchangeratesapi.io/v1/timeseries?access_key=55f965b9e0dba230b42830287b8cc6a1&start_date=2012-05-01&end_date%20=2012-05-25
# Попытка вывести timeseries с использованием токена, но выдает Access Restricted

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.text == '/start':
        bot.send_message(message.chat.id,
                         """Приветсввую, {0.first_name}!\nЯ - <b>{1.first_name}</b>, бот созданный для конверта валют.\n
                         Для вывода помощи введите '/help'""".format(message.from_user, bot.get_me()),
                         parse_mode='html')
    elif message.text == '/help':
        bot.send_message(message.chat.id,
                         """   Для начала работы введите '/list' или '/lst', что бы увидеть соотношение курса на базе EUR в текущий момент времени.
Если вы уже ознакомлены с курсом, можете ввести выражение в виде: 
<b>'Exchange:10/EURtoARS'</b>, где 'ARS'-желаемая валюта""",parse_mode='html')


def get_timestamp():
    html = requests.get(
        "http://api.exchangeratesapi.io/latest?access_key=55f965b9e0dba230b42830287b8cc6a1&base=EUR").json()
    return html['timestamp']


def info_adder(dd, timestamp, base, date):
    dd['timestamp'] = timestamp
    dd['base'] = base
    dd['date'] = date


def insert_keyboard():
    keypad = types.InlineKeyboardMarkup()
    item_yes = types.InlineKeyboardButton(text="Да", callback_data='yes')
    item_no = types.InlineKeyboardButton(text="Нет", callback_data='no')
    keypad.add(item_yes, item_no)
    return keypad


@bot.message_handler(commands=['list', 'lst'])
def send_info(message):
    if BASE_INFO['timestamp'] == get_timestamp():
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            bot.send_message(message.chat.id,
                             f"<b>timestamp:{BASE_INFO['timestamp']}\nbase:{BASE_INFO['base']}\ndate:{BASE_INFO['date']}</b>",
                             parse_mode='html')
            for key, value in cursor.execute(f'SELECT * FROM rates'):
                bot.send_message(message.chat.id, text=f"{key} : {value}")

    else:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as db:
                cursor = db.cursor()
                cursor.execute("""DELETE FROM rates""")
        html = requests.get(
            "http://api.exchangeratesapi.io/latest?access_key=55f965b9e0dba230b42830287b8cc6a1&base=EUR").json()
        rates_dict = html["rates"]
        info_adder(BASE_INFO, timestamp=html['timestamp'], base=html['base'], date=html['date'])
        bot.send_message(message.chat.id,
                         f"<b>timestamp:{BASE_INFO['timestamp']}\nbase:{BASE_INFO['base']}\ndate:{BASE_INFO['date']}</b>",
                         parse_mode='html')
        n = 0
        for key, value in rates_dict.items():
            with sqlite3.connect(db_path) as db:
                cursor = db.cursor()
                cursor.execute(""" CREATE TABLE IF NOT EXISTS rates(name TEXT, value REAL) """)
                cursor.execute(f""" INSERT INTO rates (name, value) VALUES('{key}',{round(value, 2)})""")
                db.commit()
            bot.send_message(message.chat.id, text=f"{key} : {round(value, 2)}")
            n += 1
            if n == 99:
                break
    keypad = insert_keyboard()
    bot.send_message(message.chat.id, text="Желаете конвертировать валюту?", reply_markup=keypad)


@bot.callback_query_handler(func=lambda call: True)
def answer(call):
    if call.message:
        if call.data == 'yes':
            bot.send_message(call.message.chat.id,
                             text="Введите выражение в виде: 'Exchange:10/EURtoARS', где 'ARS'-желаемая валюта")
        elif call.data == 'no':
            pass
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Принято", reply_markup=None)


@bot.message_handler(content_types=['text'])
def run(message):
    if re.match(r'exchange:', message.text.lower()):
        try:
            count = int(re.search('[-0-9]+', message.text).group())
            currency = message.text[12:].split('to')[1]
            bot.send_message(chat_id=message.chat.id, text=f"{count},{currency}")
            with sqlite3.connect(db_path) as db:
                cursor = db.cursor()
                for key, value in cursor.execute(f'SELECT * FROM rates'):
                    if key == currency:
                        bot.send_message(chat_id=message.chat.id, text=f"{count} EUR = {count * value} {key}$")
        except Exception as ex:
            bot.send_message(chat_id=message.chat.id, text="Хм, что-то пошло не так. Странно...")
        keypad = insert_keyboard()
        bot.send_message(message.chat.id, text="Желаете конвертировать валюту?", reply_markup=keypad)
    else:
        bot.send_message(chat_id=message.chat.id, text="Я вас не понимаю")


bot.polling(none_stop=True)

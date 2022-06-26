import json
import os
import random
import sqlite3
import string
import threading
import time

import numpy as np
import pandas as pd
import requests
# https://medium.com/@chris_42047/real-time-price-updates-from-binance-exchange-using-web-sockets-python-cd8374c50fcd
# https://github.com/sammchardy/python-binance
# https://github.com/LUCIT-Systems-and-Development/unicorn-binance-websocket-api
from binance.client import Client
from telegram.ext import Updater
from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager

# TELEGRAM Constants
TG_TOKEN = '1079945138:AAFpAWUd8AYgTsq8dkjJKg_HOEWAIXHItTA'
TG_URL = "https://api.telegram.org/bot{}/".format(TG_TOKEN)
ChatID = '-434324601'
# Telegram BOT starter functions
updater = Updater(TG_TOKEN)
dispatcher = updater.dispatcher
MyBot = updater.bot  # Bot instance to use that is bound to the token.

API_KEY = 'n3iweYuOAx3UXKyT95t2q9MiT4dy7cMiwghjs8TSAFLDYBpeEwElWgbLIVn1Nu7B'
API_KEY_SECRET = 'kreH4pr4kX22FXrbni0ExyJuXasnMeXNPDfW6P1NzZbVKRq4WVgOg2mja4gb9rhT'
base_endpoint = 'https://api.binance.com'  # Select the Binance API endpoint for your exchange

# Initialize binance client
client = Client(api_key=API_KEY, api_secret=API_KEY_SECRET, tld='com')

end = int(time.time() * 1000)  # 1635015600000
start = end - 60000 * 60 * 24 * 1  # 1633708800000
TIMEFRAMES = ('M5', 'M15', 'H1', 'H4', 'D1')
TABLE_NAMES = ('COIN_M5', 'COIN_M15', 'COIN_H1', 'COIN_H4', 'COIN_D1')

'''Get binance latest new listing announcements'''


def get_announcement():
    """
    Retrieves new coin listing announcements
    """
    # Generate random query/params to help prevent caching
    rand_page_size = random.randint(1, 200)
    letters = string.ascii_letters
    random_string = "".join(random.choice(letters) for i in range(random.randint(10, 20)))
    random_number = random.randint(1, 99999999999999999999)
    queries = [
        "type=1",
        "catalogId=48",
        "pageNo=1",
        f"pageSize={str(rand_page_size)}",
        f"rnd={str(time.time())}",
        f"{random_string}={str(random_number)}",
    ]
    random.shuffle(queries)
    request_url = (
        f"https://www.binance.com/gateway-api/v1/public/cms/article/list/query"
        f"?{queries[0]}&{queries[1]}&{queries[2]}&{queries[3]}&{queries[4]}&{queries[5]}"
    )
    latest_announcement = requests.get(request_url)
    if latest_announcement.status_code == 200:
        latest_announcement = latest_announcement.json()
        return latest_announcement["data"]["catalogs"][0]["articles"][0]["title"]
    else:
        return ""


# util function to check if the message from Binance is empty
def is_empty_message(message):
    if message is False:
        return True
    if '"result":null' in message:
        return True
    if '"result":None' in message:
        return True
    return False


'''The next function handles price changes. This is the integration point where 
you want to add your code for evaluating the price change, e.g. for generating 
buy or sell signals'''


def handle_price_change(symbol, timestamp, price):
    print(f"Handle price change for symbol: {symbol}, timestamp: {timestamp}, price: {price}")


'''pops the last message from the data stream buffer and converts it to JSON 
and then calls the handle_price_change() function'''


def process_stream_data(binance_websocket_api_manager):
    while True:
        if binance_websocket_api_manager.is_manager_stopping():
            exit(0)
        oldest_data = binance_websocket_api_manager.pop_stream_data_from_stream_buffer()
        is_empty = is_empty_message(oldest_data)
        if is_empty:
            time.sleep(0.01)
        else:
            oldest_data_dict = json.loads(oldest_data)
            print(oldest_data_dict)
            data = oldest_data_dict['data']
            #  Handle price change
            handle_price_change(symbol=data['s'], timestamp=data['T'], price=data['p'])


'''
- establishes a web socket manager connection
- sets the exchange, the streams and symbols to listen to 
- and sets the API keys for authentication
- Then it starts a new thread to listen to changes and passes the 
process_stream_data() function to handle events
'''


def start_websocket_listener():
    binance_us_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.us")
    channels = {'trade', }
    binance_us_websocket_api_manager.create_stream(channels, markets=lc_symbols, api_key=API_KEY,
                                                   api_secret=API_KEY_SECRET)
    # Start a worker process to move the received stream_data from the stream_buffer to a print function
    worker_thread = threading.Thread(target=process_stream_data, args=(binance_us_websocket_api_manager,))
    worker_thread.start()


'''
get the supported symbols for the exchange and exchange info 
using the Binance client
'''


def get_traded_symbols():
    symbols = []
    exchange_info = client.get_exchange_info()
    for s in exchange_info['symbols']:
        symbols.append(s['symbol'])
    return symbols


def get_all_symbols():
    t1 = time.time() * 1000
    tickers = client.get_all_tickers()
    symbol_list_usdt = []
    symbol_list_btc = []
    for item in tickers:
        symb = item['symbol']
        if 'USDT' in symb and 'BTC' not in symb:
            symbol_list_usdt.append(symb.lower())
        elif 'BTC' in symb and 'USD' not in symb and 'UST' not in symb:
            symbol_list_btc.append(symb.lower())
    all_symbols = symbol_list_btc + symbol_list_btc
    all_symbols = np.array(all_symbols)
    print(f"All coin names are gathered in {0.001 * (time.time() * 1000 - t1):.2f} seconds.\n")
    return all_symbols


class Coin:

    def __init__(self, name):
        self.name = name.upper()
        self.data = {'TIME': 0, 'OPEN': 0, 'HIGH': 0, 'LOW': 0, 'CLOSE': 0, 'VOLUME': 0}
        self.M5 = pd.DataFrame(data=self.data, index=[0])
        self.M15 = pd.DataFrame(data=self.data, index=[0])
        self.H1 = pd.DataFrame(data=self.data, index=[0])
        self.H4 = pd.DataFrame(data=self.data, index=[0])
        self.D1 = pd.DataFrame(data=self.data, index=[0])
        self.filenameM5 = "db/M5_" + self.name
        self.filenameM15 = "db/M15_" + self.name
        self.filenameM30 = "db/M30_" + self.name
        self.filenameH1 = "db/H1_" + self.name
        self.filenameH4 = "db/H4_" + self.name
        self.filenameD1 = "db/D1_" + self.name

    @staticmethod
    def update_indicators(df):
        df['RSI'] = calc_rsi(df['CLOSE'])
        df['IFTRSI'] = calc_iftrsi(df['RSI'])
        df['BOLL_H'], df['BOLL_L'], df['BOLL_M'] = calc_bollinger(df['CLOSE'])
        df['MACD'], df['MACD_S'] = calc_macd(df['CLOSE'])
        df['MA_200'] = sma(df['CLOSE'], 200)
        df['MA_50'] = sma(df['CLOSE'], 50)
        df['MA_20'] = sma(df['CLOSE'], 20)
        df['VOLUME(10)'] = sma(df['VOLUME'], 10)

    def initialize_dfs(self, start_time, end_time):
        t1 = time.time() * 1000
        print(self.name)
        INTERVALS = [Client.KLINE_INTERVAL_5MINUTE, Client.KLINE_INTERVAL_15MINUTE, Client.KLINE_INTERVAL_1HOUR,
                     Client.KLINE_INTERVAL_4HOUR, Client.KLINE_INTERVAL_1DAY]
        HOW_MUCH_BACK = 60  # 220 - How many candles back for each timeframe(220 to calculate MA200)
        DURATIONS = [1000 * 60 * 5 * HOW_MUCH_BACK, 1000 * 60 * 15 * HOW_MUCH_BACK,
                     1000 * 60 * 60 * HOW_MUCH_BACK, 1000 * 60 * 240 * HOW_MUCH_BACK, 1000 * 60 * 1440 * HOW_MUCH_BACK]
        # Creating ohlc and indicators
        for i in range(len(INTERVALS)):
            start_time = end_time - DURATIONS[i]
            kline = np.array(client.get_historical_klines(self.name, INTERVALS[i], start_time, end_time))
            vars(self)[TIMEFRAMES[i]] = pd.DataFrame(kline.reshape(-1, 12)[:, :6], dtype=float,
                                                     columns=('TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'))
            self.update_indicators(vars(self)[TIMEFRAMES[i]])
        print(f"Klines are collected and dataframes are initialized in {0.001 * (time.time() * 1000 - t1):.2f} secs.")

    def update_dfs_by_kline(self, idx, interval, kline):
        filenames = [self.filenameM5, self.filenameM15, self.filenameH1, self.filenameH4, self.filenameD1]
        t1 = time.time() * 1000
        # kline = np.array(client.get_historical_klines(self.name, interval, start_time, end_time))
        df_temp = pd.DataFrame(kline, dtype=float,
                               columns=('TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'))
        # Check if the init kline collection got the latest candle without closing.
        if int(vars(self)[TIMEFRAMES[idx]]['TIME'].iloc[-1]) == int(df_temp['TIME'].iloc[-1]):
            vars(self)[TIMEFRAMES[idx]] = vars(self)[TIMEFRAMES[idx]][:-1]
        vars(self)[TIMEFRAMES[idx]] = vars(self)[TIMEFRAMES[idx]].append(df_temp).reset_index(drop=True)
        self.update_indicators(vars(self)[TIMEFRAMES[idx]])
        del df_temp
        conn = sqlite3.connect(str(filenames[idx] + '.db'))
        vars(self)[TIMEFRAMES[idx]].to_sql(TABLE_NAMES[idx], conn, if_exists='replace', index=False)
        conn.commit()
        conn.close()
        print(f"Klines are collected and dataframes are updated in {0.001 * (time.time() * 1000 - t1):.2f} secs.")

    def check_db(self):
        return os.path.isfile(str(self.filenameM5 + '.db'))

    def read_dbs(self):
        filenames = [self.filenameM5, self.filenameM15, self.filenameH1, self.filenameH4, self.filenameD1]
        for i in range(len(TIMEFRAMES)):
            conn = sqlite3.connect(str(filenames[i] + '.db'))
            vars(self)[TIMEFRAMES[i]] = pd.read_sql_query(f"SELECT * FROM {TABLE_NAMES[i]}", conn)
            conn.close()

    def create_dbs(self):
        filenames = [self.filenameM5, self.filenameM15, self.filenameH1, self.filenameH4, self.filenameD1]
        for i in range(len(TIMEFRAMES)):
            conn = sqlite3.connect(str(filenames[i] + '.db'))
            vars(self)[TIMEFRAMES[i]].to_sql(TABLE_NAMES[i], conn, if_exists='replace', index=False)
            conn.commit()
            conn.close()

    def append2db(self):
        filenames = [self.filenameM5, self.filenameM15, self.filenameH1, self.filenameH4, self.filenameD1]
        for i in range(len(TIMEFRAMES)):
            conn = sqlite3.connect(str(filenames[i] + '.db'))
            vars(self)[TIMEFRAMES[i]].to_sql(TABLE_NAMES[i], conn, if_exists='replace', index=False)
            conn.commit()
            conn.close()


def calc_rsi(series):
    rsi_length = 14
    delta = series.diff().dropna()
    delta = delta[1:]
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    roll_up1 = up.ewm(alpha=1 / rsi_length).mean()
    roll_down1 = down.abs().ewm(alpha=1 / rsi_length).mean()
    rsi1 = 100.0 - (100.0 / (1.0 + roll_up1 / roll_down1))
    return rsi1


def calc_iftrsi(series):
    period = 9
    v1 = 0.1 * (series - 50)
    v2 = v1.ewm(alpha=1 / period).mean()
    iftrsi = (np.exp(2 * v2) - 1) / (np.exp(2 * v2) + 1)
    return iftrsi


def calc_bollinger(df):
    length = 20
    std = 2
    mean = df.rolling(window=length).mean()
    st = df.rolling(window=length).apply(np.std)
    return (mean + std * st, mean - std * st, mean)


def sma(df, period):
    return df.rolling(window=period).mean()


def calc_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def initialize_coins(symbols):
    t1 = time.time() * 1000
    coin_objects = np.array([])
    for names in symbols:
        a_coin = Coin(names)
        if a_coin.check_db():
            a_coin.read_dbs()
        else:
            a_coin.initialize_dfs(start, end)
            a_coin.create_dbs()
        coin_objects = np.append(coin_objects, a_coin)
    print(f"All coins are initialized in {0.001 * (time.time() * 1000 - t1):.2f} seconds.\n")
    return coin_objects


def create_new_kline(data):
    interval = data['i']
    symbol = data['s']
    idx = np.where(all_symbols == symbol.lower())[0][0]
    coin = coin_list[idx]
    new_kline = np.array(
        [data['t'], data['o'], data['h'], data['l'], data['c'], data['v']]).reshape(-1, 6)
    if interval == '5m':
        idx_tf = 0
        df = coin.M5
        if df['TIME'].iloc[-1] < int(data['t']) - 5 * 60 * 1000:
            new_kline = np.array(
                client.get_historical_klines(coin.name, '5m', int(df['TIME'].iloc[-1] + 10000),
                                             int(time.time() * 1000))).reshape(-1, 12)[:, :6]
    elif interval == '15m':
        idx_tf = 1
        df = coin.M15
        if df['TIME'].iloc[-1] < int(data['t']) - 15 * 60 * 1000:
            new_kline = np.array(
                client.get_historical_klines(coin.name, '15m', int(df['TIME'].iloc[-1] + 10000),
                                             int(time.time() * 1000))).reshape(-1, 12)[:, :6]
    elif interval == '1h':
        idx_tf = 2
        df = coin.H1
        if df['TIME'].iloc[-1] < int(data['t']) - 60 * 60 * 1000:
            new_kline = np.array(
                client.get_historical_klines(coin.name, '1h', int(df['TIME'].iloc[-1] + 10000),
                                             int(time.time() * 1000))).reshape(-1, 12)[:, :6]
    elif interval == '4h':
        idx_tf = 3
        df = coin.H4
        if df['TIME'].iloc[-1] < int(data['t']) - 240 * 60 * 1000:
            new_kline = np.array(
                client.get_historical_klines(coin.name, '4h', int(df['TIME'].iloc[-1] + 10000),
                                             int(time.time() * 1000))).reshape(-1, 12)[:, :6]
    elif interval == '1d':
        idx_tf = 4
        df = coin.D1
        if df['TIME'].iloc[-1] < int(data['t']) - 1440 * 60 * 1000:
            new_kline = np.array(
                client.get_historical_klines(coin.name, '1d', int(df['TIME'].iloc[-1] + 10000),
                                             int(time.time() * 1000))).reshape(-1, 12)[:, :6]
    return coin, idx_tf, interval, new_kline


def is_price_jump(coin):
    if coin.M5['CLOSE'].iloc[-1] / coin.M5['OPEN'].iloc[-1] > 1.10:
        return True
    return False


def is_volume_jump(coin):
    if coin.H1['VOLUME'].iloc[-1] / coin.H1['VOLUME(10)'].iloc[-1] > 2.0:
        return True
    return False


def validate_symbols(all_symbols):
    end = int(time.time() * 1000)
    start = end - 60000 * 60
    symbols = np.array([])
    for i in range(len(all_symbols)):
        kline = np.array(
            client.get_historical_klines(all_symbols[i].upper(), Client.KLINE_INTERVAL_5MINUTE, start, end))
        if len(kline) > 0:
            symbols = np.append(symbols, all_symbols[i])
    return symbols


'''
main() function in which we are defining the crypto symbols we want to 
get price updates for, then initializing the Binance client, calling some 
Binance client APIs to get exchange info and finally we are starting the 
WebSocket listener to get price updates
'''

all_symbols = get_all_symbols()
all_symbols = np.unique(all_symbols[0:50])
all_symbols = validate_symbols(all_symbols)
number_of_coins = len(all_symbols)
# all_symbols = np.array(['ethbtc', 'ltcbtc'])
print('Creating coin instances and initializing databases...', len(all_symbols), '\n', all_symbols)  # [0:2]
coin_list = initialize_coins(all_symbols)  # [0:2]


def main():
    print('Generating binance websocket api manager...')
    binance_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.com", output_default="dict")
    binance_websocket_api_manager.create_stream('kline_5m', all_symbols, stream_label="dict", output="dict")
    # TODO: create ticker instances
    # TODO: check if there is a database for each ticker
    # TODO: get kline info of ticker and create/update database
    # TODO: add telegram bot
    # TODO: add plotly traces

    # MyBot.send_message(chat_id=ChatID, text='Binance tracker started')
    last_announcement = get_announcement()
    last_announcement_time = time.time()
    print(last_announcement)
    last_data_time = coin_list[1].M5['TIME'].values[-1]
    print(last_data_time)
    count = 0
    sleep = 0  # if it sleeps but no websocket info was found for an iteration, it shouldnt sleep that much again.
    while True:
        now = time.time() * 1000
        if count == 0 and sleep == 0 and now < last_data_time + 60000 * 10:
            s = int(0.001 * (last_data_time + 60000 * 10 - now)) + 5
            print(f"Sleeping for {s} seconds.")
            time.sleep(s)
            sleep = 1
        if binance_websocket_api_manager.is_manager_stopping():
            exit(0)
        oldest_stream_data_from_stream_buffer = binance_websocket_api_manager.pop_stream_data_from_stream_buffer()
        if oldest_stream_data_from_stream_buffer is False:
            time.sleep(1)
        else:
            if oldest_stream_data_from_stream_buffer is not None:
                # try:
                now = time.time()
                if now - last_announcement_time > 3600:
                    new_announcement = get_announcement()
                    if last_announcement != new_announcement:
                        last_announcement = new_announcement
                        print(new_announcement)
                        MyBot.send_message(chat_id=ChatID, text=str(new_announcement))
                    last_announcement_time = now
                if 'data' in oldest_stream_data_from_stream_buffer.keys():
                    if oldest_stream_data_from_stream_buffer['data']['k']['x']:
                        print(oldest_stream_data_from_stream_buffer['data']['k'])
                        data = oldest_stream_data_from_stream_buffer['data']['k']
                        coin, idx_tf, interval, new_kline = create_new_kline(data)
                        coin.update_dfs_by_kline(idx_tf, interval, new_kline)
                        # print('df:\n', df.tail())
                        price_rocket = is_price_jump(coin)
                        volume_rocket = is_volume_jump(coin)
                        msg = ""
                        if price_rocket:
                            msg += f"{coin.name} price went up {100 * (coin.M5['CLOSE'].iloc[-1] / coin.M5['OPEN'].iloc[-1] - 1):.2f}%\n"
                        if volume_rocket:
                            msg += f"{coin.name} volume went up {100 * (coin.H1['VOLUME'].iloc[-1] / coin.H1['VOLUME(10)'].iloc[-1] - 1):.2f}%\n"
                        if price_rocket or volume_rocket:
                            MyBot.send_message(chat_id=ChatID, text=msg)
                        count += 1
                        print(count)
                        if count == number_of_coins:
                            count = 0
                            sleep = 0
                            last_data_time = coin.M5['TIME'].iloc[-1]
                            print(time.time() * 1000, last_data_time)
                # except Exception as e:
                #     print(str(e))
        # TODO: set a timer and check if binance announcement changes, return new listing info
        # TODO: set another timer and check for telegram requests
        # TODO: send plotly analysis image(supports and resistances)
        # TODO: add price action info


if __name__ == "__main__":
    main()

#  Get traded symbols
# traded_symbols = get_traded_symbols()
# print("Traded symbols: ", traded_symbols)


# start_websocket_listener()

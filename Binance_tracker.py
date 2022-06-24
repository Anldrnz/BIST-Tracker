import json
import os
import random
import sqlite3
import string
import threading
import time

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests
# https://medium.com/@chris_42047/real-time-price-updates-from-binance-exchange-using-web-sockets-python-cd8374c50fcd
# https://github.com/sammchardy/python-binance
# https://github.com/LUCIT-Systems-and-Development/unicorn-binance-websocket-api
from binance.client import Client
from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager

API_KEY = 'n3iweYuOAx3UXKyT95t2q9MiT4dy7cMiwghjs8TSAFLDYBpeEwElWgbLIVn1Nu7B'
API_KEY_SECRET = 'kreH4pr4kX22FXrbni0ExyJuXasnMeXNPDfW6P1NzZbVKRq4WVgOg2mja4gb9rhT'
base_endpoint = 'https://api.binance.com'  # Select the Binance API endpoint for your exchange

# Initialize binance client
client = Client(api_key=API_KEY, api_secret=API_KEY_SECRET, tld='com')

end = int(time.time() * 1000)  # 1635015600000
start = end - 60000 * 60 * 24 * 10  # 1633708800000
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
    print(request_url)

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
    tickers = client.get_all_tickers()
    symbol_list_usdt = []
    symbol_list_btc = []
    all_symbols = []
    for item in tickers:
        symb = item['symbol']
        if 'USDT' in symb and 'BTC' not in symb:
            symbol_list_usdt.append(symb.lower())
        elif 'BTC' in symb and 'USD' not in symb:
            symbol_list_btc.append(symb.lower())
    all_symbols = symbol_list_btc + symbol_list_btc

    print(len(symbol_list_usdt), symbol_list_usdt)
    print(len(symbol_list_btc), symbol_list_btc)

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
        t2 = time.time()
        print(self.name)
        kline = client.get_historical_klines(self.name, Client.KLINE_INTERVAL_5MINUTE, start_time, end_time)
        print(f'Klines were collected in {time.time() - t2:.2f} seconds...')
        self.M5.drop(index=self.M5.index[0], axis=0, inplace=True)
        self.M15.drop(index=self.M15.index[0], axis=0, inplace=True)
        self.H1.drop(index=self.H1.index[0], axis=0, inplace=True)
        self.H4.drop(index=self.H4.index[0], axis=0, inplace=True)
        self.D1.drop(index=self.D1.index[0], axis=0, inplace=True)
        # Creating 5M timeframe ohlc and indicators
        for i in range(len(kline) - 1):
            self.M5 = self.M5.append({
                'TIME': float(kline[i][0]),
                'OPEN': float(kline[i][1]),
                'HIGH': float(kline[i][2]),
                'LOW': float(kline[i][3]),
                'CLOSE': float(kline[i][4]),
                'VOLUME': float(kline[i][5]),
                'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                'MA_200': 0, 'MA_50': 0, 'MA_10': 0
            }, ignore_index=True)
        self.update_indicators(self.M5)
        # Creating remaining timeframe ohlc and indicators
        for i in range(2, len(self.M5), 3):
            self.M15 = self.M15.append(
                {'TIME': float(self.M5['TIME'][i - 2]), 'OPEN': float(self.M5['OPEN'][i - 2]),
                 'HIGH': max(float(self.M5['HIGH'][i]), float(self.M5['HIGH'][i - 1]),
                             float(self.M5['HIGH'][i - 2])),
                 'LOW': min(float(self.M5['LOW'][i]), float(self.M5['LOW'][i - 1]),
                            float(self.M5['LOW'][i - 2])),
                 'CLOSE': float(self.M5['CLOSE'][i]),
                 'VOLUME': sum([float(self.M5['VOLUME'][i]), float(self.M5['VOLUME'][i - 1]),
                                float(self.M5['VOLUME'][i - 2])]),
                 'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                 'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
            if (i + 1) % 12 == 0 and i >= 11:
                self.H1 = self.H1.append(
                    {'TIME': float(self.M15['TIME'].iloc[-4]), 'OPEN': float(self.M15['OPEN'].iloc[-4]),
                     'HIGH': max(float(self.M15['HIGH'].iloc[-1]), float(self.M15['HIGH'].iloc[-2]),
                                 float(self.M15['HIGH'].iloc[-3]), float(self.M15['HIGH'].iloc[-4])),
                     'LOW': min(float(self.M15['LOW'].iloc[-1]), float(self.M15['LOW'].iloc[-2]),
                                float(self.M15['LOW'].iloc[-3]), float(self.M15['LOW'].iloc[-4])),
                     'CLOSE': float(self.M15['CLOSE'].iloc[-1]),
                     'VOLUME': sum([float(self.M15['VOLUME'].iloc[-1]), float(self.M15['VOLUME'].iloc[-2]),
                                    float(self.M15['VOLUME'].iloc[-3]), float(self.M15['VOLUME'].iloc[-4])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
            if (i + 1) % 48 == 0 and i >= 47:
                self.H4 = self.H4.append(
                    {'TIME': float(self.H1['TIME'].iloc[-4]), 'OPEN': float(self.H1['OPEN'].iloc[-4]),
                     'HIGH': max(float(self.H1['HIGH'].iloc[-1]), float(self.H1['HIGH'].iloc[-2]),
                                 float(self.H1['HIGH'].iloc[-3]), float(self.H1['HIGH'].iloc[-4])),
                     'LOW': min(float(self.H1['LOW'].iloc[-1]), float(self.H1['LOW'].iloc[-2]),
                                float(self.H1['LOW'].iloc[-3]), float(self.H1['LOW'].iloc[-4])),
                     'CLOSE': float(self.H1['CLOSE'].iloc[-1]),
                     'VOLUME': sum([float(self.H1['VOLUME'].iloc[-1]), float(self.H1['VOLUME'].iloc[-2]),
                                    float(self.H1['VOLUME'].iloc[-3]), float(self.H1['VOLUME'].iloc[-4])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
            if (i + 1) % 288 == 0 and i >= 287:
                self.D1 = self.D1.append(
                    {'TIME': float(self.H4['TIME'].iloc[-6]), 'OPEN': float(self.H4['OPEN'].iloc[-6]),
                     'HIGH': max(float(self.H4['HIGH'].iloc[-1]), float(self.H4['HIGH'].iloc[-2]),
                                 float(self.H4['HIGH'].iloc[-3]), float(self.H4['HIGH'].iloc[-4]),
                                 float(self.H4['HIGH'].iloc[-5]), float(self.H4['HIGH'].iloc[-6])),
                     'LOW': min(float(self.H4['LOW'].iloc[-1]), float(self.H4['LOW'].iloc[-2]),
                                float(self.H4['LOW'].iloc[-3]), float(self.H4['LOW'].iloc[-4]),
                                float(self.H4['LOW'].iloc[-5]), float(self.H4['LOW'].iloc[-6])),
                     'CLOSE': float(self.H4['CLOSE'].iloc[-1]),
                     'VOLUME': sum(
                         [float(self.H4['VOLUME'].iloc[-1]), float(self.H4['VOLUME'].iloc[-2]),
                          float(self.H4['VOLUME'].iloc[-3]), float(self.H4['VOLUME'].iloc[-4]),
                          float(self.H4['VOLUME'].iloc[-5]), float(self.H4['VOLUME'].iloc[-6])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
                self.update_indicators(self.M15)
                self.update_indicators(self.H1)
                self.update_indicators(self.H4)
                self.update_indicators(self.D1)

                '''
                main() function in which we are defining the crypto symbols we want to 
                get price updates for, then initializing the Binance client, calling some 
                Binance client APIs to get exchange info and finally we are starting the 
                WebSocket listener to get price updates
                '''

    def update_dfs_by_kline(self, kline):
        update_m15 = False
        update_h1 = False
        update_h4 = False
        update_d1 = False
        for i in range(len(kline)):
            self.M5 = self.M5.append({
                'TIME': float(kline[i][0]),
                'OPEN': float(kline[i][1]),
                'HIGH': float(kline[i][2]),
                'LOW': float(kline[i][3]),
                'CLOSE': float(kline[i][4]),
                'VOLUME': float(kline[i][5]),
                'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                'MA_200': 0, 'MA_50': 0, 'MA_10': 0
            }, ignore_index=True)
            if self.M5['TIME'].iloc[-1] == self.M15['TIME'].iloc[-1] + 60000 * 25:
                self.M15 = self.M15.append(
                    {'TIME': float(self.M5['TIME'].iloc[-3]), 'OPEN': float(self.M5['OPEN'].iloc[-3]),
                     'HIGH': max(float(self.M5['HIGH'].iloc[-1]), float(self.M5['HIGH'].iloc[-2]),
                                 float(self.M5['HIGH'].iloc[-3])),
                     'LOW': min(float(self.M5['LOW'].iloc[-1]), float(self.M5['LOW'].iloc[-2]),
                                float(self.M5['LOW'].iloc[-3])),
                     'CLOSE': float(self.M5['CLOSE'].iloc[-1]),
                     'VOLUME': sum([float(self.M5['VOLUME'].iloc[-1]), float(self.M5['VOLUME'].iloc[-2]),
                                    float(self.M5['VOLUME'].iloc[-3])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
                update_m15 = True
                self.update_indicators(self.M15)
            if self.M5['TIME'].iloc[-1] == self.H1['TIME'].iloc[-1] + 60000 * 115:
                self.H1 = self.H1.append(
                    {'TIME': float(self.M15['TIME'].iloc[-4]), 'OPEN': float(self.M15['OPEN'].iloc[-4]),
                     'HIGH': max(float(self.M15['HIGH'].iloc[-1]), float(self.M15['HIGH'].iloc[-2]),
                                 float(self.M15['HIGH'].iloc[-3]), float(self.M15['HIGH'].iloc[-4])),
                     'LOW': min(float(self.M15['LOW'].iloc[-1]), float(self.M15['LOW'].iloc[-2]),
                                float(self.M15['LOW'].iloc[-3]), float(self.M15['LOW'].iloc[-4])),
                     'CLOSE': float(self.M15['CLOSE'].iloc[-1]),
                     'VOLUME': sum(
                         [float(self.M15['VOLUME'].iloc[-1]), float(self.M15['VOLUME'].iloc[-2]),
                          float(self.M15['VOLUME'].iloc[-3]), float(self.M15['VOLUME'].iloc[-4])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
                update_h1 = True
                self.update_indicators(self.H1)
            if self.M5['TIME'].iloc[-1] == self.H4['TIME'].iloc[-1] + 60000 * 475:
                self.H4 = self.H4.append(
                    {'TIME': float(self.H1['TIME'].iloc[-4]), 'OPEN': float(self.H1['OPEN'].iloc[-4]),
                     'HIGH': max(float(self.H1['HIGH'].iloc[-1]), float(self.H1['HIGH'].iloc[-2]),
                                 float(self.H1['HIGH'].iloc[-3]), float(self.H1['HIGH'].iloc[-4])),
                     'LOW': min(float(self.H1['LOW'].iloc[-1]), float(self.H1['LOW'].iloc[-2]),
                                float(self.H1['LOW'].iloc[-3]), float(self.H1['LOW'].iloc[-4])),
                     'CLOSE': float(self.H1['CLOSE'].iloc[-1]),
                     'VOLUME': sum([float(self.H1['VOLUME'].iloc[-1]), float(self.H1['VOLUME'].iloc[-2]),
                                    float(self.H1['VOLUME'].iloc[-3]), float(self.H1['VOLUME'].iloc[-4])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
                update_h4 = True
                self.update_indicators(self.H4)
            if self.M5['TIME'].iloc[-1] == self.D1['TIME'].iloc[-1] + 60000 * 2875:
                self.D1 = self.D1.append(
                    {'TIME': float(self.H4['TIME'].iloc[-6]), 'OPEN': float(self.H4['OPEN'].iloc[-6]),
                     'HIGH': max(float(self.H4['HIGH'].iloc[-1]), float(self.H4['HIGH'].iloc[-2]),
                                 float(self.H4['HIGH'].iloc[-3]), float(self.H4['HIGH'].iloc[-4]),
                                 float(self.H4['HIGH'].iloc[-5]), float(self.H4['HIGH'].iloc[-6])),
                     'LOW': min(float(self.H4['LOW'].iloc[-1]), float(self.H4['LOW'].iloc[-2]),
                                float(self.H4['LOW'].iloc[-3]), float(self.H4['LOW'].iloc[-4]),
                                float(self.H4['LOW'].iloc[-5]), float(self.H4['LOW'].iloc[-6])),
                     'CLOSE': float(self.H4['CLOSE'].iloc[-1]),
                     'VOLUME': sum([float(self.H4['VOLUME'].iloc[-1]), float(self.H4['VOLUME'].iloc[-2]),
                                    float(self.H4['VOLUME'].iloc[-3]), float(self.H4['VOLUME'].iloc[-4]),
                                    float(self.H4['VOLUME'].iloc[-5]), float(self.H4['VOLUME'].iloc[-6])]),
                     'RSI': 0, 'IFTRSI': 0, 'BOLL_H': 0, 'BOLL_M': 0, 'BOLL_L': 0,
                     'MA_200': 0, 'MA_50': 0, 'MA_10': 0}, ignore_index=True)
                update_d1 = True
                self.update_indicators(self.D1)
        self.update_indicators(self.M5)

    def check_db(self):
        return os.path.isfile(str(self.filenameM5 + '.db'))

    def read_dbs(self):
        filenames = [self.filenameM5, self.filenameM15, self.filenameH1, self.filenameH4, self.filenameD1]
        for i in range(len(TIMEFRAMES)):
            conn = sqlite3.connect(str(filenames[i] + '.db'))
            vars(self)[TIMEFRAMES[i]] = pd.read_sql_query(f"SELECT * FROM {TABLE_NAMES[i]}", conn)
            conn.close()
        if vars(self)['M5']['TIME'].iloc[-1] + 60000 * 5 + 10000 < time.time() * 1000:  # 1634573100000 + 60000 * 6:
            print('-> New data available, checking for klines...')
            t4 = time.time()
            kline = client.get_historical_klines(self.name, Client.KLINE_INTERVAL_5MINUTE,
                                                 int(vars(self)['M5']['TIME'].iloc[-1] + 10000),
                                                 int(time.time() * 1000))
            # int(time.time()*1000)) 1634573100000 + 60000 * 6
            print(f'-> -> New klines were collected in {time.time() - t4:.2f} seconds...')
            t4 = time.time()
            self.update_dfs_by_kline(kline)
            self.append2db()
            print(f'-> -> Databases appended in {time.time() - t4:.2f} seconds...')

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
    return (df.rolling(window=length).mean() + std * df.rolling(window=length).apply(
        np.std)), (df.rolling(window=length).mean() - std * df.rolling(window=length).apply(np.std)), (
               df.rolling(window=length).mean())


def sma(df, period):
    return df.rolling(window=period).mean()


def calc_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def initialize_coins(symbols):
    coin_objects = np.array([])
    for names in symbols:
        a_coin = Coin(names)
        coin_objects = np.append(coin_objects, a_coin)
        # print(f'\nCoin * - {a_coin.name} - * created...')
        # print('-> -> Checking if the databases were created...')
        if a_coin.check_db():
            # t1 = time.time()
            a_coin.read_dbs()
            # print(f'-> -> Read the existing dbs in {time.time() - t1:.2f} seconds...')
        else:
            # t1 = time.time()
            a_coin.initialize_dfs(start, end)
            # print(f'-> -> Dataframes initialized in {time.time() - t1:.2f} seconds...')
            # t1 = time.time()
            a_coin.create_dbs()
            # print(f'-> -> Databases are created in {time.time() - t1:.2f} seconds...')
        # print("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
    return coin_objects


def main():
    print('Getting the list of all symbols...')
    # all_symbols = get_all_symbols()
    all_symbols = ['ethbtc', 'ltcbtc']
    print('Creating coin instances and initializing databases...', all_symbols[0:2])
    coin_list = initialize_coins(all_symbols[0:2])
    print(f"Created coins: {coin_list}")
    print('Generating binance websocket api manager...')
    binance_websocket_api_manager = BinanceWebSocketApiManager(exchange="binance.com", output_default="dict")
    binance_websocket_api_manager.create_stream('kline_5m', all_symbols, stream_label="dict", output="dict")
    # TODO: create ticker instances
    # TODO: check if there is a database for each ticker
    # TODO: get kline info of ticker and create/update database
    # TODO: add telegram bot
    # TODO: add plotly traces
    while True:
        if binance_websocket_api_manager.is_manager_stopping():
            exit(0)
        oldest_stream_data_from_stream_buffer = binance_websocket_api_manager.pop_stream_data_from_stream_buffer()
        if oldest_stream_data_from_stream_buffer is False:
            time.sleep(0.1)
        else:
            if oldest_stream_data_from_stream_buffer is not None:
                try:
                    if oldest_stream_data_from_stream_buffer['data']['k']['x']:
                        # TODO: check if price went up more than 10%
                        # TODO: check if volume went up more than 10%
                        print(f"dict: {oldest_stream_data_from_stream_buffer}")
                except KeyError:
                    pass
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

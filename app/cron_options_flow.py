import time 
from benzinga import financial_data
import ujson
import numpy as np
import sqlite3
import asyncio
from datetime import datetime, timedelta
import concurrent.futures
from GetStartEndDate import GetStartEndDate

from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv('BENZINGA_API_KEY')

fin = financial_data.Benzinga(api_key)

stock_con = sqlite3.connect('stocks.db')
stock_cursor = stock_con.cursor()
stock_cursor.execute("SELECT DISTINCT symbol FROM stocks")
stock_symbols = [row[0] for row in stock_cursor.fetchall()]

etf_con = sqlite3.connect('etf.db')
etf_cursor = etf_con.cursor()
etf_cursor.execute("SELECT DISTINCT symbol FROM etfs")
etf_symbols = [row[0] for row in etf_cursor.fetchall()]

start_date_1d, end_date_1d = GetStartEndDate().run()
start_date = start_date_1d.strftime("%Y-%m-%d")
end_date = end_date_1d.strftime("%Y-%m-%d")

#print(start_date,end_date)

def process_page(page):
    try:
        data = fin.options_activity(date_from=start_date, date_to=end_date, page=page, pagesize=1000)
        data = ujson.loads(fin.output(data))['option_activity']

        return data
    except Exception as e:
        print(e)
        return []


# Assuming fin, stock_symbols, and etf_symbols are defined elsewhere
res_list = []

# Adjust max_workers to control the degree of parallelism
max_workers = 6

# Fetch pages concurrently
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_page = {executor.submit(process_page, page): page for page in range(130)}
    for future in concurrent.futures.as_completed(future_to_page):
        page = future_to_page[future]
        try:
            page_list = future.result()
            res_list += page_list
        except Exception as e:
            print(f"Exception occurred: {e}")
            break

# res_list now contains the aggregated results from all pages
#print(res_list)
def custom_key(item):
    return item['time']

res_list = [{key: value for key, value in item.items() if key not in ['description_extended','updated']} for item in res_list]
filtered_list = []
for item in res_list:
    try:
        if item['underlying_price'] != '':
            ticker = item['ticker']
            if ticker == 'BRK.A':
                ticker = 'BRK-A'
            elif ticker == 'BRK.B':
                ticker = 'BRK-B'

            put_call = 'Calls' if item['put_call'] == 'CALL' else 'Puts'

            asset_type = 'stock' if ticker in stock_symbols else ('etf' if ticker in etf_symbols else '')

            item['underlying_type'] = asset_type.lower()
            item['put_call'] = put_call
            item['ticker'] = ticker
            item['price'] = round(float(item['price']), 2)
            item['strike_price'] = round(float(item['strike_price']), 2)
            item['cost_basis'] = round(float(item['cost_basis']), 2)
            item['underlying_price'] = round(float(item['underlying_price']), 2)
            item['option_activity_type'] = item['option_activity_type'].capitalize()
            item['sentiment'] = item['sentiment'].capitalize()
            item['execution_estimate'] = item['execution_estimate'].replace('_', ' ').title()
            item['tradeCount'] = item['trade_count']

            filtered_list.append(item)
    except:
        pass

filtered_list = sorted(filtered_list, key=custom_key, reverse =True)

with open(f"json/options-flow/feed/data.json", 'w') as file:
    ujson.dump(filtered_list, file)

stock_con.close()
etf_con.close()
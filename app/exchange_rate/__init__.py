"""
The main file that will evolve into our trading library
"""
import requests
import json
import csv
import os
import datetime

def main():
    URLS = [("CNY_HKD","https://api.ofx.com/PublicSite.ApiService/SpotRateHistory/3year/HKD/CNY?DecimalPlaces=6&ReportingInterval=daily")
    ,("USD_KRW","https://api.ofx.com/PublicSite.ApiService/SpotRateHistory/3year/USD/KRW?DecimalPlaces=6&ReportingInterval=daily")
    ,("USD_CNY","https://api.ofx.com/PublicSite.ApiService/SpotRateHistory/3year/USD/CNY?DecimalPlaces=6&ReportingInterval=daily")]
    with  requests.Session() as session:
        for cur_pair, url in URLS:
            session.headers = {"Accept":"application/json, text/plain, */*",
                "User-Agent":"Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"}
            rsp = session.get(url)
            jsrsp = json.loads(rsp.text)["HistoricalPoints"]
            for each in jsrsp:
                each['PointInTime'] = datetime.datetime.utcfromtimestamp(each['PointInTime'] / 1000.0).strftime("%Y%m%d")
            base_path = os.path.dirname(__file__)
            with open(os.path.join(base_path,cur_pair + ".csv"),"w") as f:
                cf = csv.DictWriter(f,['PointInTime','InterbankRate','InverseInterbankRate'],dialect=csv.Dialect.delimiter)
                cf.writeheader()
                cf.writerows(jsrsp)

if __name__ == "__main__":
    main()
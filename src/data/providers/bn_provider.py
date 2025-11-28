import requests

headers = {}
# headers['X-MBX-APIKEY'] = <your_api_key>

resp = requests.get('https://api.binance.us/api/v3/historicalTrades?symbol=<symbol>', headers=headers)

print(resp.json())
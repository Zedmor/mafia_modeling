import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    # 'Accept-Encoding': 'gzip, deflate, br',
    'Sec-WebSocket-Version': '13',
    'Origin': 'https://polemicagames.kz',
    'Sec-WebSocket-Extensions': 'permessage-deflate',
    'Sec-WebSocket-Key': 'q8g5vyWtr668yjmB4XIc9Q==',
    'Connection': 'keep-alive, Upgrade',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'websocket',
    'Sec-Fetch-Site': 'cross-site',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'Upgrade': 'websocket',
}

params = {
    'userId': '44330',
    'authKey': 'bJUlGIHfwU0wP3jonAxSTqkrSbbIabb9',
    'intention': 'game_search',
    'EIO': '3',
    'transport': 'websocket',
}

response = requests.get('wss://het1.polemicagame.com:4242/socket.io/', params=params, headers=headers)
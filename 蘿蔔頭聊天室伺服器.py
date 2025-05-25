
import websockets
import json
import os

HOST = '0.0.0.0'
PORT = 12345

USER_FILE = 'users.json'
if not os.path.exists(USER_FILE):
with open(USER_FILE, 'w') as f:
json.dump({}, f)

with open(USER_FILE, 'r') as f:
users = json.load(f)

clients = {} # 暱稱: websocket

def save_users():
with open(USER_FILE, 'w') as f:
json.dump(users, f)

async def handle_client(websocket, path):
nickname = None
try:
async for message in websocket:
request = json.loads(message)

        if request['action'] == 'register':
            nick = request['nickname']
            pw = request['password']
            if nick in users:
                await websocket.send(json.dumps({'status': 'error', 'msg': '暱稱已存在'}))
            elif any(u['password'] == pw for u in users.values()):
                await websocket.send(json.dumps({'status': 'error', 'msg': '密碼已使用'}))
            else:
                users[nick] = {'password': pw}
                save_users()
                await websocket.send(json.dumps({'status': 'ok'}))

        elif request['action'] == 'login':
            nick = request['nickname']
            pw = request['password']
            if users.get(nick, {}).get('password') == pw:
                nickname = nick
                clients[nick] = websocket
                await websocket.send(json.dumps({'status': 'ok'}))
            else:
                await websocket.send(json.dumps({'status': 'error', 'msg': '登入失敗'}))

        elif request['action'] == 'message':
            target = request['to']
            msg = request['msg']
            if target in clients:
                await clients[target].send(json.dumps({
                    'from': nickname,
                    'msg': msg
                }))

        elif request['action'] == 'list':
            await websocket.send(json.dumps({
                'users': list(users.keys())
            }))
finally:
    if nickname and nickname in clients:
        del clients[nickname]
啟動 WebSocket 伺服器

start_server = websockets.serve(handle_client, HOST, PORT)
print(f"WebSocket 伺服器已啟動在 ws://{HOST}:{PORT}")

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

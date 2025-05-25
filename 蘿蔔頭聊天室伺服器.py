import asyncio
import websockets
import json
import os
from typing import Dict, Optional

HOST = '0.0.0.0'
PORT = 12345
USER_FILE = 'users.json'

# 初始化使用者資料檔案
if not os.path.exists(USER_FILE):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False)

with open(USER_FILE, 'r', encoding='utf-8') as f:
    users: Dict[str, Dict[str, str]] = json.load(f)

clients: Dict[str, websockets.WebSocketServerProtocol] = {}  # 暱稱: websocket


def save_users() -> None:
    """同步儲存使用者資料至檔案"""
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


async def handle_client(websocket: websockets.WebSocketServerProtocol, path: str) -> None:
    nickname: Optional[str] = None
    try:
        async for message in websocket:
            try:
                request = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({'status': 'error', 'msg': '訊息格式錯誤'}))
                continue

            action = request.get('action')
            if action == 'register':
                nick = request.get('nickname')
                pw = request.get('password')
                if not nick or not pw:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '暱稱和密碼不可為空'}))
                    continue
                if nick in users:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '暱稱已存在'}))
                elif any(u['password'] == pw for u in users.values()):
                    await websocket.send(json.dumps({'status': 'error', 'msg': '密碼已使用'}))
                else:
                    users[nick] = {'password': pw}
                    save_users()
                    await websocket.send(json.dumps({'status': 'ok'}))

            elif action == 'login':
                nick = request.get('nickname')
                pw = request.get('password')
                if not nick or not pw:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '暱稱和密碼不可為空'}))
                    continue
                if users.get(nick, {}).get('password') == pw:
                    nickname = nick
                    clients[nick] = websocket
                    await websocket.send(json.dumps({'status': 'ok'}))
                    print(f'{nick} 登入成功')
                else:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '登入失敗'}))

            elif action == 'message':
                if not nickname:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '尚未登入'}))
                    continue
                target = request.get('to')
                msg = request.get('msg')
                if not target or not msg:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '目標或訊息不可為空'}))
                    continue
                if target in clients:
                    await clients[target].send(json.dumps({
                        'type': 'message',
                        'from': nickname,
                        'msg': msg
                    }))
                else:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '目標用戶不存在或不在線上'}))

            elif action == 'list':
                await websocket.send(json.dumps({
                    'type': 'list',
                    'users': list(users.keys())
                }))

            else:
                await websocket.send(json.dumps({'status': 'error', 'msg': '未知的動作'}))

    except websockets.exceptions.ConnectionClosed:
        print(f'{nickname if nickname else "一位用戶"} 已斷線')
    except Exception as e:
        print(f'發生錯誤: {e}')
    finally:
        if nickname and nickname in clients:
            del clients[nickname]
            print(f'{nickname} 已從線上清單移除')


async def main():
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"WebSocket 伺服器已啟動在 ws://{HOST}:{PORT}")
        await asyncio.Future()  # 永遠運行


if __name__ == '__main__':
    asyncio.run(main())

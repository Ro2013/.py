import asyncio
import websockets
import json
import sqlite3
import os
from typing import Dict, Optional

HOST = '0.0.0.0'
PORT = 12345
DB_FILE = 'users.db'

# 初始化 SQLite 資料庫
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            nickname TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def register_user(nickname: str, password: str) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (nickname, password) VALUES (?, ?)", (nickname, password))
        conn.commit()
        return "ok"
    except sqlite3.IntegrityError:
        return "exists"
    finally:
        conn.close()

def check_password_used(password: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE password = ?", (password,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def verify_login(nickname: str, password: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE nickname = ?", (nickname,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == password

def list_users() -> list:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT nickname FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

clients: Dict[str, websockets.WebSocketServerProtocol] = {}

async def handle_client(websocket: websockets.WebSocketServerProtocol, path: str):
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
                elif check_password_used(pw):
                    await websocket.send(json.dumps({'status': 'error', 'msg': '密碼已被使用'}))
                else:
                    result = register_user(nick, pw)
                    if result == "exists":
                        await websocket.send(json.dumps({'status': 'error', 'msg': '暱稱已存在'}))
                    else:
                        await websocket.send(json.dumps({'status': 'ok'}))

            elif action == 'login':
                nick = request.get('nickname')
                pw = request.get('password')
                if verify_login(nick, pw):
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
                if target in clients:
                    await clients[target].send(json.dumps({
                        'type': 'message',
                        'from': nickname,
                        'msg': msg
                    }))
                else:
                    await websocket.send(json.dumps({'status': 'error', 'msg': '目標不在線上'}))

            elif action == 'list':
                await websocket.send(json.dumps({'type': 'list', 'users': list_users()}))

            else:
                await websocket.send(json.dumps({'status': 'error', 'msg': '未知動作'}))

    except websockets.exceptions.ConnectionClosed:
        print(f'{nickname or "一位用戶"} 離線')
    finally:
        if nickname and nickname in clients:
            del clients[nickname]

async def main():
    init_db()
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"WebSocket 伺服器已啟動在 ws://{HOST}:{PORT}")
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())

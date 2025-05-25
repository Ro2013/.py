import asyncio
import json
import sqlite3
import os
from aiohttp import web, WSMsgType

DB_FILE = 'users.db'
clients = {}

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

def register_user(nickname, password):
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

def check_password_used(password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE password = ?", (password,))
    result = c.fetchone()
    conn.close()
    return result is not None

def verify_login(nickname, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE nickname = ?", (nickname,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == password

def list_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT nickname FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    nickname = None
    clients_ws = request.app['clients']

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                await ws.send_json({'status': 'error', 'msg': '格式錯誤'})
                continue

            action = data.get('action')

            if action == 'register':
                nickname = data.get('nickname')
                password = data.get('password')
                if not nickname or not password:
                    await ws.send_json({'status': 'error', 'msg': '暱稱和密碼不能空白'})
                elif check_password_used(password):
                    await ws.send_json({'status': 'error', 'msg': '密碼已被使用'})
                else:
                    result = register_user(nickname, password)
                    if result == 'exists':
                        await ws.send_json({'status': 'error', 'msg': '暱稱已存在'})
                    else:
                        await ws.send_json({'status': 'ok'})

            elif action == 'login':
                nickname = data.get('nickname')
                password = data.get('password')
                if verify_login(nickname, password):
                    clients_ws[nickname] = ws
                    await ws.send_json({'status': 'ok'})
                else:
                    await ws.send_json({'status': 'error', 'msg': '登入失敗'})

            elif action == 'message':
                target = data.get('to')
                msg_text = data.get('msg')
                if target in clients_ws:
                    await clients_ws[target].send_json({
                        'type': 'message',
                        'from': nickname,
                        'msg': msg_text
                    })
                else:
                    await ws.send_json({'status': 'error', 'msg': '對方不在線上'})

            elif action == 'list':
                await ws.send_json({'type': 'list', 'users': list_users()})

        elif msg.type == WSMsgType.ERROR:
            print(f'WebSocket error: {ws.exception()}')

    if nickname and nickname in clients_ws:
        del clients_ws[nickname]

    return ws

async def handle_health(request):
    return web.Response(text='OK')

async def main():
    init_db()
    app = web.Application()
    app['clients'] = {}

    app.router.add_get('/', handle_health)
    app.router.add_get('/ws', websocket_handler)

    PORT = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    print(f"伺服器已啟動於 PORT {PORT}")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

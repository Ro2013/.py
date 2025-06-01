import asyncio
import json
import os
from aiohttp import web, WSMsgType
from supabase import create_client, Client

# 🔧 Supabase 連線設定（請改成你自己的）
SUPABASE_URL = "https://jdnwcyoesbwuzxyxtlut.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpkbndjeW9lc2J3dXp4eXh0bHV0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg3NDA0MjgsImV4cCI6MjA2NDMxNjQyOH0.5iMd0VYCyehE3EXUz0O8RsHFKPNxta2iQy_92p-gIhQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

clients = {}

def register_user(nickname, password):
    try:
        result = supabase.table("users").insert({"nickname": nickname, "password": password}).execute()
        if result.status_code == 201:
            return "ok"
        else:
            return "error"
    except Exception:
        return "exists"

def check_password_used(password):
    result = supabase.table("users").select("nickname").eq("password", password).execute()
    return len(result.data) > 0

def verify_login(nickname, password):
    result = supabase.table("users").select("password").eq("nickname", nickname).execute()
    if result.data and result.data[0]["password"] == password:
        return True
    return False

def list_users():
    result = supabase.table("users").select("nickname").execute()
    return [row["nickname"] for row in result.data]

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
                    elif result == 'ok':
                        await ws.send_json({'status': 'ok'})
                    else:
                        await ws.send_json({'status': 'error', 'msg': '註冊失敗'})

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

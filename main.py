import argparse
import asyncio
import json
import traceback
import urllib.request
import emoji
from openai import OpenAI
import sys, os
import random, uuid
sys.path.insert(0, os.path.dirname(__file__))

public_dir = '/public'
cookies_dir = './cookies'

from EdgeGPT.EdgeGPT import Chatbot
from aiohttp import web


def generate_hex_string(length):
    hex_digits = '0123456789ABCDEF'
    return ''.join(random.choice(hex_digits) for _ in range(length))


async def sydney_process_message(user_message, bot_mode, context, _U, KievRPSSecAuth, _RwBf, MUID, locale, enable_gpt4turbo, imageInput, enableSearch, enableFakeCookie, loaded_cookies):
    chatbot = None
    # 设置最大重试次数
    max_retries = 10
    for i in range(max_retries + 1):
        try:
            cookies = loaded_cookies
            if _U:
                cookies = list(filter(lambda d: d.get('name') != '_U', cookies)) + [{"name": "_U", "value": _U}]
            if KievRPSSecAuth:
                cookies = list(filter(lambda d: d.get('name') != 'KievRPSSecAuth', cookies)) + [{"name": "KievRPSSecAuth", "value": KievRPSSecAuth}]
            if _RwBf:
                cookies = list(filter(lambda d: d.get('name') != '_RwBf', cookies)) + [{"name": "_RwBf", "value": _RwBf}]
            if MUID:
                cookies = list(filter(lambda d: d.get('name') != 'MUID', cookies)) + [{"name": "MUID", "value": MUID}]
            SRCHHPGUSR = {
                "creative": "cdxtone=Creative&cdxtoneopts=h3imaginative,gencontentv3,nojbfedge",
                "precise": "cdxtone=Precise&cdxtoneopts=h3precise,clgalileo,gencontentv3,nojbfedge",
                "balanced": "cdxtone=Balanced&cdxtoneopts=galileo,fluxhint,glfluxv13,nojbfedge"
            }
            cookies = list(filter(lambda d: d.get('name') != 'SRCHHPGUSR', cookies)) + [{"name": "SRCHHPGUSR","value": "SRCHLANG=zh-Hans&" + SRCHHPGUSR[bot_mode]}]
            os.environ['image_gen_cookie'] = json.dumps(cookies)
            if enableFakeCookie:
                chatCookie = [{"name": "_U", "value": str(uuid.uuid4()).replace('-','')}] + list(filter(lambda d: d.get('name') not in ['_U', 'KievRPSSecAuth', '_RwBf'], cookies))
            else:
                chatCookie = cookies
            chatbot = await Chatbot.create(cookies=chatCookie, proxy=args.proxy, imageInput=imageInput)
            async for _, response in chatbot.ask_stream(prompt=user_message, conversation_style=bot_mode, raw=True,
                                                        webpage_context=context, search_result=enableSearch, locale=locale,
                                                        enable_gpt4turbo=enable_gpt4turbo):
                yield response
            break
        except Exception as e:
            if (
                "Sorry, you need to login first to access this service." in str(e)
                or "ServiceClient failure for DeepLeo" in str(e)
                or "Cannot retrieve user status" in str(e)
                or "Authentication failed" in str(e)
                or "conversationSignature" in str(e)
                or "Unhandled Exception" in str(e)
            ) and i < max_retries:
                print("Retrying...", i + 1, "attempts.")
                await asyncio.sleep(0.1)
            else:
                if i == max_retries:
                    print("Failed after", max_retries, "attempts.")
                yield {"type": "error", "error": traceback.format_exc()}
        finally:
            if chatbot:
                await chatbot.close()


async def openai_process_message(bot_type, context, user_message):
    # 从环境变量中获取 API 密钥和 URL
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

    # 创建 OpenAI 客户端实例
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 发送请求到 OpenAI API
    response = client.chat.completions.create(
        model=bot_type,
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": user_message}
        ],
        stream=True  # 启用流式响应
    )

    # 处理流式响应
    collected_messages = []
    for chunk in response:
        chunk_message = chunk.choices[0].delta.content
        if chunk_message is not None:
            collected_messages.append(chunk_message)
            yield {"type": "reply", "text": ''.join(collected_messages)}

    # 发送结束信号
    yield {"type": "finished"}


async def http_handler(request):
    file_path = request.path
    if file_path == "/":
        file_path = "/index.html"
    full_path = os.path.realpath('.' + public_dir + file_path)
    if not full_path.startswith(os.path.realpath('.' + public_dir)):
        raise web.HTTPForbidden()
    response = web.FileResponse(full_path)
    response.headers['Cache-Control'] = 'no-store'
    return response

async def get_cookie_files(request):
    try:
        files = os.listdir(cookies_dir)
        cookie_files = [f for f in files if f.endswith('.json')]
        return web.json_response(cookie_files)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def load_cookies(cookie_file):
    full_path = os.path.join(cookies_dir, cookie_file)
    if os.path.isfile(full_path):
        with open(full_path, 'r') as f:
            loaded_cookies = json.load(f)
        print(f"Loaded {full_path}")
    else:
        loaded_cookies = []
        print(f"{full_path} not found")
    return loaded_cookies

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async def monitor():
        while True:
            if ws.closed:
                task.cancel()
                break
            await asyncio.sleep(0.1)

    async def main_process():
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                request = json.loads(msg.data)
                user_message = request['message']
                context = request['context']
                locale = request['locale']

                cookie_file = request['selectedCookieFile']
                loaded_cookies = await load_cookies(cookie_file)

                enable_gpt4turbo = request['enable_gpt4turbo']
                _U = request.get('_U')
                KievRPSSecAuth = request.get('KievRPSSecAuth')
                _RwBf = request.get('_RwBf')
                MUID = request.get('MUID')
                enableSearch = request.get('enableSearch')
                enableFakeCookie = request.get('enableFakeCookie')
                if (request.get('imageInput') is not None) and (len(request.get('imageInput')) > 0):
                    imageInput = request.get('imageInput').split(",")[1]
                else:
                    imageInput = None
                bot_type = request.get("botType", "Sydney")
                bot_mode = request.get("botMode", "creative")
                if bot_type == "Sydney":
                    async for response in sydney_process_message(user_message, bot_mode, context, _U, KievRPSSecAuth, _RwBf, MUID, locale=locale, enable_gpt4turbo=enable_gpt4turbo, imageInput=imageInput, enableSearch=enableSearch, enableFakeCookie=enableFakeCookie, loaded_cookies=loaded_cookies):
                        await ws.send_json(response)
                else:
                    async for response in openai_process_message(bot_type, context, user_message):
                        await ws.send_json(response)

    task = asyncio.ensure_future(main_process())
    monitor_task = asyncio.ensure_future(monitor())
    done, pending = await asyncio.wait([task, monitor_task], return_when=asyncio.FIRST_COMPLETED)

    for task in pending:
        task.cancel()

    return ws


async def main(host, port):
    app = web.Application()
    app.router.add_get('/ws/', websocket_handler)
    app.router.add_get('/cookie-files', get_cookie_files)  # 添加新的路由
    app.router.add_get('/{tail:.*}', http_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Go to http://{host}:{port} to start chatting!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-H", help="host:port for the server", default="localhost:65432")
    parser.add_argument("--proxy", "-p", help='proxy address like "http://localhost:7890"',
                        default=urllib.request.getproxies().get('https'))
    args = parser.parse_args()
    print(f"Proxy used: {args.proxy}")

    host, port = args.host.split(":")
    port = int(port)

    try:
        asyncio.run(main(host, port))
    except KeyboardInterrupt:
        pass

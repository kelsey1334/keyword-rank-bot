{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import logging\
from telegram import Update\
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes\
import aiohttp\
import asyncio\
from queue import Queue\
\
import os\
API_USERNAME = os.getenv("kelsey@procons.one")\
API_PASSWORD = os.getenv("ce924c4b04d101da")\
BOT_TOKEN = os.getenv("8121072039:AAHcjhIbwffx6p5o8vyPqH2hzDT8gFqJ3wA")\
\
job_queue = Queue()\
logging.basicConfig(level=logging.INFO)\
\
async def call_dataforseo_api(keyword: str):\
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"\
    payload = \{\
        "keyword": keyword,\
        "location_code": 2376,\
        "language_code": "vi",\
        "depth": 10\
    \}\
\
    async with aiohttp.ClientSession() as session:\
        async with session.post(url, json=[payload], auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:\
            data = await resp.json()\
            try:\
                items = data['tasks'][0]['result'][0]['items']\
                domains = [item['domain'] for item in items if 'domain' in item]\
                return domains\
            except Exception as e:\
                return [f"L\uc0\u7895 i khi l\u7845 y d\u7919  li\u7879 u: \{str(e)\}"]\
\
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    keyword = ' '.join(context.args)\
    if not keyword:\
        await update.message.reply_text("Vui l\'f2ng nh\uc0\u7853 p t\u7915  kh\'f3a sau l\u7879 nh /search")\
        return\
\
    await update.message.reply_text("\uc0\u272 ang x\u7917  l\'fd...")\
\
    job_queue.put((update, keyword))\
\
async def worker():\
    while True:\
        if not job_queue.empty():\
            update, keyword = job_queue.get()\
            domains = await call_dataforseo_api(keyword)\
            msg = "\\n".join(domains[:10]) if domains else "Kh\'f4ng t\'ecm th\uc0\u7845 y k\u7871 t qu\u7843 ."\
            await update.message.reply_text(f"Top 10 domain cho t\uc0\u7915  kh\'f3a \\"\{keyword\}\\":\\n\{msg\}")\
        await asyncio.sleep(1)\
\
async def start_bot():\
    app = ApplicationBuilder().token(BOT_TOKEN).build()\
    app.add_handler(CommandHandler("search", search))\
    asyncio.create_task(worker())\
    await app.run_polling()\
\
if __name__ == '__main__':\
    asyncio.run(start_bot())}
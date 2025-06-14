import os
import logging
import asyncio
from queue import Queue

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

# Lấy thông tin từ biến môi trường
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")

# Kiểm tra biến môi trường có đầy đủ chưa
if not BOT_TOKEN or not API_USERNAME or not API_PASSWORD:
    raise ValueError("Thiếu BOT_TOKEN, API_USERNAME hoặc API_PASSWORD trong biến môi trường.")

# Hàng đợi để xử lý keyword
job_queue = Queue()

# Logging để debug
logging.basicConfig(level=logging.INFO)

# Gọi API của DataForSEO để lấy top domain
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = {
        "keyword": keyword,
        "location_code": 2376,  # Vietnam
        "language_code": "vi",
        "depth": 10
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=[payload], auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:
            data = await resp.json()
            try:
                items = data['tasks'][0]['result'][0]['items']
                domains = [item['domain'] for item in items if 'domain' in item]
                return domains
            except Exception as e:
                return [f"Lỗi khi lấy dữ liệu: {str(e)}"]

# Khi người dùng nhập /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("Vui lòng nhập từ khóa sau lệnh /search")
        return

    await update.message.reply_text("Đang xử lý...")
    job_queue.put((update, keyword))

# Worker xử lý hàng đợi
async def worker():
    while True:
        if not job_queue.empty():
            update, keyword = job_queue.get()
            domains = await call_dataforseo_api(keyword)
            msg = "\n".join(domains[:10]) if domains else "Không tìm thấy kết quả."
            await update.message.reply_text(f"Top 10 domain cho từ khóa \"{keyword}\":\n{msg}")
        await asyncio.sleep(1)

# Hàm khởi chạy bot
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("search", search))

    # Chạy worker song song
    asyncio.create_task(worker())

    await app.run_polling()

# Entry point
if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(start_bot())

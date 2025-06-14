import logging
import os
import aiohttp
import asyncio
from queue import Queue
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Lấy biến môi trường từ Railway
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Hàng đợi
job_queue = Queue()

# Gọi API DataForSEO
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = {
        "keyword": keyword,
        "location_code": 2376,
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

# Lệnh /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("Vui lòng nhập từ khóa sau lệnh /search")
        return

    await update.message.reply_text(f"Vui lòng đợi, chúng tôi đang kiểm tra thứ hạng từ khóa: {keyword}")
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

# Khởi động bot
async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("search", search))

    # Khởi chạy worker nền
    asyncio.create_task(worker())

    print("Bot đang chạy...")
    await app.run_polling()

# Gọi bot
if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except RuntimeError as e:
        # Fix lỗi Railway đã có sẵn event loop
        if "This event loop is already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(start_bot())
            loop.run_forever()
        else:
            raise

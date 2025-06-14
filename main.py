import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp
import asyncio
from queue import Queue

# Thông tin xác thực
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Hàng đợi xử lý
job_queue = Queue()

# Gọi API từ DataForSEO
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = {
        "keyword": keyword,
        "location_code": 2376,  # Việt Nam
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
    await update.message.reply_text("Đang xử lý...")
    job_queue.put((update, keyword))

# Worker xử lý hàng đợi
async def worker(application):
    while True:
        if not job_queue.empty():
            update, keyword = job_queue.get()
            domains = await call_dataforseo_api(keyword)
            msg = "\n".join(domains[:10]) if domains else "Không tìm thấy kết quả."
            try:
                await update.message.reply_text(f"Top 10 domain cho từ khóa \"{keyword}\":\n{msg}")
            except Exception as e:
                logging.warning(f"Gửi tin nhắn lỗi: {e}")
        await asyncio.sleep(1)

# Hàm khởi chạy bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("search", search))
    asyncio.create_task(worker(app))
    print("Bot đang chạy...")
    await app.run_polling()

# Không dùng asyncio.run() nếu Railway đã có event loop
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # <- fix lỗi lặp event loop
    asyncio.get_event_loop().create_task(setup())
    asyncio.get_event_loop().run_forever()

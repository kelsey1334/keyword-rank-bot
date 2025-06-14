import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp
import asyncio
from queue import Queue

# Thông tin xác thực từ biến môi trường
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Hàng đợi xử lý từ người dùng
job_queue = Queue()

# Gọi API DataForSEO để lấy kết quả tìm kiếm
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = {
        "keyword": keyword,
        "location_code": 1028581,  # Việt Nam
        "language_code": "vi",
        "depth": 10
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=[payload], auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:
            data = await resp.json()
            try:
                items = data['tasks'][0]['result'][0]['items']
                domains = [item['domain'] for item in items if item.get("type") == "organic" and "domain" in item]
                return domains
            except Exception as e:
                logging.error(f"Lỗi xử lý dữ liệu: {e}")
                return [f"Lỗi khi lấy dữ liệu: {str(e)}"]

# Lệnh /start: chào mừng và hướng dẫn
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 Xin chào! Tôi là bot hỗ trợ kiểm tra thứ hạng từ khóa trên Google.\n\n"
        "👉 Để kiểm tra thứ hạng, hãy dùng lệnh:\n"
        "/search từ_khóa\n"
        "Ví dụ: /search go88\n\n"
        "📌 Tôi sẽ trả về top 10 kết quả tìm kiếm organic tại Việt Nam."
    )
    await update.message.reply_text(message)

# Lệnh /getidtele: trả về ID người dùng
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 ID Telegram của bạn là: {user_id}")

# Lệnh /search: đưa vào hàng đợi xử lý
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /search\nVí dụ: /search go88")
        return
    await update.message.reply_text("⏳ Đang xử lý, vui lòng chờ giây lát...")
    job_queue.put((update, keyword))

# Xử lý hàng đợi, gửi kết quả về người dùng
async def worker(application):
    while True:
        if not job_queue.empty():
            update, keyword = job_queue.get()
            domains = await call_dataforseo_api(keyword)
            if domains:
                msg = "\n".join([f"🔹 Top {i+1}: {domain}" for i, domain in enumerate(domains[:10])])
            else:
                msg = "❌ Không tìm thấy kết quả."
            try:
                await update.message.reply_text(f"📊 Top 10 domain cho từ khóa \"{keyword}\":\n{msg}")
            except Exception as e:
                logging.warning(f"Lỗi gửi tin nhắn: {e}")
        await asyncio.sleep(1)

# Cài đặt và khởi chạy bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("search", search))
    asyncio.create_task(worker(app))
    print("🤖 Bot đang chạy...")
    await app.run_polling()

# Khởi động chương trình (tương thích với Railway)
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().create_task(setup())
    asyncio.get_event_loop().run_forever()

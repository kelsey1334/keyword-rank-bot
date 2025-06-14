import logging
import os
import asyncio
from datetime import time
from queue import Queue

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
)
import aiohttp
import nest_asyncio

# Biến môi trường
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")  # Telegram ID cá nhân để nhận thông báo 8h sáng

# Logging
logging.basicConfig(level=logging.INFO)
job_queue = Queue()

# Gọi API DataForSEO
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = {
        "keyword": keyword,
        "location_code": 1028581,
        "language_code": "vi",
        "depth": 10
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=[payload], auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:
            data = await resp.json()
            try:
                items = data['tasks'][0]['result'][0]['items']
                domains = [item['domain'] for item in items if item.get('type') == 'organic' and 'domain' in item]
                return domains
            except Exception as e:
                return [f"Lỗi khi lấy dữ liệu: {str(e)}"]

# /search command
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("Vui lòng nhập từ khóa sau lệnh /search")
        return
    await update.message.reply_text("Đang xử lý...")
    job_queue.put((update, keyword))

# /getidtele command
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"ID của telegram của bạn là: {user_id}")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 Xin chào! Chào mừng bạn đến với bot kiểm tra thứ hạng Google!\n\n"
        "💡 Hãy bấm: `/search từ_khóa` để kiểm tra thứ hạng website.\n"
        "📌 Ví dụ: `/search go88`\n\n"
        "📎 Một số lệnh hữu ích:\n"
        "• /getidtele - Lấy ID Telegram\n"
        "• /tygia - Xem tỷ giá 100 Baht\n\n"
        "🚀 Chúc bạn một ngày hiệu quả!"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

# Worker xử lý hàng đợi
async def worker(application):
    while True:
        if not job_queue.empty():
            update, keyword = job_queue.get()
            domains = await call_dataforseo_api(keyword)
            if domains:
                msg = "\n".join([f"Top {i+1}: {domain}" for i, domain in enumerate(domains[:10])])
            else:
                msg = "Không tìm thấy kết quả."
            try:
                await update.message.reply_text(f"🔍 Kết quả cho từ khóa \"{keyword}\":\n{msg}")
            except Exception as e:
                logging.warning(f"Gửi tin nhắn lỗi: {e}")
        await asyncio.sleep(1)

# API thời tiết Bangkok
async def get_weather_bangkok():
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Bangkok&appid={WEATHER_API_KEY}&units=metric&lang=vi"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            temp = data['main']['temp']
            desc = data['weather'][0]['description'].capitalize()
            return f"🌤 Thời tiết Bangkok hôm nay: {desc}, nhiệt độ {temp}°C"

# API tỷ giá
async def get_exchange_rate():
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/THB"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            try:
                rate = data['conversion_rates']['VND']
                return f"💱 100 Baht = {round(rate * 100):,} VND"
            except:
                return "Không lấy được tỷ giá."

# /tygia command
async def tygia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await get_exchange_rate()
    await update.message.reply_text(text)

# Gửi thông báo sáng hàng ngày
async def morning_message(context: ContextTypes.DEFAULT_TYPE):
    weather = await get_weather_bangkok()
    exchange = await get_exchange_rate()
    quote = "🌱 Mỗi ngày là một cơ hội để tốt hơn hôm qua."
    food = "🥣 Gợi ý món sáng: Cháo thịt bằm hoặc mì trộn cay Thái."
    message = f"{weather}\n\n{food}\n\n{quote}\n\n{exchange}"
    try:
        await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message)
    except Exception as e:
        logging.warning(f"Gửi tin nhắn sáng thất bại: {e}")

# Setup bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Thiết lập JobQueue nếu chưa có
    if not app.job_queue:
        app.job_queue = JobQueue()
        app.job_queue.set_application(app)
        app.job_queue.start()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("tygia", tygia))

    # Worker queue
    asyncio.create_task(worker(app))

    # Gửi thông báo sáng lúc 8h
    app.job_queue.run_daily(morning_message, time=time(hour=8, minute=0))

    print("Bot đang chạy...")
    await app.run_polling()

# Chạy bot
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(setup())

import logging
import os
import asyncio
from queue import Queue
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Thông tin xác thực từ biến môi trường
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Hàng đợi xử lý
job_queue = Queue()

# Gọi API DataForSEO: Lấy top 10 domain
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": keyword,
        "location_code": 1028581,
        "language_code": "vi",
        "depth": 10
    }]

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:
            data = await resp.json()
            try:
                items = data['tasks'][0]['result'][0]['items']
                domains = [item['domain'] for item in items if item.get("type") == "organic" and "domain" in item]
                return domains
            except Exception as e:
                logging.error(f"Lỗi xử lý dữ liệu: {e}")
                return [f"Lỗi khi lấy dữ liệu: {str(e)}"]

# Gọi API intent và từ khoá phụ
async def call_search_intent_api(keyword: str):
    intent_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/search_intent/live"
    related_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/related_keywords/live"

    intent_payload = [{
        "language_code": "vi",
        "keywords": [keyword]
    }]

    related_payload = [{
        "language_code": "vi",
        "location_code": 1028581,
        "keyword": keyword,
        "limit": 3
    }]

    async with aiohttp.ClientSession() as session:
        # Search intent
        async with session.post(intent_url, json=intent_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as r1:
            intent_data = await r1.json()

        # Related keywords
        async with session.post(related_url, json=related_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as r2:
            related_data = await r2.json()

    try:
        intent = intent_data["tasks"][0]["result"][0]["search_intent_info"]["main_intent"]
    except:
        intent = None
    try:
        kws = [item["keyword"] for item in related_data["tasks"][0]["result"]][:3]
    except:
        kws = []

    return intent, kws

# Lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Chào bạn! Tôi là bot hỗ trợ kiểm tra thứ hạng và intent từ khóa trên Google.\n\n"
        "👉 Dùng lệnh:\n"
        "/search từ_khóa – Xem top 10 domain\n"
        "/intent từ_khóa – Phân tích intent + từ khoá phụ\n"
        "/getidtele – Xem ID Telegram"
    )
    await update.message.reply_text(msg)

# Lệnh /getidtele
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 ID Telegram của bạn là: {update.effective_user.id}")

# Lệnh /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /search\nVí dụ: /search go88")
        return
    await update.message.reply_text("⏳ Đang xử lý...")
    job_queue.put((update, 'search', keyword))

# Lệnh /intent
async def intent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /intent\nVí dụ: /intent giày thể thao")
        return
    await update.message.reply_text("⏳ Đang phân tích intent...")
    job_queue.put((update, 'intent', keyword))

# Worker xử lý hàng đợi
async def worker():
    while True:
        if not job_queue.empty():
            update, action, keyword = job_queue.get()
            try:
                if action == 'search':
                    domains = await call_dataforseo_api(keyword)
                    if domains:
                        msg = "\n".join([f"🔹 Top {i+1}: {domain}" for i, domain in enumerate(domains[:10])])
                        await update.message.reply_text(f"📊 Top 10 domain cho từ khóa \"{keyword}\":\n{msg}")
                    else:
                        await update.message.reply_text("❌ Không tìm thấy kết quả.")
                elif action == 'intent':
                    intent_type, related_kws = await call_search_intent_api(keyword)
                    if not intent_type:
                        await update.message.reply_text("❌ Không xác định được intent.")
                    else:
                        msg = f"🔍 Intent: `{intent_type}`\n\n"
                        if related_kws:
                            msg += "🧩 Từ khoá phụ:\n" + '\n'.join([f"- {kw}" for kw in related_kws])
                        await update.message.reply_text(msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Lỗi trong worker: {e}")
                await update.message.reply_text("❗ Đã xảy ra lỗi khi xử lý yêu cầu.")
        await asyncio.sleep(1)

# Cấu hình bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("intent", intent))
    asyncio.create_task(worker())
    print("🤖 Bot đang chạy...")
    await app.run_polling()

# Khởi động
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(setup())

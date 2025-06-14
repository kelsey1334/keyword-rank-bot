import logging
import os
import asyncio
from queue import Queue
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

# Lấy thông tin từ biến môi trường
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO)

# Hàng đợi xử lý từ người dùng
job_queue = Queue()

# Gọi API DataForSEO để lấy domain top 10 cho từ khóa
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": keyword,
        "location_code": 1028581,  # Việt Nam
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

# Gọi API intent và related keywords
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
        intent_task = session.post(intent_url, json=intent_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD))
        related_task = session.post(related_url, json=related_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD))
        intent_resp, related_resp = await asyncio.gather(intent_task, related_task)

        intent_data = await intent_resp.json()
        related_data = await related_resp.json()

        # Intent
        try:
            result = intent_data["tasks"][0]["result"][0]["search_intent_info"]
            intent_type = result.get("main_intent", "Không xác định")
        except:
            intent_type = None

        # Related keywords
        related_keywords = []
        try:
            for kw in related_data["tasks"][0]["result"]:
                txt = kw.get("keyword")
                if txt and txt != keyword:
                    related_keywords.append(txt)
                if len(related_keywords) >= 3:
                    break
        except:
            pass

        return intent_type, related_keywords

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 Xin chào! Tôi là bot hỗ trợ kiểm tra thứ hạng từ khóa trên Google.\n\n"
        "👉 Để kiểm tra thứ hạng, hãy dùng lệnh:\n"
        "/search từ_khóa\n"
        "Ví dụ: /search go88\n\n"
        "🔍 Để phân tích intent và từ khoá phụ: /intent từ_khóa"
    )
    await update.message.reply_text(message)

# /getidtele
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 ID Telegram của bạn là: {user_id}")

# /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /search\nVí dụ: /search go88")
        return
    await update.message.reply_text("⏳ Đang xử lý, vui lòng chờ giây lát...")
    job_queue.put((update, keyword))

# Hàng đợi xử lý tìm kiếm
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

# /intent
async def intent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Dùng: /intent từ_khóa (ví dụ: /intent máy lạnh mini)")
        return

    await update.message.reply_text("🧠 Đang phân tích intent và từ khoá phụ…")

    intent_type, related_keywords = await call_search_intent_api(keyword)

    if not intent_type:
        await update.message.reply_text("❌ Không định được intent. Có thể API bị lỗi.")
        return

    msg = f"🔸 *Search Intent:* `{intent_type}`"
    if related_keywords:
        msg += "\n\n🧩 *Từ khoá phụ đề xuất:*"
        msg += "".join(f"\n- {kw}" for kw in related_keywords)

    await update.message.reply_text(msg, parse_mode="Markdown")

# Cài đặt và khởi chạy bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("intent", intent))
    asyncio.create_task(worker(app))
    print("🤖 Bot đang chạy...")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().create_task(setup())
    asyncio.get_event_loop().run_forever()

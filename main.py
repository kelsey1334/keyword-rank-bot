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

# Gọi API SERP của DataForSEO để lấy top 10 domain
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
                logging.error(f"Lỗi xử lý dữ liệu SERP: {e}")
                return [f"Lỗi khi lấy dữ liệu: {str(e)}"]

# Gọi API Search Intent + Từ khoá phụ
async def call_search_intent_api(keyword: str):
    intent_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/search_intent/live"
    related_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/related_keywords/live"

    intent_payload = {
        "keyword": keyword,
        "language_code": "vi",
        "location_code": 1028581
    }

    related_payload = {
        "keyword": keyword,
        "language_code": "vi",
        "location_code": 1028581
    }

    async with aiohttp.ClientSession() as session:
        try:
            intent_task = session.post(intent_url, json=intent_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD))
            related_task = session.post(related_url, json=related_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD))

            intent_resp, related_resp = await asyncio.gather(intent_task, related_task)

            intent_data = await intent_resp.json()
            related_data = await related_resp.json()

            # Ý định tìm kiếm
            intent_type = "Không xác định"
            domains = []
            try:
                result = intent_data["tasks"][0]["result"][0]
                intent_type = result.get("search_intent", "Không xác định")
                serp_snapshots = result.get("serp_snapshots", [])
                for snap in serp_snapshots:
                    domain = snap.get("domain")
                    if domain and domain not in domains:
                        domains.append(domain)
                    if len(domains) >= 5:
                        break
            except Exception as e:
                logging.warning(f"Lỗi xử lý intent: {e}")

            # Từ khoá phụ
            related_keywords = []
            try:
                results = related_data["tasks"][0]["result"]
                for kw in results:
                    keyword_text = kw.get("keyword")
                    if keyword_text and keyword_text != keyword:
                        related_keywords.append(keyword_text)
                    if len(related_keywords) >= 3:
                        break
            except Exception as e:
                logging.warning(f"Lỗi xử lý từ khoá phụ: {e}")

            return intent_type, domains, related_keywords

        except Exception as e:
            logging.error(f"Lỗi gọi API: {e}")
            return None, [], []

# /start: chào mừng
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 Xin chào! Tôi là bot kiểm tra thứ hạng từ khoá trên Google.\n\n"
        "👉 Lệnh khả dụng:\n"
        "/search từ_khóa – Top 10 website\n"
        "/intent từ_khóa – Phân tích ý định + từ khoá phụ\n"
        "/getidtele – Xem Telegram ID"
    )
    await update.message.reply_text(message)

# /getidtele: trả ID
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 ID Telegram của bạn là: {user_id}")

# /search: vào hàng đợi
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khoá sau lệnh /search\nVí dụ: /search go88")
        return
    await update.message.reply_text("⏳ Đang xử lý, vui lòng chờ giây lát...")
    job_queue.put((update, keyword))

# Xử lý hàng đợi
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
                await update.message.reply_text(f"📊 Top 10 domain cho từ khoá \"{keyword}\":\n{msg}")
            except Exception as e:
                logging.warning(f"Lỗi gửi tin nhắn: {e}")
        await asyncio.sleep(1)

# /intent: phân tích search intent + từ khoá phụ
async def intent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khoá sau lệnh /intent\nVí dụ: /intent máy lạnh mini")
        return

    await update.message.reply_text("🔍 Đang phân tích ý định và từ khoá liên quan...")

    intent_type, domains, related_keywords = await call_search_intent_api(keyword)

    if not intent_type:
        await update.message.reply_text("❌ Không thể phân tích từ khoá này.")
        return

    msg = f"""🧠 *Phân tích từ khoá:* _{keyword}_

🔸 *Search Intent:* `{intent_type}`

🔹 *Domain phổ biến:*
""" + "\n".join([f"{i+1}. {domain}" for i, domain in enumerate(domains)])

    if related_keywords:
        msg += "\n\n🧩 *Từ khoá phụ đề xuất:*\n"
        msg += "\n".join([f"- {kw}" for kw in related_keywords])

    await update.message.reply_text(msg, parse_mode="Markdown")

# Khởi chạy bot
async def setup():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("intent", intent))
    asyncio.create_task(worker(app))
    print("🤖 Bot đang chạy...")
    await app.run_polling()

# Chạy main
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().create_task(setup())
    asyncio.get_event_loop().run_forever()

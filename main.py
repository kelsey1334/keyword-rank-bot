import logging
import os
import asyncio
from queue import Queue
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Thông tin xác thực từ biến môi trường
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Kiểm tra xem các biến môi trường đã được đặt chưa
if not all([API_USERNAME, API_PASSWORD, BOT_TOKEN]):
    logging.error("Lỗi: Vui lòng đặt các biến môi trường API_USERNAME, API_PASSWORD, và BOT_TOKEN.")
    exit()

# Hàng đợi xử lý
job_queue = Queue()

# Gọi API DataForSEO: Lấy top 10 domain
async def call_dataforseo_api(keyword: str):
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": keyword,
        "location_code": 1028581, # Vietnam
        "language_code": "vi",
        "depth": 10
    }]

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as resp:
                resp.raise_for_status() # Sẽ báo lỗi nếu status code là 4xx hoặc 5xx
                data = await resp.json()
                
                # Kiểm tra cấu trúc dữ liệu trả về
                if data and data.get('tasks') and data['tasks'][0].get('result'):
                    items = data['tasks'][0]['result'][0].get('items', [])
                    domains = [item['domain'] for item in items if item.get("type") == "organic" and "domain" in item]
                    return domains
                else:
                    logging.warning(f"Cấu trúc dữ liệu không như mong đợi từ DataForSEO cho từ khóa: {keyword}")
                    return []
        except aiohttp.ClientError as e:
            logging.error(f"Lỗi khi gọi API DataForSEO (SERP): {e}")
            return [f"Lỗi khi gọi API: {str(e)}"]
        except Exception as e:
            logging.error(f"Lỗi không xác định khi xử lý dữ liệu SERP: {e}")
            return [f"Lỗi khi xử lý dữ liệu: {str(e)}"]

# >>>>> PHẦN CODE ĐÃ ĐƯỢC SỬA LẠI <<<<<
# Gọi API intent và từ khoá phụ
async def call_search_intent_api(keyword: str):
    intent_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/search_intent/live"
    related_url = "https://api.dataforseo.com/v3/dataforseo_labs/google/related_keywords/live"

    # Payload cho Search Intent, ĐÃ THÊM location_code
    intent_payload = [{
        "language_code": "vi",
        "location_code": 1028581,
        "keywords": [keyword]
    }]

    # Payload cho Related Keywords
    related_payload = [{
        "language_code": "vi",
        "location_code": 1028581,
        "keyword": keyword,
        "limit": 3
    }]
    
    intent = None
    kws = []

    try:
        async with aiohttp.ClientSession() as session:
            # GỌI API SEARCH INTENT
            async with session.post(intent_url, json=intent_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as r1:
                r1.raise_for_status()
                intent_data = await r1.json()

            # GỌI API RELATED KEYWORDS
            async with session.post(related_url, json=related_payload, auth=aiohttp.BasicAuth(API_USERNAME, API_PASSWORD)) as r2:
                r2.raise_for_status()
                related_data = await r2.json()

        # XỬ LÝ KẾT QUẢ INTENT (AN TOÀN HƠN)
        if intent_data.get("tasks") and intent_data["tasks"][0].get("result"):
            result_list = intent_data["tasks"][0]["result"]
            if result_list:
                result_item = result_list[0]
                if result_item and "search_intent_info" in result_item:
                    intent = result_item["search_intent_info"].get("main_intent")

        # XỬ LÝ KẾT QUẢ RELATED KEYWORDS (AN TOÀN HƠN)
        if related_data.get("tasks") and related_data["tasks"][0].get("result"):
            kws = [item["keyword"] for item in related_data["tasks"][0]["result"]][:3]

    except aiohttp.ClientError as e:
        logging.error(f"Lỗi khi gọi API Labs: {e}")
    except (IndexError, KeyError, TypeError) as e:
        logging.error(f"Lỗi khi phân tích dữ liệu từ API Labs: {e}")
    
    return intent, kws

# Lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Chào bạn! Tôi là bot hỗ trợ kiểm tra thứ hạng và intent từ khóa trên Google.\n\n"
        "👉 Dùng lệnh:\n"
        "/search [từ_khóa] – Xem top 10 domain\n"
        "/intent [từ_khóa] – Phân tích intent + từ khoá phụ\n"
        "/getidtele – Xem ID Telegram"
    )
    await update.message.reply_text(msg)

# Lệnh /getidtele
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 ID Telegram của bạn là: `{update.effective_user.id}`", parse_mode="Markdown")

# Lệnh /search
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /search\nVí dụ: /search go88")
        return
    await update.message.reply_text(f"⏳ Đang tìm top 10 cho từ khóa \"{keyword}\"...")
    job_queue.put((update, 'search', keyword))

# Lệnh /intent
async def intent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = ' '.join(context.args)
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa sau lệnh /intent\nVí dụ: /intent giày thể thao")
        return
    await update.message.reply_text(f"⏳ Đang phân tích intent cho từ khóa \"{keyword}\"...")
    job_queue.put((update, 'intent', keyword))

# Worker xử lý hàng đợi
async def worker():
    while True:
        if not job_queue.empty():
            update, action, keyword = job_queue.get()
            chat_id = update.effective_chat.id
            logging.info(f"Processing job '{action}' for keyword '{keyword}' in chat {chat_id}")
            try:
                if action == 'search':
                    domains = await call_dataforseo_api(keyword)
                    if domains:
                        # Kiểm tra xem có phải là thông báo lỗi từ API không
                        if isinstance(domains[0], str) and domains[0].startswith("Lỗi"):
                            msg = f"❌ Đã xảy ra lỗi khi lấy dữ liệu cho \"{keyword}\":\n{domains[0]}"
                        else:
                            msg_list = "\n".join([f"🔹 Top {i+1}: {domain}" for i, domain in enumerate(domains[:10])])
                            msg = f"📊 Top 10 domain cho từ khóa \"{keyword}\":\n{msg_list}"
                        await update.message.reply_text(msg)
                    else:
                        await update.message.reply_text(f"❌ Không tìm thấy kết quả xếp hạng cho từ khóa \"{keyword}\".")
                
                elif action == 'intent':
                    intent_type, related_kws = await call_search_intent_api(keyword)
                    if not intent_type:
                        await update.message.reply_text(f"❌ Không xác định được intent cho từ khóa \"{keyword}\". API có thể không hỗ trợ hoặc từ khóa không rõ ràng.")
                    else:
                        msg = f"**Từ khóa:** `{keyword}`\n\n"
                        msg += f"🔍 **Intent chính:** `{intent_type}`\n\n"
                        if related_kws:
                            msg += "🧩 **Gợi ý từ khoá phụ:**\n" + '\n'.join([f"- `{kw}`" for kw in related_kws])
                        else:
                            msg += "🧩 _Không tìm thấy từ khoá phụ._"
                        await update.message.reply_text(msg, parse_mode="Markdown")

            except Exception as e:
                logging.error(f"Lỗi nghiêm trọng trong worker khi xử lý '{keyword}': {e}", exc_info=True)
                await update.message.reply_text("❗ Đã xảy ra lỗi hệ thống khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.")
            finally:
                job_queue.task_done()
        await asyncio.sleep(1)

# Cấu hình và chạy bot
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getidtele", get_id))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("intent", intent))
    
    # Khởi chạy worker như một background task
    asyncio.create_task(worker())
    
    print("🤖 Bot đang chạy...")
    logging.info("Bot started successfully.")
    
    # Chạy bot
    await app.run_polling()

# Khởi động
if __name__ == "__main__":
    nest_asyncio.apply()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot is shutting down.")

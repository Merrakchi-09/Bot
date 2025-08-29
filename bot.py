from flask import Flask, request
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
from bs4 import BeautifulSoup
import urllib.parse
import os

# ===== إعدادات =====
BOT_TOKEN = "8445493492:AAG8AWp3pW0sPe_eWMG1ZUzT6SNpfBIOMQk"
AMAZON_TAG = "thehorizon-20"
ALIEXPRESS_TRACKING_ID = "Ewsa6Ro"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_queries = {}

# ===== Flask =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive on Render!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

# ===== دوال البوت =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك! أرسل اسم المنتج الذي تريد البحث عنه.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("❌ الرجاء إرسال اسم المنتج بشكل صحيح.")
        return

    user_id = update.message.from_user.id
    user_queries[user_id] = query

    buttons = [
        [InlineKeyboardButton("🔵 أمازون", callback_data="amazon")],
        [InlineKeyboardButton("🔴 علي إكسبريس", callback_data="aliexpress")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("🔍 اختر المنصة للبحث فيها:", reply_markup=markup)

async def handle_platform_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    platform = query.data
    user_id = query.from_user.id
    product = user_queries.get(user_id)

    if not product:
        await query.edit_message_text("❌ لم أتمكن من الحصول على اسم المنتج، يرجى إعادة الإرسال.")
        return

    await query.edit_message_text(f"⏳ جاري البحث عن \"{product}\" في {platform.capitalize()}...")

    if platform == "amazon":
        result = search_amazon(product)
    else:
        result = search_aliexpress(product)

    if not result:
        await query.message.reply_text("❌ لم أجد نتائج للمنتج الذي طلبته.")
        return

    title, link = result
    response = f"✅ <b>{title}</b>\n🔗 <a href=\"{link}\">رابط المنتج</a>"
    await query.message.reply_html(response)

# ===== البحث في أمازون =====
def search_amazon(query: str):
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    encoded_query = urllib.parse.quote_plus(query.strip())
    search_url = f"https://www.amazon.com/s?k={encoded_query}"
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return f"رابط البحث عن \"{query}\" في أمازون", f"{search_url}&tag={AMAZON_TAG}"
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.select('div[data-component-type="s-search-result"]')
        for item in results:
            title_tag = item.select_one("h2 a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            raw_link = title_tag.get("href")
            if raw_link and "/dp/" in raw_link:
                asin = raw_link.split("/dp/")[1].split("/")[0].split("?")[0]
                affiliate_link = f"https://www.amazon.com/dp/{asin}?tag={AMAZON_TAG}"
                return title, affiliate_link
        return f"رابط البحث عن \"{query}\" في أمازون", f"{search_url}&tag={AMAZON_TAG}"
    except Exception as e:
        logger.error(f"خطأ أثناء البحث في أمازون: {e}")
        return None

# ===== البحث في علي إكسبريس =====
def search_aliexpress(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    base_url = "https://www.aliexpress.com/wholesale"
    params = {"SearchText": query}
    search_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        product_link = soup.select_one('a[href*="/item/"]')
        if product_link:
            title = product_link.get_text(strip=True)
            link = product_link['href']
            if link.startswith("//"):
                link = "https:" + link
            elif link.startswith("/"):
                link = "https://www.aliexpress.com" + link
            sep = "&" if "?" in link else "?"
            link += f"{sep}aff_fcid={ALIEXPRESS_TRACKING_ID}"
            return title, link
        search_url += f"&aff_fcid={ALIEXPRESS_TRACKING_ID}"
        return "رابط البحث في علي إكسبريس", search_url
    except Exception as e:
        logger.error(f"خطأ في البحث بعلي إكسبريس: {e}")
        return None

# ===== تشغيل البوت =====
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_platform_selection))

if __name__ == "__main__":
    RENDER_URL = os.getenv("RENDER_URL", "https://your-app-name.onrender.com")
    PORT = int(os.getenv("PORT", 5000))

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{RENDER_URL}/{BOT_TOKEN}"
    )

# -*- coding: utf-8 -*-
import logging, requests, csv, io, json
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes

BOT_TOKEN       = "8275086123:AAFM8iifVbe8cidhE07hoEbQ0svwqvRB8ac"
ALLOWED_CHAT_ID = -1002307445361
ALLOWED_THREAD  = 1575
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyDTnMjVzYH6utYWodJS2X06ifZTB72HH8o"
SHEET_URL  = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSzE3yAIP1h8h-uE8eXUtZMQrFy1exAQNpoDRHbNl8pHtRQ5LHPMSVHPj9Bo3S0S37ddiujcbYH6N1t/pub?gid=1477460020&single=true&output=csv"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_products():
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
        products = []
        i = 1
        while i < len(rows):
            row = rows[i]
            if not row or not row[0].strip():
                i += 1
                continue
            kod  = row[0].strip()
            nom  = row[1].strip() if len(row) > 1 else ""
            narx = row[2].strip().replace(" uzs","").replace(",","").strip() if len(row) > 2 else ""
            ball = row[3].strip() if len(row) > 3 else ""
            if kod and nom:
                products.append({"kod": kod, "nom": nom, "narx": narx, "ball": ball})
            i += 1
        return products, None
    except Exception as e:
        return [], str(e)

def format_price(narx):
    try:
        return "{:,}".format(int(float(narx.replace(" uzs","").replace(",","").strip()))).replace(",", " ")
    except:
        return narx

def search_products(query, products):
    q = query.lower().strip()
    return [p for p in products if q in p["kod"].lower() or q in p["nom"].lower()]

async def gemini_call(prompt):
    try:
        resp = requests.post(GEMINI_URL, headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error("Gemini xato: " + str(e))
        return ""

async def get_tavsiya(nom):
    result = await gemini_call("Mahsulot uchun Ozbek tilida 1 qisqa tavsiya yoz (max 15 soz). Faqat tavsiya: " + nom)
    return result or "Sogligingiz uchun foydali!"

async def ai_search(query, products):
    plist = "\n".join([str(i+1)+". Kod:"+p["kod"]+" Nom:"+p["nom"] for i,p in enumerate(products[:300])])
    prompt = 'Sorovi: "' + query + '"\nJSON format: {"kodlar":["KOD1"],"tavsiya":"..."}\nMahsulotlar:\n' + plist
    raw = await gemini_call(prompt)
    try:
        return json.loads(raw.replace("```json","").replace("```","").strip())
    except:
        return {"kodlar": [], "tavsiya": ""}

def make_card(p, tavsiya=""):
    msg = "\u2728 *Greenleaf Sifati* \u2728\n\n"
    msg += "\U0001f9fc *Mahsulot:* " + p["nom"] + "\n"
    msg += "\U0001f194 *Kod:* `" + p["kod"] + "`\n"
    msg += "\U0001f4b0 *Narx:* " + format_price(p["narx"]) + " so'm\n"
    msg += "\U0001f48e *Ball:* " + p["ball"] + " PV"
    if tavsiya:
        msg += "\n\u2705 " + tavsiya
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f44b *Assalomu alaykum!*\n\n"
        "\U0001f50d Mahsulot *kodi* yoki *nomini* yozing\n"
        "\U0001f4ac Erkin savol: `tish uchun nima bor?`\n\n"
        "Kanal ichida ishlatish: `@malumotqoldirishbot nomi`\n\n"
        "\U0001f4cb /barchasi \u2014 barcha mahsulotlar\n"
        "\U0001f504 /yangilash",
        parse_mode="Markdown"
    )

async def barchasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products, error = fetch_products()
    if error:
        await update.message.reply_text(error)
        return
    context.user_data["all_products"] = products
    await send_page(update, context, products, 0)

async def send_page(update, context, products, page):
    PAGE = 10
    si, ei = page*PAGE, (page+1)*PAGE
    text = "\U0001f4cb *Barcha mahsulotlar* (" + str(len(products)) + " ta)\n_" + str(page+1) + "-sahifa_\n\n"
    for p in products[si:ei]:
        text += "\u2022 `" + p["kod"] + "` \u2014 " + p["nom"] + " | \U0001f4b0" + format_price(p["narx"]) + " | \u2b50" + p["ball"] + "\n"
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton("\u2b05\ufe0f Oldingi", callback_data="page_"+str(page-1)))
    if ei < len(products):
        btns.append(InlineKeyboardButton("Keyingi \u27a1\ufe0f", callback_data="page_"+str(page+1)))
    kb = InlineKeyboardMarkup([btns]) if btns else None
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    page = int(update.callback_query.data.split("_")[1])
    products = context.user_data.get("all_products", [])
    if not products:
        products, _ = fetch_products()
        context.user_data["all_products"] = products
    if products:
        await send_page(update, context, products, page)

async def yangilash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\U0001f504 Yangilanmoqda...")
    products, error = fetch_products()
    if error:
        await msg.edit_text(error)
        return
    await msg.edit_text("\u2705 Yangilandi! Jami *" + str(len(products)) + "* ta mahsulot.", parse_mode="Markdown")

async def qidiruv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if len(query_text) < 2:
        await update.message.reply_text("\u26a0\ufe0f Kamida 2 ta harf kiriting.")
        return
    msg = await update.message.reply_text("\U0001f50d Qidirilmoqda...")
    products, error = fetch_products()
    if error:
        await msg.edit_text(error)
        return
    results = search_products(query_text, products)
    if results:
        if len(results) == 1:
            tavsiya = await get_tavsiya(results[0]["nom"])
            await msg.edit_text(make_card(results[0], tavsiya), parse_mode="Markdown")
        else:
            text = "\u2705 *" + str(len(results)) + "* ta natija:\n\n"
            for p in results[:20]:
                text += "\u2022 `" + p["kod"] + "` \u2014 " + p["nom"] + " | \U0001f4b0" + format_price(p["narx"]) + " | \U0001f48e" + p["ball"] + " PV\n"
            await msg.edit_text(text, parse_mode="Markdown")
        return
    await msg.edit_text("\U0001f916 AI qidirilmoqda...")
    ai = await ai_search(query_text, products)
    found = [p for p in products if p["kod"] in ai.get("kodlar", [])]
    if not found:
        await msg.edit_text("\U0001f615 *'" + query_text + "'* topilmadi.\n\U0001f4a1 Boshqacha yozing.", parse_mode="Markdown")
        return
    text = "\U0001f50d *'" + query_text + "'* uchun:\n\n"
    for p in found:
        text += "\U0001f9f4 *" + p["nom"] + "*\n"
        text += "`" + p["kod"] + "` | \U0001f4b0" + format_price(p["narx"]) + " | \U0001f48e" + p["ball"] + " PV\n\n"
    if ai.get("tavsiya"):
        text += "\U0001f916 " + ai["tavsiya"]
    await msg.edit_text(text, parse_mode="Markdown")

async def inline_qidiruv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if len(query) < 2:
        await update.inline_query.answer([], cache_time=0)
        return
    products, _ = fetch_products()
    results = search_products(query, products)
    if not results and len(query) >= 3:
        ai = await ai_search(query, products)
        results = [p for p in products if p["kod"] in ai.get("kodlar", [])]
    answers = []
    for p in results[:10]:
        answers.append(InlineQueryResultArticle(
            id=p["kod"],
            title=p["nom"][:60],
            description=format_price(p["narx"]) + " so'm | " + p["ball"] + " PV",
            input_message_content=InputTextMessageContent(
                message_text=make_card(p),
                parse_mode="Markdown"
            )
        ))
    await update.inline_query.answer(answers, cache_time=30)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("barchasi", barchasi))
    app.add_handler(CommandHandler("yangilash", yangilash))
    app.add_handler(CallbackQueryHandler(page_cb, pattern=r"^page_\d+$"))
    app.add_handler(InlineQueryHandler(inline_qidiruv))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, qidiruv))
    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()

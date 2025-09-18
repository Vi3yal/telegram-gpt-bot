import os
from uuid import uuid4
from openai import OpenAI
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler
)

BOT_TOKEN = '7869868942:AAH1ls4ZShrYxcOkO-_QGX6lB4U-QIqaxq8'
OPENAI_API_KEY = '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'


client = OpenAI(api_key=OPENAI_API_KEY)

# цена за 1 генерацию (Stars)
PRICE_TEXT_XTR = 99
PRICE_IMAGE_XTR = 199

# состояние пользователей
USER_STATE = {}
# {uid: {"text_free":1, "photo_free":1, "mode":None, "paid":False}}

def keyboard_main():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Текст", callback_data="text"),
        InlineKeyboardButton("🖼️ Фото", callback_data="photo"),
    ]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid not in USER_STATE:
        USER_STATE[uid] = {"text_free":1, "photo_free":1, "mode":None, "paid":False}
    st = USER_STATE[uid]
    await update.message.reply_text(
        f"Выбери вариант работы:\n\n"
        f"📝 Бесплатных текстов осталось: {st['text_free']}\n"
        f"🖼️ Бесплатных фото осталось: {st['photo_free']}",
        reply_markup=keyboard_main()
    )

async def on_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = USER_STATE.get(uid)

    if q.data in ["text", "photo"]:
        st["mode"] = q.data
        USER_STATE[uid] = st
        await q.message.reply_text(f"Режим выбран: {q.data}. Напиши свой запрос.")

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def on_success_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    st = USER_STATE.get(uid, {})
    st["paid"] = True
    USER_STATE[uid] = st
    await update.message.reply_text("✅ Оплата прошла. Теперь можно ввести запрос!")

async def handle_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    st = USER_STATE.get(uid)
    if not st or not st.get("mode"):
        await update.message.reply_text("Сначала выбери режим: /start")
        return

    text = update.message.text

    # --- ТЕКСТ ---
    if st["mode"] == "text":
        if st["text_free"] > 0:
            st["text_free"] -= 1
        elif st["paid"]:
            st["paid"] = False
        else:
            await context.bot.send_invoice(
                chat_id=uid,
                title="Текстовая генерация",
                description="1 текстовый ответ",
                payload=f"text-{uuid4()}",
                provider_token="",  # Stars
                currency="XTR",
                prices=[LabeledPrice("Текст", PRICE_TEXT_XTR)],
            )
            return

        resp = client.responses.create(
            model="gpt-5",
            input=[{"role":"user","content":text}]
        )
        await update.message.reply_text(resp.output_text)

    # --- ФОТО ---
    elif st["mode"] == "photo":
        if st["photo_free"] > 0:
            st["photo_free"] -= 1
        elif st["paid"]:
            st["paid"] = False
        else:
            await context.bot.send_invoice(
                chat_id=uid,
                title="Фото-генерация",
                description="1 картинка по запросу",
                payload=f"photo-{uuid4()}",
                provider_token="",  # Stars
                currency="XTR",
                prices=[LabeledPrice("Фото", PRICE_IMAGE_XTR)],
            )
            return

        img = client.images.generate(
            model="gpt-image-1",
            prompt=text,
            size="1024x1024"
        )
        await update.message.reply_photo(img.data[0].url, caption="Готово ✨")

    USER_STATE[uid] = st

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(on_buttons))
app.add_handler(PreCheckoutQueryHandler(pre_checkout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_success_payment))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_prompt))

if __name__ == "__main__":
    app.run_polling()

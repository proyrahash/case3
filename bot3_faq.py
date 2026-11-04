import asyncio
import logging
import os
import threading

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, PROXY_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 1. Проверка конфигурации
# ============================================================
if not PROXY_URL:
    raise SystemExit(
        "ОШИБКА: PROXY_URL не задан.\n"
        "На Render добавь переменную PROXY_URL=socks5://user:pass@host:port"
    )

if not BOT_TOKEN:
    raise SystemExit("ОШИБКА: BOT_TOKEN не задан.")

# ============================================================
# 2. Бот с прокси
# ============================================================
session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(
    token=BOT_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher()

# ============================================================
# 3. FAQ
# ============================================================
FAQ = {
    "price":    ("💰 Сколько стоит?", "Прайс-лист отправим файлом — нажмите «📎 Прайс-лист (PDF)» в меню."),
    "time":     ("🕐 Сколько времени занимает?", "Стандартный срок — 3-5 рабочих дней."),
    "warranty": ("🛡️ Есть ли гарантия?", "Да, 14 дней на исправление ошибок после сдачи."),
    "pay":      ("💳 Как оплатить?", "Перевод на карту или СБП. Работаю как самозанятый, выдаю чек."),
}


# ============================================================
# 4. Клавиатуры
# ============================================================
def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Прайс-лист (PDF)", callback_data="file:price")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="faq")],
    ])


def faq_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, (title, _) in FAQ.items():
        rows.append([InlineKeyboardButton(text=title, callback_data=f"q:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
# 5. Хендлеры
# ============================================================
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Здравствуйте! Это демо-бот-помощник.\n"
        "Здесь можно получить прайс-лист и ответы на частые вопросы.",
        reply_markup=main_kb(),
    )


@dp.callback_query(F.data == "file:price")
async def send_price(call: CallbackQuery):
    # price.pdf должен лежать рядом с bot3_faq.py и быть в репозитории
    price_file = FSInputFile("price.pdf", filename="Прайс-лист.pdf")
    await call.message.answer_document(
        price_file,
        caption="📎 Актуальный прайс-лист (демо).",
    )
    await call.answer()


@dp.callback_query(F.data == "faq")
async def show_faq(call: CallbackQuery):
    await call.message.edit_text(
        "❓ Выберите вопрос:",
        reply_markup=faq_kb(),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("q:"))
async def answer_faq(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    if key not in FAQ:
        await call.answer("Вопрос не найден", show_alert=True)
        return
    title, text = FAQ[key]
    await call.message.edit_text(
        f"<b>{title}</b>\n\n{text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К вопросам", callback_data="faq")]
        ]),
    )
    await call.answer()


@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "👋 Главное меню:",
        reply_markup=main_kb(),
    )
    await call.answer()


# ============================================================
# 6. Flask для Render Web Service (бесплатный тариф)
# ============================================================
app = Flask(__name__)


@app.route("/")
@app.route("/health")
def health():
    return "Bot is running", 200


def run_bot():
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    # Запускаем бота в отдельном ПРОЦЕССЕ, а не в потоке
    bot_process = multiprocessing.Process(target=run_bot_process, daemon=True)
    bot_process.start()

    # Flask запускается в главном процессе и слушает порт
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

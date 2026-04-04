"""
Standalone bot runner (optional).
The bot can also run embedded in main.py via lifespan.
Run separately only if needed:
    python bot.py
"""
import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.config import settings

dp = Dispatcher()
router = Router()


@router.message(Command("start"))
async def start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔫 Открыть AUC BOT",
            web_app=WebAppInfo(url="https://your-frontend.vercel.app")  # заменить
        )
    ]])
    await msg.answer(
        "Привет! Я помогу отслеживать цены на аукционе Stalcraft.\n"
        "Открой приложение 👇",
        reply_markup=kb
    )


async def main():
    bot = Bot(token=settings.bot_token)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

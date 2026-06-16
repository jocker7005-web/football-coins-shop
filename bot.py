import logging
import json
import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

TOKEN = "8875686952:AAGUFmIRMfWU2m-lqa9r9RyTeSvsF6Cpl3E"
ADMIN_GROUP_ID = -5459056432
WEBAPP_URL = "https://football-coins-shop.vercel.app"

KARTA_RAQAM = "8600 0000 0000 0000"  # O'z kartangizni yozing
KARTA_E_EGA = "FALONCHI PISTONCHIYEV" # Ismingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class OrderState(StatesGroup):
    waiting_for_game_id = State()
    waiting_for_check = State()

@dp.message(CommandStart())
async def start_command(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Do'konni ochish ⚽️🪙", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(f"Salom {message.from_user.full_name}!\n**Football Coins** do'konimizga xush kelibsiz.\n\nSotib olish uchun pastdagi tugmani bosing 👇", parse_mode="Markdown", reply_markup=kb)

@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        await state.update_data(platform="MOBILE", item=data.get("item"), price=data.get("price"), user_handle=message.from_user.mention_html())
        await message.answer(f"🛒 Siz tanladingiz: **{data.get('item')}** ({data.get('price')} so'm).\n\nIltimos, eFootball o'yinidagi **Foydalanuvchi ID (User ID)** raqamingizni yozib yuboring:", parse_mode="Markdown")
        await state.set_state(OrderState.waiting_for_game_id)
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

@dp.message(OrderState.waiting_for_game_id)
async def process_game_id(message: types.Message, state: FSMContext):
    await state.update_data(game_id=message.text)
    user_data = await state.get_data()
    payment_text = f"💳 **To'lov ma'lumotlari:**\n\n📦 **Mahsulot:** {user_data['item']}\n💰 **To'lov miqdori:** {user_data['price']} so'm\n\n📌 **Karta raqam:** `{KARTA_RAQAM}`\n👤 **Karta egasi:** {KARTA_E_EGA}\n\n⚠️ _Iltimos, Click yoki Payme orqali to'lovni amalga oshiring va bu yerga **to'lov chekini (rasmini)** yuboring!_"
    await message.answer(payment_text, parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_check)

@dp.message(OrderState.waiting_for_check, F.photo)
async def process_check(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    check_photo = message.photo[-1].file_id
    await message.answer(f"✅ **Rahmat! Buyurtmangiz qabul qilindi va adminga yuborildi.**\nTo'lov tekshirilgach, tangalar balansingizga yuklab beriladi.", parse_mode="Markdown")
    admin_text = f"🚨 <b>YANGI BUYURTMA</b> 🚨\n\n👤 <b>Mijoz:</b> {user_data['user_handle']}\n🆔 <b>O'yin ID:</b> <code>{user_data['game_id']}</code>\n📦 <b>Mahsulot:</b> {user_data['item']}\n💰 <b>Narxi:</b> {user_data['price']} so'm"
    try: await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=check_photo, caption=admin_text, parse_mode="HTML")
    except Exception as e: logging.error(f"Xabar ketmadi: {e}")
    await state.clear()

async def handle(request): return web.Response(text="Bot is running!")
async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    asyncio.create_task(site.start())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

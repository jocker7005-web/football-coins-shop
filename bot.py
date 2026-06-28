import os
import json
import random
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# --- MAXFIY MA'LUMOTLAR VA KONSTANTALAR ---
BOT_TOKEN = "8709150837:AAE_IAqDdmhLCKTGTBdg8Ng4kqadxpw9Oww"
ADMIN_ID = 1678146043
KARTA = "9860 3501 0897 5409 (Xusanova M)"
MAIN_CHANNEL = "@coinssharhlar"

# Minimal limitlar va komissiyalar
MIN_DEPOSIT = 15000   # Minimal kiritish 15 ming so'm
MIN_WITHDRAW = 10000  # Minimal yechish 10 ming so'm
WITHDRAW_TAX = 0.03   # 3% Pul yechish komissiyasi
MARKET_TAX = 0.10     # 10% Auksion savdo komissiyasi

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = "bot_data.json"

# --- TAYYOR FUTBOLCHILAR BAZASI (QONUNIY VA DIZAYNLI) ---
DEFAULT_PLAYERS = [
    {"id": "p1", "name": "Leo Messi", "rating": 94, "tier": "Afsonaviy 🌟", "emoji": "🐐"},
    {"id": "p2", "name": "C. Ronaldo", "rating": 93, "tier": "Afsonaviy 🌟", "emoji": "🤖"},
    {"id": "p3", "name": "K. Mbappe", "rating": 92, "tier": "Oltin 🟡", "emoji": "🐢"},
    {"id": "p4", "name": "K. De Bruyne", "rating": 91, "tier": "Oltin 🟡", "emoji": "👑"},
    {"id": "p5", "name": "V. van Dijk", "rating": 89, "tier": "Oltin 🟡", "emoji": "🧱"},
    {"id": "p6", "name": "Neymar Jr", "rating": 88, "tier": "Kumush ⚪", "emoji": "🇧🇷"},
    {"id": "p7", "name": "L. Modric", "rating": 87, "tier": "Kumush ⚪", "emoji": "🪄"},
    {"id": "p8", "name": "M. Salah", "rating": 86, "tier": "Kumush ⚪", "emoji": "👑"},
    {"id": "p9", "name": "E. Haaland", "rating": 91, "tier": "Oltin 🟡", "emoji": "🤖"},
    {"id": "p10", "name": "J. Bellingham", "rating": 88, "tier": "Kumush ⚪", "emoji": "💎"},
]

# --- MA'LUMOTLAR BAZASI FUNKSIYALARI ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"last_id": 0, "orders": {}, "withdraws": {}, "users": {}, "market": {}}
    try:
        with open(DATA_FILE, "r") as f:
            d = json.load(f)
            if "market" not in d: d["market"] = {}
            if "withdraws" not in d: d["withdraws"] = {}
            return d
    except Exception:
        return {"last_id": 0, "orders": {}, "withdraws": {}, "users": {}, "market": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def init_user(user_id, username=None):
    data = load_data()
    if str(user_id) not in data["users"]:
        # Boshlang'ich 3ta tasodifiy futbolchi berish
        starting_players = random.sample(DEFAULT_PLAYERS, 3)
        user_players = []
        for p in starting_players:
            p_copy = p.copy()
            p_copy["instance_id"] = f"{p['id']}_{random.randint(1000,9999)}"
            user_players.append(p_copy)
            
        data["users"][str(user_id)] = {
            "balance": 0,             # Joriy UZS balansi
            "frozen_balance": 0,      # Auksionda band bo'lgan UZS
            "username": username or "Mijoz",
            "players": user_players
        }
        save_data(data)

def get_next_order_id():
    data = load_data()
    current_id = data.get("last_id", 0)
    if current_id == 0 and data.get("orders"):
        try: current_id = max(int(k) for k in data["orders"].keys())
        except Exception: current_id = 0
    new_id = int(current_id) + 1
    data["last_id"] = new_id
    save_data(data)
    return int(new_id)
# --- FSM HOLATLARI (FOYDALANUVCHI KIRITAYOTGAN MA'LUMOTLARNI ESLAB QOLISH) ---
class BotStates(StatesGroup):
    entering_deposit_amount = State()   # Pul kiritish miqdorini yozish holati
    sending_deposit_receipt = State()   # To'lov chekini (rasmini) yuborish holati
    entering_withdraw_amount = State()  # Pul yechish miqdorini yozish holati
    entering_withdraw_card = State()    # Pul yechiladigan karta raqamini yozish holati
    selling_player_price = State()      # Auksionga qo'yilayotgan futbolchi narxini yozish holati

# --- ASOSIY REPLIK MENYULAR (BOT TUGMALARI) ---
def get_main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    
    # Biz kelishgan yangi o'yin va auksion menyu tizimi
    builder.row(types.KeyboardButton(text="🏟 Mening Klubim"), types.KeyboardButton(text="⚒ Auksion Bozori"))
    builder.row(types.KeyboardButton(text="💰 Mening Balansim"), types.KeyboardButton(text="🏆 Turnir"))
    builder.row(types.KeyboardButton(text="🎁 Bonuslarim"), types.KeyboardButton(text="📖 Qo'llanma"))
    builder.row(types.KeyboardButton(text="👨‍💻 Admin / Yordam"), types.KeyboardButton(text="✍️ Taklif qoldirish"))
    
    # Agar kirgan odam admin bo'lsa, qo'shimcha Admin Panel tugmasi chiqadi
    if user_id == ADMIN_ID:
        builder.row(types.KeyboardButton(text="🛠 Admin Panel"))
        
    return builder.as_markup(resize_keyboard=True)

# --- /START KOMANDASI (BOTGA BIRINCHI MARTA KIRILGANDA) ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Foydalanuvchini bazada tekshirish va ro'yxatdan o'tkazish (3 ta bepul futbolchi berish)
    init_user(user_id, username)
    
    await message.answer(
        f"Salom {message.from_user.full_name}! Shaxsiy Futbol Menejeri va Auksion botiga xush kelibsiz!\n"
        f"Ushbu botda siz o'z jamoangizni yig'ishingiz, auksionda UZS so'mida savdo qilishingiz mumkin.\n\n"
        f"Kerakli bo'limni tanlang:",
        reply_markup=get_main_menu(user_id)
    )

# --- AXBOROT VA YORDAM TUGMALARI ---
@dp.message(F.text == "📖 Qo'llanma")
async def cmd_guide(message: types.Message):
    await message.answer(
        "📖 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
        "1️⃣ <b>Mening Balansim</b> bo'limi orqali hisobingizni so'm (UZS) valyutasida to'ldiring (Kamida 15 000 so'm).\n"
        "2️⃣ <b>Auksion Bozori</b> sahifasiga kiring va sotuvdagi tayyor akkauntlarni yoki kuchli futbolchilarni sotib olish uchun stavka qo'ying.\n"
        "3️⃣ O'z futbolchilaringizni auksionga sotuvga qo'ying va so'm ishlab toping.\n"
        "4️⃣ Ishlab topgan pullaringizni <b>Mening Balansim</b> bo'limidan kartangizga yechib oling (Kamida 10 000 so'm).",
        parse_mode="HTML"
    )

@dp.message(F.text == "👨‍💻 Admin / Yordam")
async def cmd_support(message: types.Message):
    await message.answer("👨‍💻 Har qanday savollar, muammolar yoki takliflar bo'yicha adminga murojaat qiling: @jocker7005")
# --- 🏟 MENING KLUBIM BO'LIMI (JAMOANI KO'RISH) ---
@dp.message(F.text == "🏟 Mening Klubim")
async def cmd_my_club(message: types.Message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.username)
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    players = user_data.get("players", [])
    if players:
        total_rating = sum(p["rating"] for p in players)
        avg_rating = round(total_rating / len(players), 1)
    else:
        avg_rating = 0
        
    text = f"🏟 <b>Sizning shaxsiy futbol klubingiz:</b>\n\n" \
           f"💰 Hisobingiz: <b>{user_data.get('balance', 0)} UZS</b>\n" \
           f"🔒 Muzlatilgan pullar: <b>{user_data.get('frozen_balance', 0)} UZS</b>\n" \
           f"📊 Jamoa umumiy kuchi: <b>{avg_rating} / 100</b>\n" \
           f"🏃‍♂️ Jami futbolchilar: <b>{len(players)} ta</b>\n\n" \
           f"📋 <b>Sizning futbolchilaringiz ro'yxati:</b>\n"
           
    for i, p in enumerate(players, 1):
        text += f"{i}. {p['emoji']} <b>{p['name']}</b> | Reyting: <code>{p['rating']}</code> | {p['tier']}\n"
        
    await message.answer(text, parse_mode="HTML")

# --- ✍️ TAKLIF QOLDIRISH TIZIMI ---
@dp.message(F.text == "✍️ Taklif qoldirish")
async def cmd_suggestion(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.writing_suggestion)
    await message.answer("Taklif yoki shikoyatingizni yozib yuboring:")

@dp.message(BotStates.writing_suggestion, F.text)
async def process_suggestion(message: types.Message, state: FSMContext):
    # Agar foydalanuvchi taklif yozish o'rniga boshqa menyu tugmasini bossa, jarayon bekor bo'ladi
    if message.text in ["🏟 Mening Klubim", "⚒ Auksion Bozori", "💰 Mening Balansim", "🏆 Turnir", "🎁 Bonuslarim", "📖 Qo'llanma", "👨‍💻 Admin / Yordam", "✍️ Taklif qoldirish", "🛠 Admin Panel"]:
        await state.clear()
        return await dp.feed_message(bot, message)
        
    admin_msg = f"✍️ <b>YANGI TAKLIF</b>\n\nKimdan: {message.from_user.full_name}\nID: <code>{message.from_user.id}</code>\n\n\"{message.text}\""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
        await message.answer("✅ Taklifingiz adminga yetkazildi!")
    except Exception:
        await message.answer("✅ Qabul qilindi!")
    await state.clear()
# --- 💰 MENING BALANSIM VA PUL AMALLARI BO'LIMI ---
@dp.message(F.text == "💰 Mening Balansim")
async def cmd_my_balance(message: types.Message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.username)
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    text = f"💰 <b>Sizning shaxsiy balansingiz:</b>\n\n" \
           f"🟢 Joriy balans: <b>{user_data.get('balance', 0)} UZS</b>\n" \
           f"🔒 Muzlatilgan pullar: <b>{user_data.get('frozen_balance', 0)} UZS</b>\n\n" \
           f"ℹ️ <i>Kiritish komissiyasi: 0% (Minimal: 15 000 so'm)\n" \
           f"Yechish komissiyasi: 3% (Minimal: 10 000 so'm)</i>"
           
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Balansni to'ldirish (+)", callback_data="deposit_start")
    builder.button(text="💸 Pul yechish (-)", callback_data="withdraw_start")
    builder.adjust(2)
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- 📥 PUL KIRITISH (DEPOSIT) TIZIMI ---
@dp.callback_query(F.data == "deposit_start")
async def process_deposit_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.entering_deposit_amount)
    await callback.message.answer("Hisobingizni qancha so'm (UZS) ga to'ldirmoqchisiz? Miqdorni raqamlarda yozing (Masalan: 50000):")
    await callback.answer()

@dp.message(BotStates.entering_deposit_amount, F.text)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, miqdorni faqat raqamlarda kiriting:")
        return
        
    amount = int(message.text)
    if amount < MIN_DEPOSIT:
        await message.answer(f"⚠️ Minimal to'ldirish miqdori {MIN_DEPOSIT:,} so'm! Iltimos, qaytadan ko'proq miqdor kiriting:")
        return
        
    await state.update_data(deposit_amount=amount)
    await state.set_state(BotStates.sending_deposit_receipt)
    
    await message.answer(
        f"To'lov summasi: <b>{amount:,} UZS</b> (Komissiya: 0%)\n\n" \
        f"To'lovni amalga oshiring:\n" \
        f"💳 Karta raqami: <code>{KARTA}</code>\n\n" \
        f"Pulni o'tkazib bo'lgach, chek rasmini (skrinshotini) shu yerga yuboring.",
        parse_mode="HTML"
    )

@dp.message(BotStates.sending_deposit_receipt, F.photo)
async def process_deposit_receipt(message: types.Message, state: FSMContext):
    data = load_data()
    order_id = get_next_order_id()
    fsm_data = await state.get_data()
    amount = fsm_data.get("deposit_amount")
    
    # Buyurtmani bazada saqlash
    data["orders"][str(order_id)] = {
        "user_id": message.from_user.id,
        "amount": amount,
        "status": "Kutilmoqda ⏳"
    }
    save_data(data)
    
    await message.answer(f"✅ Arizangiz adminga yuborildi, tekshirilmoqda ⏳\nBuyurtma raqamingiz: #N{order_id}")
    
    # Adminga tasdiqlash tugmalari boradi
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash (0%)", callback_data=f"adm_dep_ok:{order_id}")
    builder.button(text="❌ Rad etish", callback_data=f"adm_dep_rej:{order_id}")
    builder.adjust(2)
    
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    admin_text = f"🚨 <b>YANGI PUL KIRITISH #N{order_id}</b>\n\n" \
                 f"👤 Kimdan: {username}\n" \
                 f"💰 Summa: <b>{amount:,} UZS</b>"
                 
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception: pass
    await state.clear()

# --- 📤 PUL YECHISH (WITHDRAW) TIZIMI ---
@dp.callback_query(F.data == "withdraw_start")
async def process_withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = load_data()
    user_balance = data["users"][str(user_id)].get("balance", 0)
    
    if user_balance < MIN_WITHDRAW:
        await callback.message.answer(f"❌ Balansingizda pul yetarli emas! Minimal yechish miqdori: {MIN_WITHDRAW:,} so'm.")
        await callback.answer()
        return
        
    await state.clear()
    await state.set_state(BotStates.entering_withdraw_amount)
    await callback.message.answer(f"Balansingizda: {user_balance:,} UZS bor.\nQancha pul yechmoqchisiz? (Minimal: {MIN_WITHDRAW:,} so'm):")
    await callback.answer()

@dp.message(BotStates.entering_withdraw_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, miqdorni faqat raqamlarda kiriting:")
        return
        
    amount = int(message.text)
    user_id = message.from_user.id
    data = load_data()
    user_balance = data["users"][str(user_id)].get("balance", 0)
    
    if amount < MIN_WITHDRAW:
        await message.answer(f"⚠️ Minimal pul yechish miqdori {MIN_WITHDRAW:,} so'm! Qaytadan kiriting:")
        return
        
    if amount > user_balance:
        await message.answer(f"❌ Hisobingizda mablag' yetarli emas! Sizda bor: {user_balance:,} UZS. Qaytadan kiriting:")
        return
        
    await state.update_data(withdraw_amount=amount)
    await state.set_state(BotStates.entering_withdraw_card)
    await message.answer("Pullar o'tkazib berilishi kerak bo'lgan Plastik karta raqamini kiriting:")

@dp.message(BotStates.entering_withdraw_card, F.text)
async def process_withdraw_card(message: types.Message, state: FSMContext):
    card_number = message.text
    fsm_data = await state.get_data()
    amount = fsm_data.get("withdraw_amount")
    user_id = message.from_user.id
    
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    # Balansdan pulni muzlatish
    user_data["balance"] -= amount
    user_data["frozen_balance"] += amount
    
    withdraw_id = f"w_{random.randint(10000,99999)}"
    data["withdraws"][withdraw_id] = {
        "user_id": user_id,
        "amount": amount,
        "card": card_number,
        "status": "Kutilmoqda ⏳"
    }
    save_data(data)
    
    # 3% komissiya hisoblash
    tax = int(amount * WITHDRAW_TAX)
    final_amount = amount - tax
    
    await message.answer(f"✅ Pul yechish so'rovi muvaffaqiyatli qabul qilindi. Adminga yuborildi.\n" \
                         f"Muzlatilgan summa: {amount:,} UZS\n" \
                         f"Kartangizga tushadigan sof pul (3% komissiya ushlanib): <b>{final_amount:,} UZS</b>")
                         
    # Adminga xabar yuborish
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ To'landi", callback_data=f"adm_w_ok:{withdraw_id}")
    builder.button(text="❌ Rad etish", callback_data=f"adm_w_rej:{withdraw_id}")
    builder.adjust(2)
    
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    admin_text = f"💸 <b>PUL YECHISH SO'ROVI</b>\n\n" \
                 f"👤 Kimdan: {username}\n" \
                 f"💳 Karta: <code>{card_number}</code>\n" \
                 f"💰 Yechish summasi: <b>{amount:,} UZS</b>\n" \
                 f"🚀 Kartaga o'tkazish kerak: <b>{final_amount:,} UZS</b>"
                 
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception: pass
    await state.clear()
# --- ⚒ AUKSION BOZORI BO'LIMI (P2P AUCTION) ---
@dp.message(F.text == "⚒ Auksion Bozori")
async def cmd_auction_market(message: types.Message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.username)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Auksiondagi e'lonlarni ko'rish", callback_data="auc_browse")
    builder.button(text="➕ Jamoani auksionga qo'yish", callback_data="auc_sell_list")
    builder.adjust(1)
    
    await message.answer(
        "⚒ <b>Auksion bozoriga xush kelibsiz!</b>\n\n"
        "Bu yerda siz o'z futbolchi yoki jamoangizni auksion savdosiga qo'yishingiz mumkin. "
        "Eng baland stavka qo'ygan ishtirokchi g'olib bo'ladi. "
        "Muvaffaqiyatli savdodan 10% komissiya ushlab qolinadi.", 
        reply_markup=builder.as_markup(), 
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "auc_browse")
async def process_auc_browse(callback: types.CallbackQuery):
    data = load_data()
    market = data.get("market", {})
    
    if not market:
        await callback.message.answer("❌ Hozirda auksionda sotiladigan jamoalar/futbolchilar yo'q.")
        await callback.answer()
        return
        
    text = "⚒ <b>Auksiondagi joriy e'lonlar:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for m_id, item in market.items():
        p = item["player"]
        # O'z e'loniga stavka qo'yishni taqiqlash
        if str(item["seller_id"]) != str(callback.from_user.id):
            current_price = item["price"]
            next_min_bid = current_price + 5000  # Minimal qadam: +5 000 UZS
            
            builder.button(
                text=f"Stavka qo'yish: {p['name']} ({next_min_bid:,} UZS)", 
                callback_data=f"bid_p:{m_id}"
            )
            
            # G'olib holatini aniqlash
            winner_text = f"@{item['highest_bidder_name']}" if item.get("highest_bidder") else "Hech kim"
            
            text += f"🔸 {p['emoji']} <b>{p['name']}</b> (Reyting: {p['rating']})\n" \
                    f"💵 Joriy narx: <code>{current_price:,} UZS</code>\n" \
                    f"👑 Etakchi: {winner_text}\n" \
                    f"👤 Sotuvchi: ID {item['seller_id']}\n\n"
            
    builder.adjust(1)
    if not builder.export():
        await callback.message.answer("❌ Bozorda faqat siz qo'ygan auksion e'lonlari mavjud.")
    else:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "auc_sell_list")
async def process_auc_sell_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = load_data()
    user_data = data["users"][str(user_id)]
    players = user_data.get("players", [])
    
    if len(players) <= 3:
        await callback.message.answer("❌ Jamoangizda kamida 3 ta futbolchi qolishi kerak! Shuning uchun hozir auksionga qo'ya olmaysiz.")
        await callback.answer()
        return
        
    builder = InlineKeyboardBuilder()
    for p in players:
        builder.button(text=f"{p['emoji']} {p['name']} ({p['rating']})", callback_data=f"auc_sl_p:{p['instance_id']}")
    builder.adjust(1)
    
    await callback.message.answer("Auksionga boshlang'ich narx belgilab sotmoqchi bo'lgan futbolchingizni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("auc_sl_p:"))
async def process_auc_sell_price(callback: types.CallbackQuery, state: FSMContext):
    instance_id = callback.data.split(":")[-1]
    await state.update_data(sell_instance_id=instance_id)
    await state.set_state(BotStates.selling_player_price)
    await callback.message.answer("Auksion uchun boshlang'ich narxni (so'mda) kiriting (Masalan: 20000):")
    await callback.answer()

@dp.message(BotStates.selling_player_price, F.text)
async def process_auc_selling_final(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, boshlang'ich narxni faqat raqamlarda kiriting:")
        return
        
    start_price = int(message.text)
    fsm_data = await state.get_data()
    instance_id = fsm_data.get("sell_instance_id")
    
    user_id = message.from_user.id
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    player_to_sell = None
    for p in user_data["players"]:
        if p["instance_id"] == instance_id:
            player_to_sell = p
            break
            
    if player_to_sell:
        market_id = f"auc_{random.randint(10000,99999)}"
        # Auksion e'lonini bazaga qo'shish
        data["market"][market_id] = {
            "seller_id": user_id,
            "player": player_to_sell,
            "price": start_price,
            "highest_bidder": None,
            "highest_bidder_name": None
        }
        user_data["players"].remove(player_to_sell)
        save_data(data)
        await message.answer(f"✅ {player_to_sell['name']} muvaffaqiyatli auksion bozoriga {start_price:,} UZS boshlang'ich narxda joylashtirildi!\n\n<i>Eslatma: Auksion tizimi avtomatik savdoda ishlaydi.</i>", parse_mode="HTML")
    else:
        await message.answer("Xatolik yuz berdi. Qayta urinib ko'ring.")
        
    await state.clear()

@dp.callback_query(F.data.startswith("bid_p:"))
async def process_auction_bid_final(callback: types.CallbackQuery):
    market_id = callback.data.split(":")[-1]
    buyer_id = callback.from_user.id
    username = callback.from_user.username or "O'yinchi"
    data = load_data()
    
    item = data["market"].get(market_id)
    if not item:
        await callback.message.answer("❌ Bu auksion yakunlangan yoki o'chirilgan.")
        await callback.answer()
        return
        
    current_price = item["price"]
    next_min_bid = current_price + 5000  # Qadam: +5 000 UZS
    
    buyer_data = data["users"][str(buyer_id)]
    if buyer_data.get("balance", 0) < next_min_bid:
        await callback.message.answer("❌ Hisobingizda stavka qo'yish uchun yetarli pul (UZS) yo'q!")
        await callback.answer()
        return
        
    # Agarda avval boshqa odam etakchi bo'lsa, uning pulini muzlatishdan chiqarib balansiga qaytaramiz
    old_bidder = item.get("highest_bidder")
    if old_bidder:
        data["users"][str(old_bidder)]["frozen_balance"] -= current_price
        data["users"][str(old_bidder)]["balance"] += current_price
        try:
            await bot.send_message(
                chat_id=old_bidder, 
                text=f"📉 Sizning auksiondagi stavkangizni boshqa o'yinchi urib ketdi! "
                     f"<b>{item['player']['name']}</b> uchun pulingiz ({current_price:,} UZS) balansingizga qaytarildi.",
                parse_mode="HTML"
            )
        except Exception: pass

    # Yangi xaridor pulini balansidan muzlatish (qulflash)
    buyer_data["balance"] -= next_min_bid
    buyer_data["frozen_balance"] += next_min_bid
    
    # Auksion holatini yangilash
    item["price"] = next_min_bid
    item["highest_bidder"] = buyer_id
    item["highest_bidder_name"] = username
    save_data(data)
    
    await callback.message.answer(f"📈 Tabriklaymiz! Siz muvaffaqiyatli <b>{next_min_bid:,} UZS</b> stavka qo'ydingiz va auksionda etakchiga aylandingiz!", parse_mode="HTML")
    await callback.answer()
# --- 🏆 TURNIR VA FUTBOL MATCH SIMULYATORI BO'LIMI ---
@dp.message(F.text == "🏆 Turnir")
async def cmd_tournament(message: types.Message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.username)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⚽ Onlayn Match boshlash (PVP)", callback_data="start_match")
    builder.button(text="📊 Turnir Setkasini Ko'rish", url="https://t.me")
    builder.adjust(1)
    
    tournament_text = f"🏆 <b>GRAND eFOOTBALL MOBILE MATNLAR TURNIRI!</b> 🏆\n\n" \
                      f"🔥 <b>Jamoangiz bilan matnli o'yinlarda qatnashib haqiqiy UZS so'm yutib olishni xohlaysizmi?</b>\n\n" \
                      f"📌 <b>O'yin Qoidasi:</b>\n" \
                      f"Onlayn Match tugmasini bossangiz, tizim sizga raqib topadi va jamoalaringiz kuchini solishtirib o'yin natijasini aniqlaydi! G'olib o'yin hisobiga UZS yutib oladi. Charchoqni chiqarish uchun Video reklama ko'riladi.\n\n" \
                      f"🔗 <b>Rasmiy kiber-kanalimiz:</b> https://t.me"
                      
    await message.answer(text=tournament_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "start_match")
async def process_start_match(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    players = user_data.get("players", [])
    if not players:
        await callback.message.answer("❌ O'yin o'ynash uchun avval jamoangizda futbolchilar bo'lishi kerak!")
        await callback.answer()
        return
        
    user_power = sum(p["rating"] for p in players) / len(players)
    
    await callback.message.answer("⏳ <b>Raqib qidirilmoqda va match simulyatsiya qilinmoqda...</b>", parse_mode="HTML")
    await asyncio.sleep(2)
    
    # Tasodifiy raqib kuchi (Bot)
    opponent_power = random.randint(70, 95)
    
    user_score = random.randint(0, 4)
    opp_score = random.randint(0, 4)
    
    # Kuchliroq jamoaga ustunlik berish
    if user_power > opponent_power and user_score <= opp_score:
        user_score = opp_score + random.randint(1, 2)
    elif user_power < opponent_power and user_score >= opp_score:
        opp_score = user_score + random.randint(1, 2)
        
    match_text = f"🏁 <b>Match yakunlandi!</b>\n\n" \
                 f"🏟 Sizning Jamoangiz (Kuch: {round(user_power,1)}) <b>{user_score} : {opp_score}</b> Raqib Jamoa (Kuch: {opponent_power})\n\n"
                 
    if user_score > opp_score:
        user_data["balance"] = user_data.get("balance", 0) + 1000  # G'alaba uchun +1000 UZS
        match_text += f"🎉 <b>G'ALABA!</b> Jamoangiz ajoyib o'yin ko'rsatdi va siz <b>+1,000 UZS</b> mukofot yutib oldingiz!"
    elif user_score < opp_score:
        match_text += f"❌ <b>MAG'LUBIYAT!</b> Raqib taktika taraflama kuchliroq chiqdi. Jamoani kuchaytirish uchun auksiondan kuchli futbolchilar sotib oling."
    else:
        user_data["balance"] = user_data.get("balance", 0) + 300  # Durang uchun +300 UZS
        match_text += f"🤝 <b>DURANG!</b> Har ikki jamoa murosasiz o'yin ko'rsatdi. Siz <b>+300 UZS</b> tasalli mukofotini oldingiz."
        
    save_data(data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📺 Charchoqni chiqarish (Video ko'rish va yana o'ynash)", callback_data="adsgram_reward")
    await callback.message.answer(match_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# --- 🎁 BONUSLARIM (ADSGRAM INTEGRATSIYASI TUGMASI) ---
@dp.message(F.text == "🎁 Bonuslarim")
async def cmd_bonuses(message: types.Message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.username)
    data = load_data()
    user_info = data["users"][str(user_id)]
    
    text = (
        f"🎁 <b>Sizning bonus hamyoningiz:</b>\n\n"
        f"🪙 Shaxsiy O'yin Balansi: <b>{user_info.get('balance', 0)} UZS</b>\n"
        f"🔒 Muzlatilgan pullar: <b>{user_info.get('frozen_balance', 0)} UZS</b>\n\n"
        f"📺 <b>ADSGRAM SPONSOR VIDEO:</b>\n"
        f"Quyidagi tugma orqali 15 soniyalik video reklama ko'rib, o'yin balansingiz uchun bepul 500 UZS yoki Oltin Futbolchi paketini yutib oling! 👇"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="📺 Adsgram Video ko'rish (+500 UZS)", callback_data="adsgram_reward")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "adsgram_reward")
async def process_adsgram_reward(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = load_data()
    user_data = data["users"][str(user_id)]
    
    # Adsgram Simulyatsiya mukofoti (Video to'liq ko'rilganda so'm yoki karta beradi)
    prize_pool = ["uzs", "uzs", "pack"]  # 66% ehtimol bilan pul, 33% ehtimol bilan o'yinchi
    result = random.choice(prize_pool)
    
    if result == "uzs":
        user_data["balance"] = user_data.get("balance", 0) + 500  # Siz aytgan har bir reklama uchun bonus so'm
        await callback.message.answer("🎉 Adsgram videosi muvaffaqiyatli yakunlandi! Hisobingizga bepul <b>+500 UZS</b> haqiqiy o'yin puli qo'shildi!", parse_mode="HTML")
    else:
        new_p = random.choice(DEFAULT_PLAYERS).copy()
        new_p["instance_id"] = f"{new_p['id']}_{random.randint(1000,9999)}"
        user_data["players"].append(new_p)
        await callback.message.answer(f"🔥 KATTA YUTUQ! Video to'liq ko'rilgani uchun sizga BEPUL Oltin paket ochildi va ichidan: {new_p['emoji']} <b>{new_p['name']} (Reyting: {new_p['rating']})</b> chiqdi! Jamoangizga qo'shildi.", parse_mode="HTML")
        
    save_data(data)
    await callback.answer()
# --- ADMIN CALLBACK PROCESS (PUL KIRITISH VA YECHISHNI BOSHQARISH) ---
@dp.callback_query(F.data.startswith("adm_dep_ok:"))
async def admin_deposit_ok(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    order_id = callback.data.split(":")[-1]
    
    data = load_data()
    order = data["orders"].get(str(order_id))
    
    if order and order["status"] != "Bajarildi ✅":
        order["status"] = "Bajarildi ✅"
        user_id = order["user_id"]
        amount = order["amount"]
        
        # Foydalanuvchi balansiga pulni tushirish (0% komissiya)
        init_user(user_id)
        data["users"][str(user_id)]["balance"] += amount
        save_data(data)
        
        # Mijozga xabar berish
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"🎉 <b>Hisobingiz muvaffaqiyatli to'ldirildi!</b>\n"
                     f"💰 Hisobingizga: <b>{amount:,} UZS</b> qo'shildi. Auksionda qatnashishingiz mumkin!", 
                parse_mode="HTML"
            )
        except Exception: pass
        
        try:
            await callback.message.edit_caption(caption=callback.message.caption + f"\n\n🟢 STATUS: TASDIQLANDI (+{amount:,} UZS)", parse_mode="HTML")
        except Exception: pass
        
    await callback.answer()

@dp.callback_query(F.data.startswith("adm_dep_rej:"))
async def admin_deposit_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    order_id = callback.data.split(":")[-1]
    
    data = load_data()
    order = data["orders"].get(str(order_id))
    
    if order and order["status"] != "Rad etildi ❌":
        order["status"] = "Rad etildi ❌"
        save_data(data)
        
        try:
            await bot.send_message(
                chat_id=order["user_id"], 
                text=f"❌ Kechirasiz, sizning #N{order_id} raqamli pul kiritish arizangiz admin tomonidan rad etildi.\n"
                     f"Iltimos, chek rasmini to'g'ri yuborganingizni tekshiring yoki adminga murojaat qiling."
            )
        except Exception: pass
        
        try:
            await callback.message.edit_caption(caption=callback.message.caption + f"\n\n🔴 STATUS: RAD ETILDI", parse_mode="HTML")
        except Exception: pass
        
    await callback.answer()

@dp.callback_query(F.data.startswith("adm_w_ok:"))
async def admin_withdraw_ok(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    withdraw_id = callback.data.split(":")[-1]
    
    data = load_data()
    item = data["withdraws"].get(withdraw_id)
    
    if item and item["status"] != "To'landi ✅":
        item["status"] = "To'landi ✅"
        user_id = item["user_id"]
        amount = item["amount"]
        
        # Muzlatilgan pulni butunlay o'chirish
        data["users"][str(user_id)]["frozen_balance"] -= amount
        save_data(data)
        
        tax = int(amount * WITHDRAW_TAX)
        final_amount = amount - tax
        
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"🚀 <b>Pullaringiz kartangizga muvaffaqiyatli o'tkazildi!</b>\n"
                     f"💰 Yechilgan jami: {amount:,} UZS\n"
                     f"💳 Kartangizga tushgan sof pul (3% komissiya bilan): <b>{final_amount:,} UZS</b>",
                parse_mode="HTML"
            )
        except Exception: pass
        
        try:
            await callback.message.edit_text(text=callback.message.text + f"\n\n🟢 STATUS: TO'LANDI (Mijozga {final_amount:,} UZS yuborildi)")
        except Exception: pass
        
    await callback.answer()

@dp.callback_query(F.data.startswith("adm_w_rej:"))
async def admin_withdraw_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    withdraw_id = callback.data.split(":")[-1]
    
    data = load_data()
    item = data["withdraws"].get(withdraw_id)
    
    if item and item["status"] != "Rad etildi ❌":
        item["status"] = "Rad etildi ❌"
        user_id = item["user_id"]
        amount = item["amount"]
        
        # Muzlatilgan pulni qaytadan foydalanuvchining asosiy balansiga qaytarish
        data["users"][str(user_id)]["frozen_balance"] -= amount
        data["users"][str(user_id)]["balance"] += amount
        save_data(data)
        
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"❌ Sizning pul yechish so'rovingiz admin tomonidan rad etildi.\n"
                     f"Muzlatilgan <b>{amount:,} UZS</b> pulingiz hisobingizga qaytarildi.",
                parse_mode="HTML"
            )
        except Exception: pass
        
        try:
            await callback.message.edit_text(text=callback.message.text + f"\n\n🔴 STATUS: RAD ETILDI (Pullari balansiga qaytdi)")
        except Exception: pass
        
    await callback.answer()

# --- ADMIN PANEL COMMAND ---
@dp.message(F.text == "🛠 Admin Panel")
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        data = load_data()
        await message.answer(
            f"🛠 <b>Admin Panel</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{len(data.get('users', {}))} ta</b>\n"
            f"📥 Kiritish arizalari: <b>{len(data.get('orders', {}))} ta</b>\n"
            f"📤 Yechish arizalari: <b>{len(data.get('withdraws', {}))} ta</b>\n"
            f"⚒ Auksiondagi faol e'lonlar: <b>{len(data.get('market', {}))} ta</b>", 
            parse_mode="HTML"
        )

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

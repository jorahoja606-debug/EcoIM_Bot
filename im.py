import asyncio
import logging
import aiosqlite
import qrcode
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# --- SOZLAMALAR ---
API_TOKEN = "8623925872:AAGmtzyPWeX4qzZg9GHeTVe4O-h_ZJs6os0"
ADMIN_IDS = [6396886650, 8274938812, 8524520506]
DB_PATH = "ecoim_v8.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- HOLATLAR ---
class AdminActions(StatesGroup):
    target_id = State()
    amount = State()
    broadcast_msg = State()
    penalty_class = State()
    penalty_amount = State()

class Waste(StatesGroup):
    weight = State()
    photo = State()

class Reg(StatesGroup):
    name = State()
    status = State()
    class_name = State()

class EditProfile(StatesGroup):
    new_name = State()
    new_class = State()

# --- MA'LUMOTLAR OMBORI ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY, full_name TEXT, status TEXT, class_name TEXT, coins REAL DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS settings
            (key TEXT PRIMARY KEY, value REAL)""")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('p_boost', 1.0)")
        await db.commit()

# --- KLAVIATURALAR ---
def main_menu(uid):
    kb = [
        [KeyboardButton(text="➕ Chiqindi topshirish")],
        [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="🏫 Sinfiy Reyting"), KeyboardButton(text="⚙️ Sozlamalar")],
    ]
    if uid in ADMIN_IDS:
        kb.append([KeyboardButton(text="🛠 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📉 Sinfdan ball ayirish"), KeyboardButton(text="📢 Xabar yuborish")],
            [KeyboardButton(text="🚀 Aksiya Yoqish"), KeyboardButton(text="📥 Matn hisobot")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True,
    )

# --- START VA RO'YXATDAN O'TISH ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("add_") and message.from_user.id in ADMIN_IDS:
        target_id = args[1].replace("add_", "")
        await state.update_data(target_id=target_id)
        await message.answer(f"🆔 Foydalanuvchi ID: {target_id}\nQancha ball qo'shmoqchisiz?")
        await state.set_state(AdminActions.amount)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name FROM users WHERE id=?", (message.from_user.id,)) as cur:
            user = await cur.fetchone()
            if user:
                await message.answer(f"Xush kelibsiz, {user[0]}!", reply_markup=main_menu(message.from_user.id))
            else:
                await message.answer("EcoIM tizimiga xush kelibsiz!\nIsm va familiyangizni kiriting:")
                await state.set_state(Reg.name)

@dp.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="O'quvchi"), KeyboardButton(text="O'qituvchi")]], resize_keyboard=True)
    await message.answer("Siz kimsiz?", reply_markup=kb)
    await state.set_state(Reg.status)

@dp.message(Reg.status)

async def reg_status(message: types.Message, state: FSMContext):
    if message.text == "O'qituvchi":
        data = await state.get_data()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO users (id, full_name, status, class_name) VALUES (?, ?, ?, ?)",
                             (message.from_user.id, data["name"], "O'qituvchi", "O'QITUVCHILAR"))
            await db.commit()
        await message.answer("Ro'yxatdan o'tdingiz!", reply_markup=main_menu(message.from_user.id))
        await state.clear()
    else:
        await message.answer("Sinfingizni kiriting (Masalan: 10-A):")
        await state.set_state(Reg.class_name)

@dp.message(Reg.class_name)
async def reg_class(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO users (id, full_name, status, class_name) VALUES (?, ?, ?, ?)",
                         (message.from_user.id, data["name"], "O'quvchi", message.text.upper()))
        await db.commit()
    await message.answer("Muvaffaqiyatli ro'yxatdan o'tdingiz!", reply_markup=main_menu(message.from_user.id))
    await state.clear()

# --- CHIQINDI TOPSHIRISH VA ADMIN TASDIQLASHI ---
@dp.message(F.text == "➕ Chiqindi topshirish")
async def waste_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Qog'oz (5 ball)", callback_data="w:qogoz:5")],
        [InlineKeyboardButton(text="Plastik (15 ball)", callback_data="w:plastik:15")]
        [InlineKeyboardButton(text="Marker (45 ball)", callback_data="w:marker:45")]
       [InlineKeyboardButton(text="Bo'r kukuni (30 ball)", callback_data="w:bor_kukuni:30")]
    ])
    await message.answer("Chiqindi turini tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("w:"))
async def waste_type(call: types.CallbackQuery, state: FSMContext):
    _, w_type, price = call.data.split(":")
    await state.update_data(w_type=w_type, price=float(price))
    await call.message.edit_text("Vaznni kg da kiriting (Masalan: 5.2):")
    await state.set_state(Waste.weight)

@dp.message(Waste.weight)
async def waste_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        await state.update_data(weight=weight)
        await message.answer("📸 Tarozi va chiqindi ko'ringan rasm yuboring:")
        await state.set_state(Waste.photo)
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting!")

@dp.message(Waste.photo, F.photo)
async def waste_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='p_boost'") as cur:
            boost = (await cur.fetchone())[0]

    ball = data["weight"] * data["price"] * boost
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"accept:{message.from_user.id}:{ball}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{message.from_user.id}")]
    ])

    await bot.send_photo(ADMIN_IDS[0], message.photo[-1].file_id,
                         caption=f"👤 {message.from_user.full_name}\n⚖️ {data['weight']}kg | 💰 {ball} ball",
                         reply_markup=kb)
    await message.answer("⏳ Arizangiz adminlarga yuborildi.", reply_markup=main_menu(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data.startswith("accept:"))
async def admin_accept(call: types.CallbackQuery):
    _, uid, ball = call.data.split(":")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (float(ball), int(uid)))
        await db.commit()
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANDI")
    await bot.send_message(uid, f"✅ Arizangiz tasdiqlandi! Sizga {ball} ball qo'shildi.")
    await call.answer()

@dp.callback_query(F.data.startswith("reject:"))
async def admin_reject(call: types.CallbackQuery):
    uid = call.data.split(":")[1]
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ RAD ETILDI")
    await bot.send_message(uid, "❌ Arizangiz rad etildi.")
    await call.answer()

# --- ADMIN PANEL FUNKSIYALARI ---
@dp.message(F.text == "🛠 Admin Panel")
async def admin_p(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Admin boshqaruv paneli:", reply_markup=admin_menu())

@dp.message(F.text == "🚀 Aksiya Yoqish")
async def toggle_boost(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='p_boost'") as cur:
            current = (await cur.fetchone())[0]
        new_val = 2.0 if current == 1.0 else 1.0
        await db.execute("UPDATE settings SET value=? WHERE key='p_boost'", (new_val,))
        await db.commit()
    msg = "🔥 AKSIYA YOQILDI (x2)!" if new_val == 2.0 else "❄️ Aksiya to'xtatildi (x1)."
    await message.answer(msg)

@dp.message(F.text == "📥 Matn hisobot")
async def get_text_report(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, class_name, coins FROM users ORDER BY coins DESC") as cur:
            rows = await cur.fetchall()
    report = "📊 UMUMIY NATIJALAR:\n\n" + "\n".join([f"{i+1}. {r[0]} ({r[1]}) - {r[2]}" for i, r in enumerate(rows)])
    await message.answer(report[:4000])

@dp.message(F.text == "👤 Profilim")
async def show_profile(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, class_name, coins FROM users WHERE id=?", (message.from_user.id,)) as cur:
            user = await cur.fetchone()
    if not user: return

    qr_path = f"qr_{message.from_user.id}.png"
    qr_link = f"https://t.me/EcoIM_bot?start=add_{message.from_user.id}"
    qrcode.make(qr_link).save(qr_path)

    text = f"👤 PROFIL\n\nIsm: {user[0]}\nSinf: {user[1]}\nBall: {user[2]}"
    await message.answer_photo(FSInputFile(qr_path), caption=text)
    if os.path.exists(qr_path): os.remove(qr_path)

@dp.message(F.text == "🏠 Asosiy menyu")
async def go_home(message: types.Message):
    await message.answer("Bosh sahifa", reply_markup=main_menu(message.from_user.id))

print('bot ishga tushdi!')
# --- ISHGA TUSHIRISH ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())

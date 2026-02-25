import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")
# URL твоего приложения на Render (например, https://my-casino.onrender.com)
APP_URL = os.getenv("RENDER_EXTERNAL_URL") 

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Имитация базы данных (в памяти)
# ВАЖНО: На бесплатном Render данные сбросятся при перезагрузке.
users_db = {}

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{APP_URL}/webhook")

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)

@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Играть в Gold Casino 🎰", web_app=WebAppInfo(url=f"{APP_URL}/"))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! Заходи в наше казино Standoff 2. Твой стартовый баланс: 500 Gold.", reply_markup=markup)

# API для получения данных игрока (Автологин)
@app.get("/api/get_user")
async def get_user(user_id: int, name: str):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 500, "name": name}
    return users_db[user_id]

# API для игры (крутить слот)
@app.get("/api/play")
async def play(user_id: int, bet: int):
    user = users_db.get(user_id)
    if not user or user["balance"] < bet:
        return {"error": "Недостаточно Gold!"}
    
    import random
    win_multiplier = random.choice([0, 0, 0, 0.5, 2, 5]) # Шансы
    win_amount = int(bet * win_multiplier)
    user["balance"] = user["balance"] - bet + win_amount
    
    return {"new_balance": user["balance"], "win": win_amount}

# Раздача фронтенда
app.mount("/", StaticFiles(directory="static", html=True), name="static")
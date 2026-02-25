import os
import random
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

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
        [types.InlineKeyboardButton(text="Играть в GOLD CRASH 🚀", web_app=WebAppInfo(url=f"{APP_URL}/"))]
    ])
    await message.answer(f"🚀 Добро пожаловать в Crash!\n\nТвой баланс: 500 Gold.", reply_markup=markup)

@app.get("/api/get_user")
async def get_user(user_id: int, name: str):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 1000, "name": name}
    return users_db[user_id]

@app.get("/api/crash_result")
async def crash_result(user_id: int, bet: int, cashout_multiplier: float):
    user = users_db.get(user_id)
    if not user or user["balance"] < bet:
        raise HTTPException(status_code=400, detail="Low balance")

    # Генерируем точку краша на сервере
    # Математика типичного краша
    e = 2**32
    h = random.getrandbits(32)
    crash_point = floor((100 * e - h) / (e - h)) / 100.0
    crash_point = max(1.0, crash_point) # Минимум 1.0

    user["balance"] -= bet
    
    win = 0
    success = False
    
    if cashout_multiplier <= crash_point:
        win = int(bet * cashout_multiplier)
        user["balance"] += win
        success = True
        
    return {
        "success": success,
        "win": win,
        "crash_point": crash_point,
        "new_balance": user["balance"]
    }

def floor(n): return int(n)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
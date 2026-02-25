import os
import random
import sqlite3
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

# Инициализация БД
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)''')
    conn.commit()
    conn.close()

init_db()

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Активные игры (чтобы сервер помнил точку краша для каждого юзера)
active_games = {}

def get_db_conn():
    return sqlite3.connect("database.db")

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
        [types.InlineKeyboardButton(text="Запустить GOLD CRASH 🚀", web_app=WebAppInfo(url=f"{APP_URL}/"))]
    ])
    await message.answer("Погнали в Crash!", reply_markup=markup)

@app.get("/api/get_user")
async def get_user(user_id: int, name: str):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (id, name, balance) VALUES (?, ?, ?)", (user_id, name, 1000))
        conn.commit()
        balance = 1000
    else:
        balance = row[0]
    conn.close()
    return {"balance": balance}

@app.post("/api/place_bet")
async def place_bet(user_id: int, bet: int):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    res = cursor.fetchone()
    
    if not res or res[0] < bet:
        conn.close()
        raise HTTPException(status_code=400, detail="Low balance")

    # Списываем сразу
    new_balance = res[0] - bet
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    # Генерируем секретную точку краша
    crash_point = round(max(1.0, 0.99 / (1 - random.random())**0.7), 2)
    if crash_point > 50: crash_point = 50 # Ограничим для теста
    
    active_games[user_id] = {"bet": bet, "crash_point": crash_point}
    return {"status": "ok", "new_balance": new_balance}

@app.post("/api/cashout")
async def cashout(user_id: int, current_multiplier: float):
    game = active_games.get(user_id)
    if not game:
        raise HTTPException(status_code=400, detail="No active game")
    
    crash_point = game["crash_point"]
    bet = game["bet"]
    del active_games[user_id]

    if current_multiplier <= crash_point:
        win_amount = int(bet * current_multiplier)
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (win_amount, user_id))
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return {"status": "win", "win": win_amount, "new_balance": new_balance, "crash_point": crash_point}
    else:
        # Юзер пытался обмануть или нажал слишком поздно
        return {"status": "lose", "crash_point": crash_point}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
import os, time, random, sqlite3
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

# Инициализация БД
def init_db():
    with sqlite3.connect("database.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)")
init_db()

TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

active_games = {}

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
        [types.InlineKeyboardButton(text="ВХОД В GOLD CRASH 🏆", web_app=WebAppInfo(url=f"{APP_URL}/"))]
    ])
    await message.answer(f"🏮 **Добро пожаловать, {message.from_user.first_name}!**\nГотов поднять Gold?", reply_markup=markup)

@app.get("/api/get_user")
async def get_user(user_id: int, name: str):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.execute("INSERT INTO users (id, name, balance) VALUES (?, ?, ?)", (user_id, name, 5000))
            return {"balance": 5000}
        return {"balance": row[0]}

@app.post("/api/place_bet")
async def place_bet(user_id: int, bet: int):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        if balance < bet: raise HTTPException(status_code=400)
        
        new_balance = balance - bet
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        
    crash_point = round(max(1.0, 0.98 / (1 - random.random())**0.8), 2)
    active_games[user_id] = {"start_time": time.time(), "crash_point": crash_point, "bet": bet}
    return {"status": "ok", "new_balance": new_balance, "server_time": time.time()}

@app.post("/api/cashout")
async def cashout(user_id: int):
    game = active_games.get(user_id)
    if not game: return {"status": "error"}
    
    elapsed = time.time() - game["start_time"]
    current_mult = round(1.08 ** (elapsed * 2), 2)
    
    crash_point = game["crash_point"]
    del active_games[user_id]

    if current_mult <= crash_point:
        win = int(game["bet"] * current_mult)
        with sqlite3.connect("database.db") as conn:
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (win, user_id))
            res = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()[0]
        return {"status": "win", "win": win, "new_balance": res, "mult": current_mult}
    return {"status": "lose", "crash_point": crash_point}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
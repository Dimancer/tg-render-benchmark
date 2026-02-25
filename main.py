import os, time, random, sqlite3, hashlib, hmac
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

# ─── DB ───────────────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect("database.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)")
init_db()

TOKEN   = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = Bot(token=TOKEN)
dp  = Dispatcher()
app = FastAPI()

active_games: dict = {}

# ─── Telegram initData validation ─────────────────────────────────────────────
def validate_init_data(init_data: str) -> bool:
    try:
        parsed = dict(kv.split("=", 1) for kv in init_data.split("&") if "=" in kv)
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return False
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_hash, received_hash)
    except Exception:
        return False

# ─── Crash point (house edge ~2%) ─────────────────────────────────────────────
def generate_crash_point() -> float:
    r = random.random()
    if r < 0.02:
        return 1.00
    return round(0.99 / (1.0 - r), 2)

# ─── Единая формула множителя ─────────────────────────────────────────────────
def calc_mult(elapsed: float) -> float:
    return round(1.08 ** (elapsed / 2.5), 2)

# ─── Webhook ──────────────────────────────────────────────────────────────────
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
    await message.answer(
        f"🏮 **Добро пожаловать, {message.from_user.first_name}!**\nГотов поднять Gold?",
        reply_markup=markup
    )

# ─── API ──────────────────────────────────────────────────────────────────────
@app.get("/api/get_user")
async def get_user(request: Request, user_id: int, name: str):
    init_data = request.headers.get("X-Init-Data", "")
    if APP_URL and not validate_init_data(init_data):
        raise HTTPException(status_code=403, detail="Invalid initData")
    with sqlite3.connect("database.db") as conn:
        row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO users (id, name, balance) VALUES (?, ?, ?)", (user_id, name, 5000))
            return {"balance": 5000}
        return {"balance": row[0]}

@app.post("/api/place_bet")
async def place_bet(request: Request, user_id: int, bet: int):
    init_data = request.headers.get("X-Init-Data", "")
    if APP_URL and not validate_init_data(init_data):
        raise HTTPException(status_code=403, detail="Invalid initData")
    if bet <= 0:
        raise HTTPException(status_code=400, detail="Bet must be positive")
    with sqlite3.connect("database.db") as conn:
        row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if row[0] < bet:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (row[0] - bet, user_id))

    active_games[user_id] = {
        "start_time":  time.time(),
        "crash_point": generate_crash_point(),
        "bet":         bet
    }
    return {"status": "ok", "new_balance": row[0] - bet}

# ─── Tick: сервер — единственный источник правды ──────────────────────────────
# Фронт дёргает каждые 100мс, сервер отдаёт текущий mult и elapsed.
# Если время вышло — сервер сам крашит игру и возвращает status=crashed.
@app.get("/api/tick")
async def tick(request: Request, user_id: int):
    init_data = request.headers.get("X-Init-Data", "")
    if APP_URL and not validate_init_data(init_data):
        raise HTTPException(status_code=403, detail="Invalid initData")

    game = active_games.get(user_id)
    if not game:
        return {"status": "no_game"}

    elapsed      = time.time() - game["start_time"]
    current_mult = calc_mult(elapsed)
    crash_point  = game["crash_point"]

    if current_mult >= crash_point:
        del active_games[user_id]
        return {"status": "crashed", "crash_point": crash_point}

    return {"status": "running", "mult": current_mult, "elapsed": round(elapsed, 3)}

@app.post("/api/cashout")
async def cashout(request: Request, user_id: int):
    init_data = request.headers.get("X-Init-Data", "")
    if APP_URL and not validate_init_data(init_data):
        raise HTTPException(status_code=403, detail="Invalid initData")

    game = active_games.get(user_id)
    if not game:
        return {"status": "error", "detail": "No active game"}

    elapsed      = time.time() - game["start_time"]
    current_mult = calc_mult(elapsed)
    crash_point  = game["crash_point"]
    del active_games[user_id]

    if current_mult < crash_point:
        win = int(game["bet"] * current_mult)
        with sqlite3.connect("database.db") as conn:
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (win, user_id))
            new_balance = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()[0]
        return {"status": "win", "win": win, "new_balance": new_balance, "mult": current_mult}

    return {"status": "lose", "crash_point": crash_point}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
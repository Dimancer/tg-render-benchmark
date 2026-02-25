from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import verify_telegram_init_data
from jose import jwt
from config import settings
import time

router = APIRouter()

class TelegramAuthRequest(BaseModel):
    init_data: str

@router.post("/telegram")
async def auth_telegram(body: TelegramAuthRequest):
    user_data = verify_telegram_init_data(body.init_data)
    if not user_data and not settings.DEV_MODE:
        raise HTTPException(401, {"error": "invalid_init_data", "message": "Подпись Telegram не прошла"})

    if not user_data:
        # dev fallback
        user_data = {"id": 1, "first_name": "DevUser", "username": "dev"}

    user_id    = int(user_data['id'])
    first_name = user_data.get('first_name', '')
    username   = user_data.get('username', '')

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE id=$1", user_id)
        is_new = existing is None
        if is_new:
            await conn.execute(
                "INSERT INTO users(id, username, first_name) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                user_id, username, first_name
            )
        await conn.execute("UPDATE users SET last_seen=NOW() WHERE id=$1", user_id)

    token = jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) + 86400 * 7},
        settings.SECRET_KEY, algorithm="HS256"
    )
    return {"token": token, "user_id": user_id, "name": first_name, "is_new": is_new}

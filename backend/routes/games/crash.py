
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis_client import get_redis
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet
from config import settings
import json, math
from typing import Optional

router = APIRouter()
CRASH_KEY = "crash:state"

@router.get("/state")
async def crash_state():
    redis = await get_redis()
    raw = await redis.get(CRASH_KEY)
    if not raw:
        return {"phase":"waiting","multiplier":1.0,"round_id":None,"countdown":5,"bets":[]}
    s = json.loads(raw)
    # Strip crash_at from response
    s.pop("crash_at", None)
    # Strip user_id from bets
    for b in s.get("bets", []):
        b.pop("user_id", None)
        b.pop("auto_cashout", None)
    return s

class CrashBetRequest(BaseModel):
    bet: int
    auto_cashout: Optional[float] = None

@router.post("/bet")
async def crash_bet(body: CrashBetRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.bet < settings.MIN_BET: raise HTTPException(400, {"error":"bet_too_low"})
    if body.bet > settings.MAX_BET: raise HTTPException(400, {"error":"bet_too_high"})

    redis = await get_redis()
    raw   = await redis.get(CRASH_KEY)
    if not raw:
        raise HTTPException(400, {"error":"wrong_phase","message":"Игра не запущена"})
    s = json.loads(raw)
    if s["phase"] != "waiting":
        raise HTTPException(400, {"error":"wrong_phase","message":"Ставки принимаются только в фазе ожидания"})

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await deduct_bet(conn, uid, body.bet, "crash")
            row = await conn.fetchrow("SELECT first_name FROM users WHERE id=$1", uid)

    s["bets"].append({
        "user_id": uid,
        "name":    row["first_name"] if row else "User",
        "bet":     body.bet,
        "cashout": None,
        "auto_cashout": body.auto_cashout
    })
    await redis.set(CRASH_KEY, json.dumps(s))
    return {"ok": True, "round_id": s["round_id"]}

@router.post("/cashout")
async def crash_cashout(request: Request):
    uid   = await get_current_user_id(request)
    redis = await get_redis()
    raw   = await redis.get(CRASH_KEY)
    if not raw:
        raise HTTPException(400, {"error":"game_not_found"})
    s = json.loads(raw)
    if s["phase"] != "running":
        raise HTTPException(400, {"error":"wrong_phase"})

    bet_entry = next((b for b in s["bets"] if b["user_id"] == uid and b["cashout"] is None), None)
    if not bet_entry:
        raise HTTPException(400, {"error":"game_not_found","message":"Активная ставка не найдена"})

    mult   = s["multiplier"]
    payout = math.floor(bet_entry["bet"] * mult * (1 - settings.HOUSE_EDGE))
    bet_entry["cashout"] = mult
    await redis.set(CRASH_KEY, json.dumps(s))

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE users SET gold=gold+$1 WHERE id=$2", payout, uid)
            await conn.execute(
                "INSERT INTO transactions(user_id,type,amount,description,game) VALUES($1,'win',$2,$3,'crash')",
                uid, payout, f"Crash cashout x{mult}"
            )

    return {"ok": True, "payout": payout, "multiplier": mult}

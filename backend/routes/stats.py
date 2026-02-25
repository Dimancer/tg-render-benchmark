from fastapi import APIRouter, Query
from database import get_pool
from redis_client import get_redis
import json

router = APIRouter()

@router.get("/lobby")
async def lobby_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        jackpot_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(bet_amount),0) AS total FROM bets WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        jackpot = int(jackpot_row["total"] * 0.02)
        online_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM users WHERE last_seen > NOW() - INTERVAL '15 minutes'")
    return {"online": int(online_row["cnt"]), "jackpot": jackpot}

@router.get("/online")
async def online_stats():
    redis = await get_redis()
    games = ["crash", "roulette", "slots", "coin", "mines", "dice"]
    result = {}
    for g in games:
        cnt = await redis.scard(f"online:{g}")
        result[g] = cnt
    return result

@router.get("/leaderboard")
async def leaderboard(type: str = Query("profit", regex="^(profit|wagered)$")):
    field = "total_profit" if type == "profit" else "total_wagered"
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT first_name AS name, {field} AS value, games_played AS games "
            f"FROM users ORDER BY {field} DESC LIMIT 10"
        )
    return {"players": [dict(r) for r in rows]}

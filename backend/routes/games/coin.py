
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet, credit_win, record_game
from config import settings
import secrets, math

router = APIRouter()

class CoinRequest(BaseModel):
    bet: int
    side: str   # "heads" | "tails"

@router.post("/play")
async def coin_play(body: CoinRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.bet < settings.MIN_BET:
        raise HTTPException(400, {"error": "bet_too_low"})
    if body.bet > settings.MAX_BET:
        raise HTTPException(400, {"error": "bet_too_high"})
    if body.side not in ("heads", "tails"):
        raise HTTPException(400, {"error": "invalid_side"})

    result = "heads" if secrets.randbelow(2) == 0 else "tails"
    won    = result == body.side
    payout = math.floor(body.bet * 2 * (1 - settings.HOUSE_EDGE)) if won else 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await deduct_bet(conn, uid, body.bet, "coin")
            await credit_win(conn, uid, payout, "coin")
            await record_game(conn, uid, "coin", body.bet, payout, 2.0 if won else 0.0)

    return {"result": result, "won": won, "payout": payout}

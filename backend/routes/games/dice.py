
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet, credit_win, record_game
from config import settings
import secrets, math

router = APIRouter()

MULTIPLIERS = {2:36,3:18,4:12,5:9,6:7.2,7:6,8:7.2,9:9,10:12,11:18,12:36}

class DiceRequest(BaseModel):
    bet: int
    chosen: int   # 2..12

@router.post("/play")
async def dice_play(body: DiceRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.bet < settings.MIN_BET:   raise HTTPException(400, {"error":"bet_too_low"})
    if body.bet > settings.MAX_BET:   raise HTTPException(400, {"error":"bet_too_high"})
    if body.chosen not in MULTIPLIERS: raise HTTPException(400, {"error":"invalid_chosen"})

    die1 = secrets.randbelow(6) + 1
    die2 = secrets.randbelow(6) + 1
    total = die1 + die2
    won   = total == body.chosen
    mult  = MULTIPLIERS[body.chosen]
    payout = math.floor(body.bet * mult * (1 - settings.HOUSE_EDGE)) if won else 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await deduct_bet(conn, uid, body.bet, "dice")
            await credit_win(conn, uid, payout, "dice")
            await record_game(conn, uid, "dice", body.bet, payout, mult if won else 0.0,
                              {"die1": die1, "die2": die2})

    return {"die1": die1, "die2": die2, "sum": total, "won": won, "payout": payout}

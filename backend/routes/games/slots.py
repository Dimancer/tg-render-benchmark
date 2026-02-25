
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet, credit_win, record_game
from config import settings
import secrets, math
from collections import Counter

router = APIRouter()

SYMBOLS  = ['🎯','⭐','💎','🔫','💣','🪙','🔪','💀']
WEIGHTS  = [2,   4,   5,   8,   8,   12,  14,  15]
TOTAL_W  = sum(WEIGHTS)
PAYOUTS_5 = {'🎯':500,'⭐':200,'💎':100,'🔫':50,'💣':25}

def weighted_choice():
    r = secrets.randbelow(TOTAL_W)
    acc = 0
    for sym, w in zip(SYMBOLS, WEIGHTS):
        acc += w
        if r < acc:
            return sym

class SlotsRequest(BaseModel):
    bet: int

@router.post("/play")
async def slots_play(body: SlotsRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.bet < settings.MIN_BET: raise HTTPException(400, {"error":"bet_too_low"})
    if body.bet > settings.MAX_BET: raise HTTPException(400, {"error":"bet_too_high"})

    reels = [weighted_choice() for _ in range(5)]
    counts = Counter(reels)
    best_sym, max_match = counts.most_common(1)[0]

    if max_match == 5 and best_sym in PAYOUTS_5:
        multiplier = PAYOUTS_5[best_sym]
        combo = f"5x{best_sym}"
    elif max_match == 4:
        multiplier = 15
        combo = f"4x{best_sym}"
    elif max_match == 3:
        multiplier = 5
        combo = f"3x{best_sym}"
    else:
        multiplier = 0
        combo = ""

    payout = math.floor(body.bet * multiplier * (1 - settings.HOUSE_EDGE)) if multiplier > 0 else 0
    won    = payout > 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await deduct_bet(conn, uid, body.bet, "slots")
            await credit_win(conn, uid, payout, "slots")
            await record_game(conn, uid, "slots", body.bet, payout, float(multiplier),
                              {"reels": reels, "combo": combo})

    return {"reels": reels, "won": won, "payout": payout, "combo": combo}

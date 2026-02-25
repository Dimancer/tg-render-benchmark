
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet, credit_win, record_game
from config import settings
import secrets, math
from typing import Dict

router = APIRouter()

RED_NUMS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

class RouletteRequest(BaseModel):
    bets: Dict[str, int]

@router.post("/play")
async def roulette_play(body: RouletteRequest, request: Request):
    uid = await get_current_user_id(request)
    total_bet = sum(body.bets.values())
    if total_bet < settings.MIN_BET:  raise HTTPException(400, {"error":"bet_too_low"})
    if total_bet > settings.MAX_BET:  raise HTTPException(400, {"error":"bet_too_high"})

    number = secrets.randbelow(37)
    if number == 0:      color = "green"
    elif number in RED_NUMS: color = "red"
    else:                color = "black"

    HE = 1 - settings.HOUSE_EDGE
    total_payout = 0
    for key, amount in body.bets.items():
        if key.startswith("num_"):
            n = int(key.split("_")[1])
            if n == number:
                total_payout += math.floor(amount * 35 * HE)
        elif key == "cat_red"   and color == "red":    total_payout += math.floor(amount * 2 * HE)
        elif key == "cat_black" and color == "black":  total_payout += math.floor(amount * 2 * HE)
        elif key == "cat_green" and color == "green":  total_payout += math.floor(amount * 14 * HE)
        elif key == "cat_odd"   and number % 2 == 1 and number != 0: total_payout += math.floor(amount * 2 * HE)
        elif key == "cat_even"  and number % 2 == 0 and number != 0: total_payout += math.floor(amount * 2 * HE)
        elif key == "cat_half1" and 1 <= number <= 18: total_payout += math.floor(amount * 2 * HE)
        elif key == "cat_half2" and 19 <= number <= 36: total_payout += math.floor(amount * 2 * HE)

    won  = total_payout > 0
    mult = round(total_payout / total_bet, 2) if won else 0.0

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await deduct_bet(conn, uid, total_bet, "roulette")
            await credit_win(conn, uid, total_payout, "roulette")
            await record_game(conn, uid, "roulette", total_bet, total_payout, mult,
                              {"number": number, "color": color})

    return {"number": number, "color": color, "won": won, "payout": total_payout}

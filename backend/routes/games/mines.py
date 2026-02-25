
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from services.wallet_service import deduct_bet, credit_win, record_game
from config import settings
import secrets, math, uuid, json
from math import comb

router = APIRouter()

def calc_multiplier(total_safe: int, found: int, total: int = 25, mine_count: int = 0) -> float:
    prob = 1.0
    for i in range(found):
        prob *= (total_safe - i) / (total - i)
    return round((1 / prob) * (1 - settings.HOUSE_EDGE), 2)

class MinesStartRequest(BaseModel):
    bet: int
    mines: int   # 1..24

class MinesRevealRequest(BaseModel):
    game_id: str
    cell: int    # 0..24

class MinesCashoutRequest(BaseModel):
    game_id: str

@router.post("/start")
async def mines_start(body: MinesStartRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.bet < settings.MIN_BET:  raise HTTPException(400, {"error":"bet_too_low"})
    if body.bet > settings.MAX_BET:  raise HTTPException(400, {"error":"bet_too_high"})
    if not (1 <= body.mines <= 24):  raise HTTPException(400, {"error":"invalid_mines"})

    board = ['safe'] * 25
    mine_positions = random_sample(25, body.mines)
    for pos in mine_positions:
        board[pos] = 'mine'

    session_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Close any open session
            await conn.execute(
                "UPDATE mines_sessions SET cashed_out=TRUE WHERE user_id=$1 AND cashed_out=FALSE",
                uid
            )
            await deduct_bet(conn, uid, body.bet, "mines")
            await conn.execute(
                "INSERT INTO mines_sessions(id,user_id,bet,mine_count,board,revealed) VALUES($1,$2,$3,$4,$5,$6)",
                session_id, uid, body.bet, body.mines, json.dumps(board), json.dumps([])
            )
    return {"game_id": session_id}

@router.post("/reveal")
async def mines_reveal(body: MinesRevealRequest, request: Request):
    uid = await get_current_user_id(request)
    if not (0 <= body.cell <= 24):
        raise HTTPException(400, {"error":"invalid_cell"})

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            sess = await conn.fetchrow(
                "SELECT * FROM mines_sessions WHERE id=$1 FOR UPDATE", body.game_id
            )
            if not sess:              raise HTTPException(404, {"error":"game_not_found"})
            if sess["user_id"] != uid: raise HTTPException(403, {"error":"forbidden"})
            if sess["cashed_out"]:    raise HTTPException(400, {"error":"session_expired"})

            board    = json.loads(sess["board"])
            revealed = json.loads(sess["revealed"])

            if body.cell in revealed:
                raise HTTPException(400, {"error":"already_revealed"})

            revealed.append(body.cell)
            cell_type = board[body.cell]

            if cell_type == "mine":
                await conn.execute(
                    "UPDATE mines_sessions SET revealed=$1, cashed_out=TRUE WHERE id=$2",
                    json.dumps(revealed), body.game_id
                )
                await record_game(conn, uid, "mines", sess["bet"], 0, 0.0,
                                  {"mines": sess["mine_count"], "cells": len(revealed)})
                return {"safe": False, "symbol": "💣", "game_over": True, "board": board}

            await conn.execute(
                "UPDATE mines_sessions SET revealed=$1 WHERE id=$2",
                json.dumps(revealed), body.game_id
            )
            total_safe = 25 - sess["mine_count"]
            found = len(revealed)
            mult  = calc_multiplier(total_safe, found, 25, sess["mine_count"])

    return {"safe": True, "symbol": "💎", "multiplier": mult, "game_over": False, "board": None}

@router.post("/cashout")
async def mines_cashout(body: MinesCashoutRequest, request: Request):
    uid = await get_current_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            sess = await conn.fetchrow(
                "SELECT * FROM mines_sessions WHERE id=$1 FOR UPDATE", body.game_id
            )
            if not sess:               raise HTTPException(404, {"error":"game_not_found"})
            if sess["user_id"] != uid:  raise HTTPException(403, {"error":"forbidden"})
            if sess["cashed_out"]:      raise HTTPException(400, {"error":"session_expired"})

            board    = json.loads(sess["board"])
            revealed = json.loads(sess["revealed"])
            if not revealed:
                raise HTTPException(400, {"error":"no_cells_revealed"})

            total_safe = 25 - sess["mine_count"]
            mult   = calc_multiplier(total_safe, len(revealed), 25, sess["mine_count"])
            payout = math.floor(sess["bet"] * mult)

            await conn.execute(
                "UPDATE mines_sessions SET cashed_out=TRUE WHERE id=$1", body.game_id
            )
            await credit_win(conn, uid, payout, "mines")
            await record_game(conn, uid, "mines", sess["bet"], payout, mult,
                              {"mines": sess["mine_count"], "cells": len(revealed)})

    return {"payout": payout, "multiplier": mult, "board": board}

def random_sample(n: int, k: int) -> list:
    pool = list(range(n))
    result = []
    for i in range(k):
        idx = secrets.randbelow(len(pool))
        result.append(pool.pop(idx))
    return result

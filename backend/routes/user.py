from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from database import get_pool
from middleware.tg_auth import get_current_user_id
from config import settings

router = APIRouter()

@router.get("/balance")
async def get_balance(request: Request):
    uid = await get_current_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT gold FROM users WHERE id=$1", uid)
        if not row:
            raise HTTPException(404, {"error": "user_not_found"})
    return {"gold": row["gold"]}

@router.get("/profile")
async def get_profile(request: Request):
    uid = await get_current_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT first_name, xp, games_played, games_won, total_profit FROM users WHERE id=$1", uid
        )
        if not row:
            raise HTTPException(404, {"error": "user_not_found"})
    level = min(6, row["xp"] // 100)
    return {
        "name":   row["first_name"],
        "xp":     row["xp"],
        "level":  level,
        "games":  row["games_played"],
        "wins":   row["games_won"],
        "profit": row["total_profit"]
    }

@router.get("/transactions")
async def get_transactions(request: Request, limit: int = Query(10, le=50)):
    uid = await get_current_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT type, amount, description, game, created_at FROM transactions "
            "WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
            uid, limit
        )
    return {"transactions": [dict(r) for r in rows]}

class WithdrawRequest(BaseModel):
    nick: str
    amount: int

@router.post("/withdraw")
async def withdraw(body: WithdrawRequest, request: Request):
    uid = await get_current_user_id(request)
    if body.amount < settings.WITHDRAW_MIN:
        raise HTTPException(400, {"error": "amount_too_low", "message": f"Минимум {settings.WITHDRAW_MIN} Gold"})

    fee        = int(body.amount * settings.WITHDRAW_FEE)
    net_amount = body.amount - fee

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT gold FROM users WHERE id=$1 FOR UPDATE", uid)
            if not row or row["gold"] < body.amount:
                raise HTTPException(400, {"error": "insufficient_funds", "message": "Недостаточно Gold"})
            await conn.execute("UPDATE users SET gold = gold - $1 WHERE id=$2", body.amount, uid)
            wid = await conn.fetchval(
                "INSERT INTO withdrawals(user_id, amount, fee, net_amount, so2_nick) VALUES($1,$2,$3,$4,$5) RETURNING id",
                uid, body.amount, fee, net_amount, body.nick
            )
            await conn.execute(
                "INSERT INTO transactions(user_id,type,amount,description) VALUES($1,'withdraw',$2,$3)",
                uid, -body.amount, f"Вывод → {body.nick}"
            )
    return {"ok": True, "withdrawal_id": wid}

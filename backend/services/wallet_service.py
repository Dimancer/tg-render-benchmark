import asyncpg
import json

async def deduct_bet(conn: asyncpg.Connection, user_id: int, bet: int, game: str):
    row = await conn.fetchrow("SELECT gold FROM users WHERE id=$1 FOR UPDATE", user_id)
    if not row or row["gold"] < bet:
        raise ValueError("insufficient_funds")
    await conn.execute("UPDATE users SET gold = gold - $1 WHERE id=$2", bet, user_id)
    await conn.execute(
        "INSERT INTO transactions(user_id,type,amount,description,game) VALUES($1,'bet',$2,$3,$4)",
        user_id, -bet, f"Ставка · {game}", game
    )

async def credit_win(conn: asyncpg.Connection, user_id: int, payout: int, game: str):
    if payout <= 0:
        return
    await conn.execute("UPDATE users SET gold = gold + $1 WHERE id=$2", payout, user_id)
    await conn.execute(
        "INSERT INTO transactions(user_id,type,amount,description,game) VALUES($1,'win',$2,$3,$4)",
        user_id, payout, f"Победа · {game}", game
    )

async def record_game(conn: asyncpg.Connection, user_id: int, game: str,
                      bet: int, payout: int, multiplier: float, meta: dict = None):
    won = payout > 0
    await conn.execute(
        "INSERT INTO bets(user_id,game,bet_amount,payout,multiplier,meta) VALUES($1,$2,$3,$4,$5,$6)",
        user_id, game, bet, payout, multiplier, json.dumps(meta or {})
    )
    await conn.execute(
        """
        UPDATE users SET
            games_played  = games_played + 1,
            games_won     = games_won + $1,
            total_wagered = total_wagered + $2,
            total_profit  = total_profit + $3,
            xp            = xp + 8
        WHERE id=$4
        """,
        1 if won else 0, bet, payout - bet, user_id
    )

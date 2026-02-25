
import asyncio, json, time, uuid, hmac, hashlib, math, os
from redis_client import get_redis
from database import get_pool
from config import settings

CRASH_KEY = "crash:state"

def generate_crash_point() -> float:
    seed = str(uuid.uuid4())
    h = hmac.new(seed.encode(), os.urandom(32), hashlib.sha256).hexdigest()
    val = int(h[:8], 16)
    return max(1.0, round((2**32 / (val + 1)) * (1 - settings.HOUSE_EDGE), 2))

async def crash_loop():
    redis = await get_redis()
    pool  = await get_pool()

    while True:
        try:
            round_id  = str(uuid.uuid4())
            crash_at  = generate_crash_point()
            state = {
                "phase": "waiting", "multiplier": 1.0, "round_id": round_id,
                "crash_at": crash_at, "countdown": 5, "bets": []
            }
            await redis.set(CRASH_KEY, json.dumps(state))

            # ── Waiting phase (5 sec) ──────────────────────────────
            for i in range(50):
                await asyncio.sleep(0.1)
                raw = await redis.get(CRASH_KEY)
                s   = json.loads(raw)
                s["countdown"] = round(5 - i * 0.1, 1)
                await redis.set(CRASH_KEY, json.dumps(s))

            # ── Running phase ──────────────────────────────────────
            raw = await redis.get(CRASH_KEY)
            s   = json.loads(raw)
            s["phase"] = "running"
            s["countdown"] = None
            await redis.set(CRASH_KEY, json.dumps(s))

            start_ms  = time.time() * 1000
            crashed   = False
            while not crashed:
                await asyncio.sleep(0.1)
                t_ms = time.time() * 1000 - start_ms
                mult = round(math.exp(0.00006 * t_ms), 2)

                raw = await redis.get(CRASH_KEY)
                s   = json.loads(raw)
                s["multiplier"] = mult

                # Auto-cashout
                for bet in s["bets"]:
                    ac = bet.get("auto_cashout")
                    if ac and bet.get("cashout") is None and mult >= ac:
                        payout = math.floor(bet["bet"] * ac * (1 - settings.HOUSE_EDGE))
                        bet["cashout"] = ac
                        async with pool.acquire() as conn:
                            async with conn.transaction():
                                await conn.execute(
                                    "UPDATE users SET gold=gold+$1 WHERE id=$2", payout, bet["user_id"]
                                )
                                await conn.execute(
                                    "INSERT INTO transactions(user_id,type,amount,description,game) "
                                    "VALUES($1,'win',$2,$3,'crash')",
                                    bet["user_id"], payout, f"Crash auto-cashout x{ac}"
                                )

                if mult >= s["crash_at"]:
                    crashed = True
                    s["phase"] = "crashed"
                    s["multiplier"] = s["crash_at"]
                    # Record losses
                    async with pool.acquire() as conn:
                        for bet in s["bets"]:
                            payout = 0 if bet.get("cashout") is None else math.floor(
                                bet["bet"] * bet["cashout"] * (1 - settings.HOUSE_EDGE))
                            won = bet.get("cashout") is not None
                            async with conn.transaction():
                                await conn.execute(
                                    "INSERT INTO bets(user_id,game,bet_amount,payout,multiplier,meta) "
                                    "VALUES($1,'crash',$2,$3,$4,$5)",
                                    bet["user_id"], bet["bet"], payout if won else 0,
                                    bet.get("cashout") or 0.0, json.dumps({"round": round_id})
                                )
                                await conn.execute(
                                    "UPDATE users SET games_played=games_played+1,"
                                    "games_won=games_won+$1, total_wagered=total_wagered+$2,"
                                    "total_profit=total_profit+$3, xp=xp+8 WHERE id=$4",
                                    1 if won else 0, bet["bet"],
                                    (payout if won else 0) - bet["bet"], bet["user_id"]
                                )

                await redis.set(CRASH_KEY, json.dumps(s))

            # ── Post-crash pause 3s ────────────────────────────────
            await asyncio.sleep(3)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[crash_worker] error: {e}")
            await asyncio.sleep(2)

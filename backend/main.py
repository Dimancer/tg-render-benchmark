
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio

from database import create_tables
from redis_client import get_redis
from config import settings
from routes import auth, user, stats
from routes.games import coin, dice, roulette, slots, crash, mines
from services.crash_worker import crash_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    redis = await get_redis()
    await redis.ping()
    task = asyncio.create_task(crash_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="SO2 Casino API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (simple Redis-based)
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    uid = request.headers.get("X-User-Id")
    if uid and request.url.path.startswith("/api/"):
        redis = await get_redis()
        key   = f"rl:{uid}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > 30:
            return JSONResponse({"error": "rate_limited", "message": "Слишком много запросов"}, status_code=429)
    return await call_next(request)

app.include_router(auth.router,     prefix="/api/auth",              tags=["auth"])
app.include_router(user.router,     prefix="/api/user",              tags=["user"])
app.include_router(stats.router,    prefix="/api/stats",             tags=["stats"])
app.include_router(coin.router,     prefix="/api/games/coin",        tags=["games"])
app.include_router(dice.router,     prefix="/api/games/dice",        tags=["games"])
app.include_router(roulette.router, prefix="/api/games/roulette",    tags=["games"])
app.include_router(slots.router,    prefix="/api/games/slots",       tags=["games"])
app.include_router(crash.router,    prefix="/api/games/crash",       tags=["games"])
app.include_router(mines.router,    prefix="/api/games/mines",       tags=["games"])

@app.get("/health")
async def health():
    return {"status": "ok"}

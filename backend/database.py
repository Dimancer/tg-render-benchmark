import asyncpg
from config import settings

_pool: asyncpg.Pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    return _pool

async def create_tables():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id            BIGINT PRIMARY KEY,
                username      VARCHAR(64),
                first_name    VARCHAR(64),
                gold          BIGINT DEFAULT 5000,
                xp            INT DEFAULT 0,
                games_played  INT DEFAULT 0,
                games_won     INT DEFAULT 0,
                total_wagered BIGINT DEFAULT 0,
                total_profit  BIGINT DEFAULT 0,
                created_at    TIMESTAMP DEFAULT NOW(),
                last_seen     TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT REFERENCES users(id),
                type        VARCHAR(32),
                amount      BIGINT,
                description VARCHAR(128),
                game        VARCHAR(32),
                created_at  TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS bets (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT REFERENCES users(id),
                game        VARCHAR(32),
                bet_amount  BIGINT,
                payout      BIGINT,
                multiplier  DECIMAL(10,2),
                meta        JSONB,
                created_at  TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS mines_sessions (
                id          VARCHAR(64) PRIMARY KEY,
                user_id     BIGINT REFERENCES users(id),
                bet         BIGINT,
                mine_count  INT,
                board       JSONB,
                revealed    JSONB DEFAULT '[]',
                cashed_out  BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS withdrawals (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT REFERENCES users(id),
                amount      BIGINT,
                fee         BIGINT,
                net_amount  BIGINT,
                so2_nick    VARCHAR(64),
                status      VARCHAR(16) DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT NOW()
            );
        ''')

-- schema.sql

CREATE TABLE users (
  id            BIGINT PRIMARY KEY,          -- telegram_id
  username      TEXT,
  first_name    TEXT,
  balance       NUMERIC(18,2) DEFAULT 0,
  bonus_balance NUMERIC(18,2) DEFAULT 0,
  wager_left    NUMERIC(18,2) DEFAULT 0,     -- остаток отыгровки
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE rounds (
  id          SERIAL PRIMARY KEY,
  crash_at    NUMERIC(6,2) NOT NULL,         -- точка крэша (напр. 2.45x)
  seed        TEXT NOT NULL,                 -- хэш для provably fair
  started_at  TIMESTAMPTZ DEFAULT NOW(),
  ended_at    TIMESTAMPTZ
);

CREATE TABLE bets (
  id          SERIAL PRIMARY KEY,
  user_id     BIGINT REFERENCES users(id),
  round_id    INT REFERENCES rounds(id),
  amount      NUMERIC(18,2) NOT NULL,
  cashout_at  NUMERIC(6,2),                  -- на каком множителе вышел
  profit      NUMERIC(18,2),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bonuses (
  id          SERIAL PRIMARY KEY,
  user_id     BIGINT REFERENCES users(id),
  type        TEXT NOT NULL,                 -- 'welcome', 'deposit', 'daily'
  amount      NUMERIC(18,2) NOT NULL,
  wager_req   NUMERIC(18,2) NOT NULL,        -- сумма для отыгровки
  wager_done  NUMERIC(18,2) DEFAULT 0,
  expires_at  TIMESTAMPTZ,
  claimed     BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

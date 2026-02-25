// routes/bonus.js
router.post('/claim', authMiddleware, async (req, res) => {
  const { type } = req.body;
  const userId = req.telegramUser.id;

  const bonusMap = {
    welcome: { amount: 100, wager_multiplier: 10 },
    daily:   { amount: 20,  wager_multiplier: 5  },
  };

  const bonus = bonusMap[type];
  if (!bonus) return res.status(400).json({ error: 'Unknown bonus' });

  const wagerReq = bonus.amount * bonus.wager_multiplier;

  await db.query(
    `INSERT INTO bonuses (user_id, type, amount, wager_req, expires_at)
     VALUES ($1, $2, $3, $4, NOW() + INTERVAL '7 days')`,
    [userId, type, bonus.amount, wagerReq]
  );

  await db.query(
    `UPDATE users SET bonus_balance = bonus_balance + $1, wager_left = wager_left + $2
     WHERE id = $3`,
    [bonus.amount, wagerReq, userId]
  );

  res.json({ success: true, bonus });
});

// При каждой ставке обновляем вейджер:
async function processWager(userId, betAmount, db) {
  await db.query(
    `UPDATE users 
     SET wager_left = GREATEST(0, wager_left - $1)
     WHERE id = $2`,
    [betAmount, userId]
  );

  // Если вейджер закрыт — конвертируем bonus_balance в основной баланс
  const { rows } = await db.query(
    'SELECT wager_left, bonus_balance FROM users WHERE id = $1',
    [userId]
  );
  if (rows[0].wager_left === 0 && rows[0].bonus_balance > 0) {
    await db.query(
      `UPDATE users SET balance = balance + bonus_balance, bonus_balance = 0 WHERE id = $1`,
      [userId]
    );
  }
}

// ws/gameLoop.js
const crypto = require('crypto');
const { WebSocketServer } = require('ws');

function generateCrashPoint(seed) {
  const hash = crypto.createHash('sha256').update(seed).digest('hex');
  const h = parseInt(hash.slice(0, 8), 16);
  const e = Math.pow(2, 32);
  // Формула house edge 3%
  if (h % 33 === 0) return 1.0; // мгновенный крэш (1 из 33)
  return Math.floor((100 * e) / (e - h)) / 100;
}

class CrashGame {
  constructor(wss, db) {
    this.wss = wss;
    this.db = db;
    this.multiplier = 1.0;
    this.bets = new Map(); // userId -> { amount, cashedOut }
  }

  broadcast(data) {
    const msg = JSON.stringify(data);
    this.wss.clients.forEach(c => {
      if (c.readyState === 1) c.send(msg);
    });
  }

  async startRound() {
    const seed = crypto.randomBytes(16).toString('hex');
    const crashAt = generateCrashPoint(seed);

    // Сохраняем раунд в БД
    const { rows } = await this.db.query(
      'INSERT INTO rounds (crash_at, seed) VALUES ($1, $2) RETURNING id',
      [crashAt, seed]
    );
    this.roundId = rows[0].id;
    this.multiplier = 1.0;
    this.bets.clear();

    this.broadcast({ type: 'ROUND_START', roundId: this.roundId });

    // Тик каждые 100ms
    this.interval = setInterval(() => {
      this.multiplier = parseFloat((this.multiplier * 1.0058).toFixed(2));
      this.broadcast({ type: 'TICK', multiplier: this.multiplier });

      if (this.multiplier >= crashAt) {
        clearInterval(this.interval);
        this.broadcast({ type: 'CRASH', crashAt });
        this.endRound(crashAt);
      }
    }, 100);
  }

  async endRound(crashAt) {
    // Обрабатываем проигравшие ставки, обновляем wager
    // ...
    setTimeout(() => this.startRound(), 5000); // пауза 5 сек
  }
}

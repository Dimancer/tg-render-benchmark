require('dotenv').config();
const express = require('express');
const cors = require('cors');
const http = require('http');
const { WebSocketServer } = require('ws');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// ─── Crash Game Logic ───────────────────────────────────────────
function generateCrashPoint(seed) {
  const hash = crypto.createHash('sha256').update(seed).digest('hex');
  const h = parseInt(hash.slice(0, 8), 16);
  const e = Math.pow(2, 32);
  if (h % 33 === 0) return 1.0;
  return Math.max(1.0, Math.floor((100 * e) / (e - h)) / 100);
}

let gameState = {
  status: 'waiting', // waiting | running | crashed
  multiplier: 1.0,
  crashAt: 1.0,
  roundId: 0,
};

function broadcast(data) {
  const msg = JSON.stringify(data);
  wss.clients.forEach(c => {
    if (c.readyState === 1) c.send(msg);
  });
}

async function runRound() {
  const seed = crypto.randomBytes(16).toString('hex');
  const crashAt = generateCrashPoint(seed);
  gameState = { status: 'waiting', multiplier: 1.0, crashAt, roundId: gameState.roundId + 1 };
  broadcast({ type: 'WAITING', roundId: gameState.roundId });

  await new Promise(r => setTimeout(r, 5000)); // 5 сек ожидания

  gameState.status = 'running';
  gameState.multiplier = 1.0;
  broadcast({ type: 'ROUND_START', roundId: gameState.roundId });

  const interval = setInterval(() => {
    gameState.multiplier = parseFloat((gameState.multiplier * 1.0058).toFixed(2));
    broadcast({ type: 'TICK', multiplier: gameState.multiplier });

    if (gameState.multiplier >= crashAt) {
      clearInterval(interval);
      gameState.status = 'crashed';
      broadcast({ type: 'CRASH', crashAt });
      setTimeout(runRound, 3000);
    }
  }, 100);
}

// ─── Auth ────────────────────────────────────────────────────────
app.post('/api/auth/telegram', (req, res) => {
  const { initData } = req.body;
  if (!initData) return res.status(400).json({ error: 'No initData' });

  try {
    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    params.delete('hash');

    const dataCheckString = [...params.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join('\n');

    const secretKey = crypto
      .createHmac('sha256', 'WebAppData')
      .update(process.env.BOT_TOKEN || 'test')
      .digest();

    const expectedHash = crypto
      .createHmac('sha256', secretKey)
      .update(dataCheckString)
      .digest('hex');

    // В dev режиме пропускаем проверку
    if (process.env.BOT_TOKEN && expectedHash !== hash) {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    const userRaw = params.get('user');
    const user = userRaw ? JSON.parse(userRaw) : { id: 0, first_name: 'Dev' };
    const jwt = require('jsonwebtoken');
    const token = jwt.sign(user, process.env.JWT_SECRET || 'devsecret', { expiresIn: '24h' });

    res.json({ token, user });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─── Game State ──────────────────────────────────────────────────
app.get('/api/state', (req, res) => {
  res.json(gameState);
});

// ─── Health ──────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ ok: true }));

// ─── WebSocket ───────────────────────────────────────────────────
wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'STATE', state: gameState }));
});

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
  runRound();
});

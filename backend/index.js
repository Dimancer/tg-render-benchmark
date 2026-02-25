import express from 'express';
import cors from 'cors';

const app = express();
app.use(cors());
app.use(express.json());

// Ping endpoint — базовый тест латентности
app.get('/ping', (req, res) => {
  res.json({ 
    ok: true, 
    ts: Date.now(),
    uptime: process.uptime()
  });
});

// Echo endpoint — тест с payload
app.post('/echo', (req, res) => {
  const received = Date.now();
  res.json({
    ok: true,
    received,
    payload_size: JSON.stringify(req.body).length,
    uptime: process.uptime()
  });
});

// Heavy endpoint — тест CPU нагрузки
app.get('/cpu-stress', (req, res) => {
  const start = Date.now();
  let result = 0;
  for (let i = 0; i < 1_000_000; i++) result += Math.sqrt(i);
  res.json({ 
    ok: true, 
    duration_ms: Date.now() - start,
    result: result.toFixed(2)
  });
});

// Info endpoint
app.get('/info', (req, res) => {
  res.json({
    node_version: process.version,
    platform: process.platform,
    memory_mb: (process.memoryUsage().heapUsed / 1024 / 1024).toFixed(2),
    uptime_s: process.uptime().toFixed(1)
  });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Benchmark backend on :${PORT}`));

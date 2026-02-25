import { useState, useEffect } from 'react';

const API = import.meta.env.VITE_API_URL; // https://your-backend.onrender.com

const TESTS = [
  { id: 'cold_start', label: '🧊 Cold Start / Ping', endpoint: '/ping', method: 'GET' },
  { id: 'echo_1kb',   label: '📦 Echo 1KB',          endpoint: '/echo',  method: 'POST', body: { data: 'x'.repeat(1000) } },
  { id: 'cpu',        label: '⚙️ CPU Stress',         endpoint: '/cpu-stress', method: 'GET' },
  { id: 'info',       label: 'ℹ️ Server Info',        endpoint: '/info',  method: 'GET' },
];

function msColor(ms) {
  if (ms < 200) return '#4CAF50';
  if (ms < 800) return '#FFC107';
  return '#F44336';
}

export default function App() {
  const [results, setResults] = useState({});
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState([]);

  // Telegram WebApp init
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }
  }, []);

  const runTest = async (test) => {
    const start = Date.now();
    try {
      const opts = {
        method: test.method,
        headers: { 'Content-Type': 'application/json' },
        ...(test.body ? { body: JSON.stringify(test.body) } : {})
      };
      const res = await fetch(`${API}${test.endpoint}`, opts);
      const data = await res.json();
      const latency = Date.now() - start;
      return { ok: true, latency, data };
    } catch (e) {
      return { ok: false, latency: Date.now() - start, error: e.message };
    }
  };

  const runAll = async () => {
    setRunning(true);
    setResults({});
    setLog([]);

    for (const test of TESTS) {
      setLog(l => [...l, `▶ Running: ${test.label}...`]);
      const result = await runTest(test);
      setResults(r => ({ ...r, [test.id]: result }));
      setLog(l => [...l, `✅ ${test.label}: ${result.latency}ms`]);
      // Небольшая пауза между тестами
      await new Promise(r => setTimeout(r, 300));
    }
    setRunning(false);
  };

  // Повторный ping 5 раз для замера стабильности
  const runStabilityTest = async () => {
    setRunning(true);
    setLog([]);
    const times = [];
    for (let i = 0; i < 5; i++) {
      const r = await runTest(TESTS[0]);
      times.push(r.latency);
      setLog(l => [...l, `Ping #${i+1}: ${r.latency}ms`]);
      await new Promise(r => setTimeout(r, 500));
    }
    const avg = (times.reduce((a,b)=>a+b,0)/times.length).toFixed(0);
    const min = Math.min(...times);
    const max = Math.max(...times);
    setLog(l => [...l, `📊 avg: ${avg}ms | min: ${min}ms | max: ${max}ms`]);
    setRunning(false);
  };

  return (
    <div style={{ 
      fontFamily: 'system-ui, sans-serif', 
      padding: '16px', 
      maxWidth: '420px', 
      margin: '0 auto',
      background: 'var(--tg-theme-bg-color, #fff)',
      color: 'var(--tg-theme-text-color, #000)',
      minHeight: '100vh'
    }}>
      <h2 style={{ margin: '0 0 4px' }}>🚀 Render Benchmark</h2>
      <p style={{ margin: '0 0 16px', fontSize: '13px', opacity: 0.6 }}>
        Тестирует латентность твоего Render backend
      </p>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <button 
          onClick={runAll} 
          disabled={running}
          style={btnStyle('#2196F3')}
        >
          {running ? '⏳ Тестирую...' : '▶ Run All Tests'}
        </button>
        <button 
          onClick={runStabilityTest} 
          disabled={running}
          style={btnStyle('#9C27B0')}
        >
          📡 Stability
        </button>
      </div>

      {/* Результаты */}
      {TESTS.map(test => {
        const r = results[test.id];
        return (
          <div key={test.id} style={{ 
            background: 'rgba(0,0,0,0.05)', 
            borderRadius: '10px', 
            padding: '12px', 
            marginBottom: '8px',
            borderLeft: r ? `4px solid ${msColor(r.latency)}` : '4px solid #ccc'
          }}>
            <div style={{ fontWeight: 600 }}>{test.label}</div>
            {r ? (
              <div style={{ fontSize: '13px', marginTop: '4px' }}>
                <span style={{ 
                  color: msColor(r.latency), 
                  fontSize: '18px', 
                  fontWeight: 700 
                }}>
                  {r.latency}ms
                </span>
                {r.ok && r.data?.uptime_s && (
                  <span style={{ opacity: 0.6, marginLeft: '8px' }}>
                    uptime: {parseFloat(r.data.uptime).toFixed(1)}s
                  </span>
                )}
                {!r.ok && <span style={{ color: 'red' }}> ❌ {r.error}</span>}
              </div>
            ) : (
              <div style={{ fontSize: '12px', opacity: 0.4 }}>не запускался</div>
            )}
          </div>
        );
      })}

      {/* Лог */}
      {log.length > 0 && (
        <div style={{ 
          background: '#111', color: '#0f0', 
          borderRadius: '8px', padding: '10px', 
          fontSize: '12px', fontFamily: 'monospace',
          marginTop: '12px', maxHeight: '150px', overflowY: 'auto'
        }}>
          {log.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
    </div>
  );
}

const btnStyle = (bg) => ({
  flex: 1, padding: '10px', background: bg, 
  color: '#fff', border: 'none', borderRadius: '8px', 
  fontSize: '14px', cursor: 'pointer', fontWeight: 600
});

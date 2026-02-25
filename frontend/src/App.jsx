import React, { useEffect, useState, useRef } from 'react'

const API = import.meta.env.VITE_API_URL
  ? `https://${import.meta.env.VITE_API_URL}`
  : 'http://localhost:3001'

const WS = API.replace('https://', 'wss://').replace('http://', 'ws://')

export default function App() {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [gameState, setGameState] = useState({ status: 'waiting', multiplier: 1.0 })
  const [bet, setBet] = useState(10)
  const [cashedOut, setCashedOut] = useState(null)
  const [hasBet, setHasBet] = useState(false)
  const wsRef = useRef(null)

  // Telegram auto-login
  useEffect(() => {
    const tg = window.Telegram?.WebApp
    if (tg) tg.ready()

    const initData = tg?.initData || ''
    fetch(`${API}/api/auth/telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData }),
    })
      .then(r => r.json())
      .then(d => {
        setUser(d.user)
        setToken(d.token)
      })
      .catch(() => setUser({ first_name: 'Player' }))
  }, [])

  // WebSocket
  useEffect(() => {
    const ws = new WebSocket(WS)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'STATE') setGameState(msg.state)
      if (msg.type === 'TICK') setGameState(s => ({ ...s, multiplier: msg.multiplier, status: 'running' }))
      if (msg.type === 'CRASH') {
        setGameState(s => ({ ...s, status: 'crashed', crashAt: msg.crashAt }))
        setHasBet(false)
        setCashedOut(null)
      }
      if (msg.type === 'WAITING') setGameState(s => ({ ...s, status: 'waiting' }))
      if (msg.type === 'ROUND_START') setGameState(s => ({ ...s, status: 'running', multiplier: 1.0 }))
    }

    return () => ws.close()
  }, [])

  const statusColor = {
    waiting: '#a78bfa',
    running: '#22c55e',
    crashed: '#ef4444',
  }[gameState.status] || '#fff'

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--tg-theme-bg-color, #0f0f1a)',
      color: 'var(--tg-theme-text-color, #fff)',
      fontFamily: 'Inter, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '20px',
    }}>
      {/* Header */}
      <div style={{ width: '100%', maxWidth: 420, marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', opacity: 0.7 }}>
          👋 {user?.first_name || '...'}
        </h2>
        <h1 style={{ margin: '4px 0 0', fontSize: '1.6rem', fontWeight: 900 }}>
          🚀 Rocket Crash
        </h1>
      </div>

      {/* Multiplier Display */}
      <div style={{
        width: '100%', maxWidth: 420,
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 24,
        padding: '40px 20px',
        textAlign: 'center',
        marginBottom: 24,
        border: `1px solid ${statusColor}44`,
        boxShadow: `0 0 40px ${statusColor}22`,
      }}>
        {gameState.status === 'crashed' ? (
          <>
            <div style={{ fontSize: '3rem', marginBottom: 8 }}>💥</div>
            <div style={{ fontSize: '2.5rem', fontWeight: 900, color: '#ef4444' }}>
              CRASH @ {gameState.crashAt}x
            </div>
          </>
        ) : gameState.status === 'waiting' ? (
          <>
            <div style={{ fontSize: '3rem', marginBottom: 8 }}>⏳</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#a78bfa' }}>
              Следующий раунд...
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: '3rem', marginBottom: 8 }}>🚀</div>
            <div style={{
              fontSize: '4rem', fontWeight: 900,
              background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              {gameState.multiplier}x
            </div>
          </>
        )}
      </div>

      {/* Bet Panel */}
      <div style={{
        width: '100%', maxWidth: 420,
        background: 'rgba(255,255,255,0.05)',
        borderRadius: 20,
        padding: 20,
      }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input
            type="number"
            value={bet}
            onChange={e => setBet(Number(e.target.value))}
            min={1}
            style={{
              flex: 1, padding: '12px 16px',
              borderRadius: 12, border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.07)',
              color: 'white', fontSize: '1rem',
            }}
          />
          {[10, 25, 50, 100].map(v => (
            <button key={v} onClick={() => setBet(v)} style={{
              padding: '8px 12px', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.15)',
              background: bet === v ? '#7c3aed' : 'rgba(255,255,255,0.07)',
              color: 'white', cursor: 'pointer', fontSize: '0.85rem',
            }}>{v}</button>
          ))}
        </div>

        {!hasBet ? (
          <button
            disabled={gameState.status !== 'waiting'}
            onClick={() => { if (gameState.status === 'waiting') setHasBet(true) }}
            style={{
              width: '100%', padding: '14px',
              borderRadius: 16, border: 'none',
              background: gameState.status === 'waiting'
                ? 'linear-gradient(135deg, #7c3aed, #6d28d9)'
                : 'rgba(255,255,255,0.1)',
              color: 'white', fontSize: '1.1rem',
              fontWeight: 700, cursor: gameState.status === 'waiting' ? 'pointer' : 'not-allowed',
            }}>
            {gameState.status === 'waiting' ? `🎯 Ставка ${bet} монет` : 'Дождись следующего раунда'}
          </button>
        ) : (
          <button
            disabled={gameState.status !== 'running' || !!cashedOut}
            onClick={() => {
              if (gameState.status === 'running' && !cashedOut) {
                setCashedOut(gameState.multiplier)
              }
            }}
            style={{
              width: '100%', padding: '14px',
              borderRadius: 16, border: 'none',
              background: cashedOut
                ? 'rgba(34,197,94,0.3)'
                : 'linear-gradient(135deg, #22c55e, #16a34a)',
              color: 'white', fontSize: '1.1rem',
              fontWeight: 700, cursor: 'pointer',
              boxShadow: cashedOut ? 'none' : '0 4px 24px rgba(34,197,94,0.4)',
            }}>
            {cashedOut
              ? `✅ Выведено на ${cashedOut}x (+${(bet * cashedOut - bet).toFixed(0)})`
              : `💰 Вывести на ${gameState.multiplier}x`}
          </button>
        )}
      </div>
    </div>
  )
}

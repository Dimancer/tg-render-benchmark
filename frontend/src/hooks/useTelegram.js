// hooks/useTelegram.js
export function useTelegram() {
  const tg = window.Telegram.WebApp;

  const login = async () => {
    const initData = tg.initData; // уже подписано Telegram
    const res = await fetch('/api/auth/telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData }),
    });
    return res.json(); // { token, user }
  };

  return { tg, login, user: tg.initDataUnsafe?.user };
}

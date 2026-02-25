import hmac, hashlib, json, time
from urllib.parse import unquote
from fastapi import Request, HTTPException
from config import settings

def verify_telegram_init_data(init_data: str) -> dict | None:
    vals = dict(chunk.split('=', 1) for chunk in init_data.split('&') if '=' in chunk)
    received_hash = vals.pop('hash', None)
    if not received_hash:
        return None
    data_check = '\n'.join(f'{k}={unquote(v)}' for k, v in sorted(vals.items()))
    secret_key = hmac.new(b'WebAppData', settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed   = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None
    if time.time() - int(vals.get('auth_date', 0)) > 86400:
        return None
    return json.loads(unquote(vals.get('user', '{}')))

async def get_current_user_id(request: Request) -> int:
    init_data = request.headers.get('X-Tg-Init-Data')
    user_id_header = request.headers.get('X-User-Id')

    if init_data:
        user = verify_telegram_init_data(init_data)
        if not user:
            raise HTTPException(status_code=401, detail={"error": "invalid_init_data", "message": "Подпись Telegram не прошла"})
        return int(user['id'])

    if settings.DEV_MODE and user_id_header:
        return int(user_id_header)

    raise HTTPException(status_code=401, detail={"error": "invalid_init_data", "message": "Требуется авторизация"})

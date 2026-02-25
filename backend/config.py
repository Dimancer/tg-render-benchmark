from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    TELEGRAM_BOT_TOKEN: str = ""
    SECRET_KEY: str = "dev_secret"
    HOUSE_EDGE: float = 0.05
    MIN_BET: int = 10
    MAX_BET: int = 50000
    WITHDRAW_MIN: int = 200
    WITHDRAW_FEE: float = 0.05
    ALLOWED_ORIGINS: str = "https://web.telegram.org,http://localhost:3000"
    DEV_MODE: bool = False

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"

settings = Settings()

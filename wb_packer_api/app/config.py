# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "wb_packer")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "wb_packer")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "changeme")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_KEYS: list[str] = os.getenv("API_KEYS", "dev-key-change-me").split(",")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # Google Sheets
    GSHEETS_CREDENTIALS: str = os.getenv("GSHEETS_CREDENTIALS", "")
    GSHEETS_SPREADSHEET_ID: str = os.getenv(
        "GSHEETS_SPREADSHEET_ID", "1OGgsS0T4qaEekJgEkVTplZfoeQ7MeMth8o8eJTqnJGA"
    )
    GSHEETS_SKU_SPREADSHEET_ID: str = os.getenv(
        "GSHEETS_SKU_SPREADSHEET_ID", "1tQzh_qTnldbpeu9ryNF8ZKY4-amwT8UfuMqbSU1qOlA"
    )

    # Moysklad
    MOYSKLAD_TOKEN: str = os.getenv("MOYSKLAD_TOKEN", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        return (
            f"host={self.POSTGRES_HOST} port={self.POSTGRES_PORT} "
            f"dbname={self.POSTGRES_DB} user={self.POSTGRES_USER} password={self.POSTGRES_PASSWORD}"
        )


settings = Settings()

from functools import lru_cache
from urllib.parse import quote_plus  # <--- IMPORTA ESTO

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    JWT_SECRET: str

    @computed_field
    @property  # type: ignore[prop-decorator]
    def DATABASE_URL(self) -> str:
        # Esto convierte caracteres como @ en %40, evitando que rompan la URI
        safe_password = quote_plus(self.DB_PASSWORD)

        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{safe_password}"  # <--- USA LA CONTRASEÑA ESCAPEADA
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

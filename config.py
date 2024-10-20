from pydantic import RedisDsn, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import cast


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str

    YC_FOLDER_ID: str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    LOG_LEVEL: str = "INFO"

    ENV: str = "dev"

    @property
    def REDIS_DSN(self) -> RedisDsn:
        return cast(
            RedisDsn,
            RedisDsn.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=str(self.REDIS_DB),
            ),
        )

    @property
    def POSTGRES_DSN(self) -> PostgresDsn:
        return cast(
            PostgresDsn,
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            ),
        )


class DevSettings(BaseConfig):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    LOG_LEVEL: str = "DEBUG"


class ProdSettings(BaseConfig):
    model_config = SettingsConfigDict(env_file=None)

    LOG_LEVEL: str = "INFO"


def get_settings() -> BaseConfig:
    base_config = BaseConfig()
    if base_config.ENV == "prod":
        return ProdSettings()
    return DevSettings()


settings = get_settings()

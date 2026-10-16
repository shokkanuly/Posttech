import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "JanaMen Digital HR"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "synthetic-demo-secret-key-change-in-production-never-commit-secrets"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str = "sqlite:///./janamen.db"
    ENVIRONMENT: str = "development"
    AI_PROVIDER: str = "grounded_knowledge"
    AI_CONFIDENCE_THRESHOLD: float = 0.50
    HR_SUPPORT_EMAIL: str = "hr-support@janapost.kz"
    ENABLE_MOCK_INTEGRATIONS: bool = True
    MOCK_1C_BASE_URL: str = "https://mock-1c.internal.janapost.kz"
    MOCK_DOCUMENTOLOG_BASE_URL: str = "https://mock-doclog.internal.janapost.kz"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

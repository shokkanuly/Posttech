import secrets
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "JanaMen Digital HR"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(default="", repr=False)
    ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    DATABASE_URL: str = "sqlite:///./janamen.db"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEMO_MODE: bool = False
    DEMO_PASSWORD: str = Field(default="", repr=False)
    ALLOWED_ORIGINS: list[str] = []
    AI_PROVIDER: Literal["grounded_knowledge"] = "grounded_knowledge"
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)
    HR_SUPPORT_EMAIL: str = "hr-support@janapost.kz"
    ENABLE_MOCK_INTEGRATIONS: bool = False
    MOCK_1C_BASE_URL: str = "https://mock-1c.internal.janapost.kz"
    MOCK_DOCUMENTOLOG_BASE_URL: str = "https://mock-doclog.internal.janapost.kz"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_security(self):
        # Legacy configurations used unnormalised keyword scores. Keep a safe floor.
        self.AI_CONFIDENCE_THRESHOLD = max(0.75, self.AI_CONFIDENCE_THRESHOLD)
        insecure = len(self.SECRET_KEY) < 32 or any(
            word in self.SECRET_KEY.lower()
            for word in ("synthetic-demo", "change-in-production", "replace-me")
        )
        if self.ENVIRONMENT == "production":
            if insecure:
                raise ValueError(
                    "Production requires a strong SECRET_KEY from the environment (32+ characters)"
                )
            if self.DEMO_MODE:
                raise ValueError("DEMO_MODE must be disabled in production")
        elif insecure:
            self.SECRET_KEY = secrets.token_urlsafe(48)
        if "*" in self.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS must name explicit origins")
        return self


settings = Settings()

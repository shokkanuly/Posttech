import secrets
from datetime import date
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
    # "gemini" adds LLM phrasing on top of retrieval; every answer is still verified
    # against the cited sources and falls back to extractive text when it is not.
    AI_PROVIDER: Literal["grounded_knowledge", "gemini"] = "grounded_knowledge"
    # "ml" re-ranks coverage-approved passages with the trained JSON model (ml/README.md).
    AI_RETRIEVAL_MODE: Literal["lexical", "ml"] = "lexical"
    AI_RETRIEVAL_MODEL_PATH: str = ""
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)
    GEMINI_API_KEY: str = Field(default="", repr=False)
    GEMINI_MODEL: str = Field(default="gemini-3.8-flash", pattern=r"^[a-z0-9.\-]{3,64}$")
    GEMINI_TIMEOUT_SECONDS: float = Field(default=12.0, gt=0, le=60)
    MAX_ADVANCE_AMOUNT: float = Field(default=1_000_000, gt=0, allow_inf_nan=False)
    LEAVE_EXCLUDED_DATES: list[date] = Field(default_factory=list, max_length=1000)
    REQUEST_HORIZON_DAYS: int = Field(default=365, ge=1, le=730)
    HR_SUPPORT_EMAIL: str = "hr-support@janapost.kz"
    ENABLE_MOCK_INTEGRATIONS: bool = False
    MAX_REQUEST_BODY_BYTES: int = Field(default=262144, ge=65536, le=1048576)
    MOCK_1C_BASE_URL: str = "https://mock-1c.internal.janapost.kz"
    MOCK_DOCUMENTOLOG_BASE_URL: str = "https://mock-doclog.internal.janapost.kz"
    # Integration gateway (docs/INTEGRATIONS.md). Empty URL: nothing is queued or sent.
    INTEGRATION_GATEWAY_URL: str = ""
    INTEGRATION_OUTBOUND_KEY_ID: str = ""
    INTEGRATION_OUTBOUND_KEY: str = Field(default="", repr=False)
    # key_id -> secret accepted from the gateway; two ids overlap during key rotation.
    INTEGRATION_INBOUND_KEYS: dict[str, str] = Field(default_factory=dict, repr=False)
    # mTLS client certificate for the gateway and the private CA that issued the gateway's.
    INTEGRATION_TLS_CERT: str = ""
    INTEGRATION_TLS_KEY: str = Field(default="", repr=False)
    INTEGRATION_TLS_CA: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_security(self):
        if self.AI_RETRIEVAL_MODE == "ml" and not self.AI_RETRIEVAL_MODEL_PATH:
            raise ValueError("ML retrieval requires AI_RETRIEVAL_MODEL_PATH")
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
        integration_keys = list(self.INTEGRATION_INBOUND_KEYS.values())
        if self.INTEGRATION_GATEWAY_URL:
            if not self.INTEGRATION_OUTBOUND_KEY_ID:
                raise ValueError("INTEGRATION_GATEWAY_URL requires INTEGRATION_OUTBOUND_KEY_ID")
            integration_keys.append(self.INTEGRATION_OUTBOUND_KEY)
        if any(len(key) < 32 for key in integration_keys):
            raise ValueError("Integration keys must be at least 32 random characters")
        if (
            self.ENVIRONMENT == "production"
            and self.INTEGRATION_GATEWAY_URL
            and not (
                self.INTEGRATION_GATEWAY_URL.startswith("https://")
                and self.INTEGRATION_TLS_CERT
                and self.INTEGRATION_TLS_KEY
            )
        ):
            raise ValueError("Production gateway requires https and an mTLS client certificate")
        return self


settings = Settings()

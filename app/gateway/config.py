from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_", extra="ignore", hide_input_in_errors=True
    )

    MODE: Literal["MOCK"] = "MOCK"
    DATABASE_URL: str = "sqlite:///./gateway.db"
    JANAMEN_KEYS: dict[str, str] = Field(default_factory=dict, repr=False)
    APP_KEY_ID: str = ""
    APP_KEY: str = Field(default="", repr=False)
    CALLBACK_URL: str = "http://web:8000/api/v1/internal/integrations/documentolog/status"
    CALLBACK_KEY_ID: str = ""
    CALLBACK_KEY: str = Field(default="", repr=False)
    TLS_CA: str = ""
    TLS_CERT: str = ""
    TLS_KEY: str = Field(default="", repr=False)
    WORKER_ENABLED: bool = True
    POLL_SECONDS: float = Field(default=1, ge=0.05, le=60)
    MOCK_EMPLOYEES_FILE: str = ""
    MOCK_ONE_C_UNAVAILABLE: bool = False
    MOCK_DOCUMENTOLOG_FAILURE: Literal["none", "temporary", "validation"] = "none"

    @model_validator(mode="after")
    def valid_keys(self):
        if self.APP_KEY:
            if not self.APP_KEY_ID:
                raise ValueError("GATEWAY_APP_KEY_ID is required")
            self.JANAMEN_KEYS = {**self.JANAMEN_KEYS, self.APP_KEY_ID: self.APP_KEY}
        keys = list(self.JANAMEN_KEYS.values())
        if self.CALLBACK_KEY:
            keys.append(self.CALLBACK_KEY)
            if not self.CALLBACK_KEY_ID:
                raise ValueError("GATEWAY_CALLBACK_KEY_ID is required")
        if any(len(key) < 32 for key in keys):
            raise ValueError("Integration keys must be at least 32 random characters")
        return self

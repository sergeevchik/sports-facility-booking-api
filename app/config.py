from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr
    api_key: SecretStr = Field(min_length=24)
    app_version: str = "1.0.0"
    app_timezone: str = "Europe/Moscow"
    opening_hour: int = Field(default=8, ge=0, le=23)
    closing_hour: int = Field(default=22, ge=1, le=24)
    min_booking_minutes: int = Field(default=30, ge=30)
    max_booking_minutes: int = Field(default=180, ge=30)

    @model_validator(mode="after")
    def check_policy(self):
        ZoneInfo(self.app_timezone)
        if self.opening_hour >= self.closing_hour:
            raise ValueError("opening_hour must precede closing_hour")
        if self.min_booking_minutes > self.max_booking_minutes:
            raise ValueError("minimum duration exceeds maximum")
        if self.min_booking_minutes % 30 or self.max_booking_minutes % 30:
            raise ValueError("duration limits must be multiples of 30 minutes")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Configuration for the optional development seed; not required to start the API."""

from pydantic import EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SeedSettings(BaseSettings):
    seed_admin_name: str = Field(min_length=1, max_length=150)
    seed_admin_email: EmailStr
    seed_admin_password: SecretStr = Field(min_length=8)
    seed_production_name: str = Field(min_length=1, max_length=150)
    seed_production_email: EmailStr
    seed_production_password: SecretStr = Field(min_length=8)
    seed_inventory_name: str = Field(min_length=1, max_length=150)
    seed_inventory_email: EmailStr
    seed_inventory_password: SecretStr = Field(min_length=8)

    @model_validator(mode="after")
    def unique_emails(self):
        emails = [
            self.seed_admin_email.lower(),
            self.seed_production_email.lower(),
            self.seed_inventory_email.lower(),
        ]
        if len(set(emails)) != len(emails):
            raise ValueError("Seed emails must be distinct")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

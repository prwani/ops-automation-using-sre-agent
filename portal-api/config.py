"""Application configuration from environment variables."""

import json
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    cosmos_endpoint: str = ""
    cosmos_database: str = "ops-automation"
    foundry_endpoint: str = ""
    foundry_api_key: str = ""
    foundry_ops_chat_agent_id: str = ""
    allowed_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_allowed_origins(self) -> list[str]:
        """Parse allowed_origins as a list (supports JSON arrays and comma-separated)."""
        raw = self.allowed_origins.strip()
        if raw.startswith("["):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()

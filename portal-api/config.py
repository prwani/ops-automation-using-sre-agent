"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    cosmos_endpoint: str = ""
    cosmos_database: str = "ops-automation"
    foundry_endpoint: str = ""
    foundry_api_key: str = ""
    foundry_ops_chat_agent_id: str = ""
    allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

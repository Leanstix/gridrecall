from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    database_url: str | None = None
    aws_region: str = "us-east-1"
    bedrock_reasoning_model_id: str | None = None
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    cockroach_mcp_url: str = "https://cockroachlabs.cloud/mcp"
    cockroach_mcp_cluster_id: str | None = None
    cockroach_mcp_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def demo_mode(self) -> bool:
        return not all(
            [
                self.database_url,
                self.bedrock_reasoning_model_id,
                self.cockroach_mcp_cluster_id,
                self.cockroach_mcp_api_key,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

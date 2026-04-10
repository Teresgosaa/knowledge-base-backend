from typing import List, Set

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.vault import parse_vault_params, vault_connect, vault_get_value

HEADER = "\033[95m"
RESET = "\033[0m"


class Settings(BaseSettings):
    """
    Application settings.

    Configured from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000

    workers_count: int = 1
    """
    Number of workers for uvicorn.
    """

    reload: bool = False
    """
    Uvicorn reloading.
    """

    environment: str = "dev"
    """
    Running environment.
    """

    # Variables for the metadata database
    db_postgres_host: str = "localhost"
    db_postgres_port: int = 5432
    db_postgres_user: str = "admin"
    db_postgres_password: str = "admin"
    db_postgres_name: str = "agent_db"
    database_url: str = ""

    # Variables for the neo4j database
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = ""
    neo4j_password: str = ""

    # Allowed origins
    allowed_hosts: List[str] = []
    cors_origins: List[str] = []

    # S3 credentials
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = ""
    s3_bucket_name: str = ""
    s3_endpoint_url: str = ""

    yandex_cloud_folder: str = ""
    yandex_cloud_api_key: str = ""
    yandex_cloud_model: str = ""
    yandex_cloud_oauth_token: str = ""
    yandex_cloud_ai_base_url: str = ""
    yandex_cloud_ai_folder: str = ""

    max_file_size_mb: int = 10
    allowed_file_types: Set[str] = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "application/pdf",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    }

    # Upload settings
    chunk_size: int = 8192  # 8KB chunks for streaming
    presigned_url_expiry: int = 3600  # 1 hour

    max_polling_time: int = 3600

    secret_key: str = ""
    refresh_token_expire_days: int = 1

    verify_ssl: bool = True


settings = Settings()  # type: ignore


print(f"{HEADER}DB HOST:{RESET}     {settings.db_postgres_host}")
print(f"{HEADER}HOSTS:{RESET}       {settings.allowed_hosts + settings.cors_origins}")

for key, value in settings:
    if isinstance(value, str) and value.startswith("!vault"):
        params = parse_vault_params(value)
        client = vault_connect(params)
        value = vault_get_value(client, params["SECRET"], params["PATH"], params["KEY"])
        setattr(settings, key, value)

# File end

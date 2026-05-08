from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "AI_PaperCraft_Studio"
    database_url: str = "postgresql+psycopg://papercraft:papercraft_dev@127.0.0.1:5432/papercraft"
    redis_url: str = "redis://127.0.0.1:6379/0"
    s3_endpoint: str = "http://127.0.0.1:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_uploads: str = "papercraft-local-uploads"
    s3_bucket_artifacts: str = "papercraft-local-artifacts"
    s3_force_path_style: bool = True
    max_upload_mb: int = 20
    max_upload_images: int = 3
    task_timeout_seconds: int = 1800
    jwt_secret: str = "change-me-before-production"
    jwt_algorithm: str = "HS256"

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

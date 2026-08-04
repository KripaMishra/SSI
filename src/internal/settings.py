from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 1536

    chroma_api_key: str = ""
    chroma_tenant: str = ""
    chroma_database: str = ""
    chroma_collection: str = "ssi_docs"
    chroma_cloud_host: str = ""
    chroma_cloud_port: int = 443
    chroma_local_path: str = ".chroma"

    postgres_url: str = ""
    sqlite_local_path: str = "src/internal/db/ssi.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
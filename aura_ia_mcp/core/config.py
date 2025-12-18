from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "extra": "ignore",
        "env_file": ".env",
        "case_sensitive": True,
    }
    AURA_SAFE_MODE: bool = False
    ENABLE_AUTONOMY: bool = True
    ENABLE_TRAINING: bool = True
    ENABLE_ROLE_MUTATION: bool = True
    AUDIT_LOG_PATH: str = "logs/security_audit.jsonl"
    PORT_ROOT: int = 9200
    PORT_LLM_PROXY: int = 9201
    PORT_EMBEDDING: int = 9202
    PORT_RAG: int = 9203
    PORT_ROLE_ENGINE: int = 9204
    PORT_RESERVED_1: int = 9205
    PORT_RESERVED_2: int = 9206


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
    return Settings()

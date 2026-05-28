from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent.providers.base import LLMProvider

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent_name: str = "Nyx"
    provider: Literal["cohere", "openai", "anthropic"] = "cohere"
    cohere_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_model: str = "command-r-plus"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    chroma_path: str = "./data/chroma"
    db_path: str = "./data/memory.db"
    max_history: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.provider == "cohere":
        from agent.providers.cohere_provider import CohereProvider

        return CohereProvider(settings)
    if settings.provider == "openai":
        from agent.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    if settings.provider == "anthropic":
        from agent.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    raise ValueError(f"Unknown provider: {settings.provider}")


def clear_settings_cache() -> None:
    get_settings.cache_clear()

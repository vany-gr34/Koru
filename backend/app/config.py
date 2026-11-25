from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_model: str = "anthropic:claude-sonnet-5-5"
    database_url: str = ""  # empty -> in-memory checkpointer (dev/tests)


settings = Settings()

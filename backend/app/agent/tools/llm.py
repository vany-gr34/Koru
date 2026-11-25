from functools import lru_cache

from app.config import settings


@lru_cache
def get_llm():
    if settings.llm_model.startswith("ollama:"):
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.llm_model.removeprefix("ollama:"),
            base_url=settings.ollama_base_url,
            temperature=0,
        )

    from langchain.chat_models import init_chat_model

    return init_chat_model(settings.llm_model, temperature=0)
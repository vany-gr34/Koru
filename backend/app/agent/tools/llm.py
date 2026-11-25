from functools import lru_cache

from app.config import settings


@lru_cache
def get_llm():
    from langchain.chat_models import init_chat_model

    return init_chat_model(settings.llm_model, temperature=0)

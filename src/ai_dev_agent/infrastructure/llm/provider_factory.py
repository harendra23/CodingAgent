from langchain_core.language_models import BaseChatModel

from ai_dev_agent.config import Settings


def create_chat_model(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.effective_llm_model, api_key=settings.openai_api_key)

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.effective_llm_model,
            api_key=settings.anthropic_api_key,
        )

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.effective_llm_model,
        google_api_key=settings.google_api_key,
    )

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.config import get_settings, GROQ_MODEL, GEMINI_MODEL


def get_groq_llm(temperature: float = 0.7) -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model=GROQ_MODEL,
        groq_api_key=settings.groq_api_key,
        temperature=temperature,
        max_tokens=256,
    )


def get_gemini_llm(temperature: float = 0.7) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=settings.google_ai_api_key,
        temperature=temperature,
        max_tokens=256,
    )


def get_llm_with_fallback(temperature: float = 0.7):
    primary = get_groq_llm(temperature)
    fallback = get_gemini_llm(temperature)
    return primary.with_fallbacks([fallback])

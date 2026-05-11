from langchain_core.output_parsers import StrOutputParser

from apps.api.prompts.intent_prompt import INTENT_CLASSIFY_PROMPT
from apps.api.chains.fallbacks import get_groq_llm, get_gemini_llm

_VALID_INTENTS = {"DISTRESS", "OFF_TOPIC", "SCENARIO_QUESTION", "ROLEPLAY_TURN"}


def build_intent_chain():
    groq = get_groq_llm(temperature=0.0)
    gemini = get_gemini_llm(temperature=0.0)
    llm = groq.with_fallbacks([gemini])
    return INTENT_CLASSIFY_PROMPT | llm | StrOutputParser()


def parse_intent(raw: str) -> str:
    cleaned = raw.strip().upper().replace(" ", "_")
    if cleaned in _VALID_INTENTS:
        return cleaned
    return "ROLEPLAY_TURN"

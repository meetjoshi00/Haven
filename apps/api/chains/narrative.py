from __future__ import annotations

import logging

from langchain_core.output_parsers import StrOutputParser

from apps.api.chains.fallbacks import get_groq_llm
from apps.api.prompts.narrative_prompt import NARRATIVE_PROMPT

logger = logging.getLogger(__name__)

FALLBACK_NARRATIVE = "Physiological stress signals elevated."

_chain = None


def build_narrative_chain():
    global _chain
    if _chain is None:
        _chain = NARRATIVE_PROMPT | get_groq_llm(temperature=0.0) | StrOutputParser()
    return _chain


def trim_to_25_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:25]) if len(words) > 25 else text

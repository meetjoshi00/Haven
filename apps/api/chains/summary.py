from langchain_core.output_parsers import StrOutputParser

from apps.api.prompts.summary_prompt import SUMMARY_PROMPT
from apps.api.chains.fallbacks import get_llm_with_fallback


def build_summary_chain():
    llm = get_llm_with_fallback(temperature=0.5)
    return SUMMARY_PROMPT | llm | StrOutputParser()

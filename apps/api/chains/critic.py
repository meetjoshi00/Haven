import json

from langchain_core.runnables import RunnableLambda

from apps.api.prompts.critic_prompt import CRITIC_PROMPT
from apps.api.chains.fallbacks import get_llm_with_fallback

SAFE_DEFAULT = {"score": 3, "suggestion": ""}


def _safe_parse(ai_message) -> dict:
    try:
        text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n", 1)
            text = lines[1] if len(lines) > 1 else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        parsed = json.loads(text)
        score = parsed.get("score", 3)
        if not isinstance(score, (int, float)) or score < 1 or score > 5:
            score = 3
        else:
            score = int(score)
        suggestion = parsed.get("suggestion", "")
        if not isinstance(suggestion, str):
            suggestion = ""
        return {"score": score, "suggestion": suggestion}
    except Exception:
        return SAFE_DEFAULT.copy()


def build_critic_chain():
    llm = get_llm_with_fallback(temperature=0.3)
    return CRITIC_PROMPT | llm | RunnableLambda(_safe_parse)

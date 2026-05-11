def check_distress(user_text: str, keywords: list[str]) -> bool:
    text_lower = user_text.lower()
    return any(kw in text_lower for kw in keywords)

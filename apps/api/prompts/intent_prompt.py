from langchain_core.prompts import ChatPromptTemplate

INTENT_CLASSIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are classifying messages in a social-skills roleplay.\n"
            "Current scenario: {scenario_title}\n"
            "Setting: {setting}\n\n"
            "The persona's most recent message: {last_persona_message}\n\n"
            "Classify the user's reply into exactly ONE category. "
            "Respond with ONLY the category name, nothing else.\n\n"
            "DISTRESS — crisis, self-harm, suicidal ideation, acute overwhelm, abuse disclosure\n"
            "OFF_TOPIC — clearly unrelated to the scenario AND not a natural part of the "
            "social interaction (e.g., discussing a movie during a job interview)\n"
            "SCENARIO_QUESTION — question about the scenario itself, what to practice, "
            "or how the system works\n"
            "ROLEPLAY_TURN — any response that continues the social interaction, including:\n"
            "  - Direct replies to the persona\n"
            "  - Greetings, small talk, or casual language natural to the setting\n"
            "  - Brief, terse, or incomplete responses\n"
            "  - Slang, informal speech, or filler words\n\n"
            "Key rule: if the message could naturally occur in the scenario's social "
            "setting, classify it as ROLEPLAY_TURN even if it seems brief or off-hand.\n\n"
            "Examples:\n"
            '- "Hey watsup" in a coffee shop → ROLEPLAY_TURN\n'
            '- "umm hi" in any scenario → ROLEPLAY_TURN\n'
            '- "yeah sure" after persona asks a question → ROLEPLAY_TURN\n'
            '- "definitely" → ROLEPLAY_TURN\n'
            '- "What is this app?" → SCENARIO_QUESTION\n'
            '- "Tell me about quantum physics" in a coffee shop → OFF_TOPIC',
        ),
        ("human", "{user_text}"),
    ]
)

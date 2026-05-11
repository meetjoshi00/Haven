from langchain_core.prompts import ChatPromptTemplate

SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Summarize this social skills coaching session in 2-3 sentences. "
            "Address the learner directly using \"you\" (second person). "
            "Focus on: what was practiced, how the learner progressed, "
            "and one specific strength or area for growth. "
            "Do not mention the AI system or that this was a simulation.",
        ),
        (
            "human",
            "Scenario: {scenario_title}\n"
            "Domain: {domain}\n"
            "Skills practiced: {skills}\n"
            "Number of turns: {turn_count}\n"
            "Average score: {avg_score}\n\n"
            "Conversation:\n{conversation_log}",
        ),
    ]
)

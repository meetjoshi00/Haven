from langchain_core.prompts import ChatPromptTemplate

NARRATIVE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You explain physiological stress signals in plain, calm English. "
        "Write exactly one sentence. Maximum 25 words. "
        "No jargon, no risk scores, no clinical language. "
        "Start directly with the explanation — no preamble.",
    ),
    ("human", "Cause tags: {cause_tags}. Generate the 'why' explanation."),
])

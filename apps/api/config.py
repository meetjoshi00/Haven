import os
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent.parent / "content"
SCENARIOS_DIR = CONTENT_DIR / "scenarios"
PERSONAS_DIR = CONTENT_DIR / "personas"
RUBRICS_DIR = CONTENT_DIR / "rubrics"
SAFETY_DIR = CONTENT_DIR / "safety"

DEFAULT_MAX_TURNS = 12
MIN_TURNS = 6
MAX_TURNS_CAP = 16

MEMORY_COSINE_THRESHOLD = 0.40
MEMORY_TOP_K = 3

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.5-flash-lite"


_API_DIR = Path(__file__).parent
_PROJECT_ROOT = _API_DIR.parent.parent

RULES_YAML_PATH = _PROJECT_ROOT / "rules" / "intervention_rules.yaml"
RISK_CALIBRATION_PATH = _PROJECT_ROOT / "ml" / "models" / "risk_calibration.json"
RISK_CALIBRATION_WEARABLE_PATH = _PROJECT_ROOT / "ml" / "models" / "risk_calibration_wearable.json"


class Settings:
    def __init__(self) -> None:
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self.google_ai_api_key = os.environ.get("GOOGLE_AI_API_KEY", "")
        self.supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
        self.supabase_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.upstash_redis_url   = os.environ.get("UPSTASH_REDIS_REST_URL", "")
        self.upstash_redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
        self.brevo_api_key       = os.environ.get("BREVO_API_KEY", "")
        self.brevo_from_email    = os.environ.get("BREVO_FROM_EMAIL", "")

    def validate(self) -> None:
        missing = []
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.google_ai_api_key:
            missing.append("GOOGLE_AI_API_KEY")
        if not self.supabase_url:
            missing.append("NEXT_PUBLIC_SUPABASE_URL")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise RuntimeError(f"Missing env vars: {', '.join(missing)}")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

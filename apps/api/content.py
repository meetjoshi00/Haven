from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml

from apps.api.config import SCENARIOS_DIR, PERSONAS_DIR, RUBRICS_DIR, SAFETY_DIR


def _load_md_dir(directory: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        post = frontmatter.load(str(path))
        meta = dict(post.metadata)
        file_id = meta.get("id", path.stem)
        result[file_id] = {"metadata": meta, "body": post.content}
    return result


def load_all_scenarios() -> dict[str, dict]:
    return _load_md_dir(SCENARIOS_DIR)


def load_all_personas() -> dict[str, dict]:
    return _load_md_dir(PERSONAS_DIR)


def load_all_rubrics() -> dict[str, dict]:
    return _load_md_dir(RUBRICS_DIR)


def load_distress_keywords() -> list[str]:
    path = SAFETY_DIR / "distress_keywords.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    keywords: list[str] = []
    categories = data.get("categories", {})
    for category in categories.values():
        phrases = category.get("phrases", [])
        keywords.extend(phrase.lower() for phrase in phrases)
    return keywords


def load_safe_response() -> str:
    path = SAFETY_DIR / "safe_response.md"
    post = frontmatter.load(str(path))
    content = post.content
    for marker in ("## Design notes", "## Tone principles"):
        idx = content.find(marker)
        if idx != -1:
            content = content[:idx]
    return content.strip()


@dataclass
class ContentStore:
    scenarios: dict[str, dict] = field(default_factory=dict)
    personas: dict[str, dict] = field(default_factory=dict)
    rubrics: dict[str, dict] = field(default_factory=dict)
    distress_keywords: list[str] = field(default_factory=list)
    safe_response_text: str = ""


def init_content_store() -> ContentStore:
    return ContentStore(
        scenarios=load_all_scenarios(),
        personas=load_all_personas(),
        rubrics=load_all_rubrics(),
        distress_keywords=load_distress_keywords(),
        safe_response_text=load_safe_response(),
    )

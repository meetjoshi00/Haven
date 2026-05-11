from __future__ import annotations

import hashlib
import logging

import httpx

from apps.api.config import get_settings

logger = logging.getLogger(__name__)


def _cache_key(cause_tags: list[str]) -> str:
    joined = ",".join(sorted(cause_tags))
    return "narrative:" + hashlib.sha256(joined.encode()).hexdigest()


async def get_cached_narrative(cause_tags: list[str]) -> str | None:
    s = get_settings()
    if not s.upstash_redis_url or not s.upstash_redis_token:
        logger.warning("Upstash env vars missing — narrative cache disabled")
        return None
    headers = {"Authorization": f"Bearer {s.upstash_redis_token}"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                s.upstash_redis_url,
                json=["GET", _cache_key(cause_tags)],
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("result")
    except Exception as exc:
        logger.warning("Redis GET failed: %s", exc)
        return None


async def set_cached_narrative(cause_tags: list[str], narrative: str) -> None:
    s = get_settings()
    if not s.upstash_redis_url or not s.upstash_redis_token:
        return
    headers = {"Authorization": f"Bearer {s.upstash_redis_token}"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                s.upstash_redis_url,
                json=["SETEX", _cache_key(cause_tags), "86400", narrative],
                headers=headers,
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Redis SETEX failed: %s", exc)

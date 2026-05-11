from __future__ import annotations

import logging

import httpx

from apps.api.config import get_settings

logger = logging.getLogger(__name__)


async def broadcast_realtime(channel: str, event: str, payload: dict) -> None:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        logger.warning("Supabase env vars missing — Realtime broadcast skipped")
        return
    url = f"{s.supabase_url}/realtime/v1/api/broadcast"
    headers = {
        "Authorization": f"Bearer {s.supabase_service_key}",
        "apikey": s.supabase_service_key,
    }
    body = {"messages": [{"topic": channel, "event": event, "payload": payload}]}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            (await client.post(url, json=body, headers=headers)).raise_for_status()
            logger.debug("Realtime broadcast sent: channel=%s event=%s", channel, event)
    except Exception as exc:
        logger.warning("Realtime broadcast failed channel=%s: %s", channel, exc)


async def send_email(to_email: str, subject: str, html_body: str) -> None:
    s = get_settings()
    if not s.brevo_api_key:
        logger.warning("BREVO_API_KEY missing — email to %s skipped", to_email)
        return
    body = {
        "sender": {"name": "Haven", "email": s.brevo_from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
    }
    headers = {"api-key": s.brevo_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            (await client.post(
                "https://api.brevo.com/v3/smtp/email",
                json=body,
                headers=headers,
            )).raise_for_status()
            logger.info("Email sent to %s", to_email)
    except Exception as exc:
        logger.warning("Email to %s failed: %s", to_email, exc)

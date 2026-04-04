"""
Telegram Bot API notification service for booking system.

Function: send_booking_notification — sends a Telegram message when a new booking is confirmed.
Called from: backend.main (booking webhook endpoint)
Invokes: Telegram Bot API via httpx.
Purpose: Fire-and-forget notification to Yanqing when a consulting session is booked.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_booking_notification(
    name: str,
    email: str,
    session_type: str,
    slot_start: str,
) -> bool:
    """Send Telegram message via Bot API. Fire-and-forget, errors are logged not raised.

    Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.

    Returns True if sent, False on error.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("[TELEGRAM] Bot token or chat ID not configured — skipping notification")
        return False

    message = (
        "\U0001f5d3 New consulting booking!\n"
        f"{name} ({email})\n"
        f"{session_type}min session at {slot_start}"
    )

    url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("[TELEGRAM] Booking notification sent for %s (%s)", name, email)
            return True
    except Exception as exc:
        logger.error("[TELEGRAM] Failed to send notification: %s", exc)
        return False
